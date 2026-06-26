from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, Any, List
import logging
from app.models.schemas import MergeRequest, Commit, Comment, Contributor, CacheMetadata
from app.services.gitlab_client import GitLabClient
from app.services.multi_group_client import MultiGroupGitLabClient
from app.config import settings

logger = logging.getLogger(__name__)


class MetricsService:
    def __init__(self, db: Session, group_id: Optional[str] = None):
        self.db = db
        self.group_id = group_id

        # Use multi-group client if no specific group requested
        groups = settings.get_groups()
        enabled_groups = [g for g in groups if g.get('enabled', True)]

        if group_id:
            # Single-group mode: find the specific group config
            group_config = next((g for g in groups if g['id'] == group_id), None)
            if group_config:
                self.gitlab_client = GitLabClient(
                    group_path=group_config['path'],
                    group_id=group_id,
                    source_type=group_config.get('type', 'group')
                )
            else:
                # Fallback to default
                self.gitlab_client = GitLabClient(group_id=group_id)
        elif len(enabled_groups) == 1:
            # Single-group mode (backward compatibility)
            group = enabled_groups[0]
            self.gitlab_client = GitLabClient(
                group_path=group['path'],
                group_id=group['id'],
                source_type=group.get('type', 'group')
            )
        else:
            # Multi-group mode
            self.gitlab_client = MultiGroupGitLabClient()

    def should_refresh_cache(self, data_type: str) -> bool:
        """Check if cache should be refreshed based on age."""
        metadata = self.db.query(CacheMetadata).filter(
            CacheMetadata.data_type == data_type
        ).first()

        if not metadata:
            return True

        cache_age = datetime.utcnow() - metadata.last_updated
        max_age = timedelta(hours=settings.cache_duration_hours)

        return cache_age > max_age

    def update_cache_metadata(self, data_type: str):
        """Update cache metadata timestamp."""
        metadata = self.db.query(CacheMetadata).filter(
            CacheMetadata.data_type == data_type
        ).first()

        if metadata:
            metadata.last_updated = datetime.utcnow()
            metadata.is_updating = False
        else:
            metadata = CacheMetadata(
                data_type=data_type,
                last_updated=datetime.utcnow(),
                is_updating=False
            )
            self.db.add(metadata)

        self.db.commit()

    def refresh_merge_requests(self, days: int = 30):
        """Refresh merge requests cache."""
        # MultiGroupGitLabClient has get_all_merge_requests, GitLabClient has get_merge_requests
        if isinstance(self.gitlab_client, MultiGroupGitLabClient):
            mrs_data = self.gitlab_client.get_all_merge_requests(days=days)
        else:
            mrs_data = self.gitlab_client.get_merge_requests(days=days)

        self.db.query(MergeRequest).delete()

        for mr_data in mrs_data:
            mr = MergeRequest(**mr_data)
            self.db.add(mr)

        self.db.commit()
        self.update_cache_metadata("merge_requests")

    def refresh_commits(self, days: int = 30):
        """Refresh commits cache."""
        # Skip for MultiGroupGitLabClient - commits derived from contributor stats in hybrid mode
        if isinstance(self.gitlab_client, MultiGroupGitLabClient):
            self.update_cache_metadata("commits")
            return

        commits_data = self.gitlab_client.get_commits(days=days)

        self.db.query(Commit).delete()

        for commit_data in commits_data:
            commit = Commit(**commit_data)
            self.db.add(commit)

        self.db.commit()
        self.update_cache_metadata("commits")

    def refresh_comments(self, days: int = 30):
        """Refresh comments cache."""
        # Skip comment fetching if review metrics are disabled (major performance improvement)
        if not settings.enable_review_metrics:
            self.update_cache_metadata("comments")
            return

        # For MultiGroupGitLabClient, fetch comments from all groups if FETCH_COMMENT_DETAILS=True
        if isinstance(self.gitlab_client, MultiGroupGitLabClient):
            if settings.fetch_comment_details:
                # Fetch comments from all groups
                comments_data = self.gitlab_client.get_all_comments(days=days)
            else:
                # Skip in hybrid mode (comments derived from contributor stats)
                self.update_cache_metadata("comments")
                return
        else:
            comments_data = self.gitlab_client.get_comments(days=days)

        self.db.query(Comment).delete()

        for comment_data in comments_data:
            comment = Comment(**comment_data)
            self.db.add(comment)

        self.db.commit()
        self.update_cache_metadata("comments")

    def refresh_contributors(self, days: int = 30, fetch_details: bool = False):
        """Refresh contributors cache - Phase 1 (fast) or Phase 2 (detailed)."""

        # Fetch MRs (fast - single API call, group-scoped)
        # MultiGroupGitLabClient has get_all_merge_requests, GitLabClient has get_merge_requests
        if isinstance(self.gitlab_client, MultiGroupGitLabClient):
            mrs_data = self.gitlab_client.get_all_merge_requests(days=days)
        else:
            mrs_data = self.gitlab_client.get_merge_requests(days=days)

        # Get contributor stats (fast if fetch_details=False, slow if True)
        contributor_stats = self.gitlab_client.get_contributor_stats_from_mrs(mrs_data, days=days, fetch_details=fetch_details)

        self.db.query(Contributor).delete()

        for contrib_data in contributor_stats:
            contributor = Contributor(**contrib_data)
            self.db.add(contributor)

        self.db.commit()
        self.update_cache_metadata("contributors")

    def refresh_contributors_detailed(self, days: int = 30):
        """Phase 2: Refresh with detailed commit/comment counts (slow background operation)."""
        self.refresh_contributors(days=days, fetch_details=True)

    def get_merge_request_metrics(
        self,
        days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_id: Optional[str] = None
    ):
        """Get merge request metrics, optionally filtered by group or custom date range."""
        from datetime import datetime

        # Determine if we need to refresh based on date range
        need_refresh = self.should_refresh_cache("merge_requests")
        refresh_days = days

        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)

            # Calculate days from start_date to now (to ensure we fetch enough data)
            days_from_start = (datetime.utcnow() - start_dt).days + 1  # +1 to be inclusive
            refresh_days = max(days_from_start, days)

            # Check if we have any data that covers the requested range
            oldest_mr = self.db.query(MergeRequest).order_by(MergeRequest.created_at.asc()).first()
            if not oldest_mr or oldest_mr.created_at > start_dt:
                # Cache doesn't go back far enough, force refresh
                need_refresh = True
                print(f"Cache refresh needed: oldest_mr={oldest_mr.created_at if oldest_mr else 'None'}, requested start={start_dt}")

            # Also check if we're requesting more days back than last refresh
            # (e.g., previously fetched 30 days, now requesting 175 days)
            if days_from_start > days:
                need_refresh = True
                print(f"Cache refresh needed: requesting {days_from_start} days back, parameter was {days}")

        if need_refresh:
            self.refresh_merge_requests(days=refresh_days)

        # Build query with optional group filter
        query = self.db.query(MergeRequest)
        if group_id or self.group_id:
            filter_group = group_id or self.group_id
            query = query.filter(MergeRequest.group_id == filter_group)

        # Apply date range filter
        if start_date and end_date:
            # Custom date range
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(
                MergeRequest.created_at >= start_dt,
                MergeRequest.created_at <= end_dt
            )
        else:
            # Days-based filter: show only MRs from the last N days
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(MergeRequest.created_at >= cutoff_date)

        mrs = query.all()

        total = len(mrs)
        merged = len([mr for mr in mrs if mr.state == "merged"])
        open_mrs = len([mr for mr in mrs if mr.state == "opened"])
        closed = len([mr for mr in mrs if mr.state == "closed"])

        # Calculate stale MRs - check ALL currently open MRs regardless of date range
        # (stale detection is about what needs attention NOW, not what was created in a time period)
        stale_threshold = datetime.utcnow() - timedelta(days=settings.stale_mr_days)
        stale_query = self.db.query(MergeRequest).filter(
            MergeRequest.state == "opened",
            MergeRequest.created_at < stale_threshold
        )

        # Apply group filter if specified (but NOT date range filter)
        if group_id or self.group_id:
            filter_group = group_id or self.group_id
            stale_query = stale_query.filter(MergeRequest.group_id == filter_group)

        stale_count = stale_query.count()

        merged_mrs_with_time = [mr for mr in mrs if mr.time_to_merge_hours is not None]
        avg_time_to_merge = (
            sum(mr.time_to_merge_hours for mr in merged_mrs_with_time) / len(merged_mrs_with_time)
            if merged_mrs_with_time else 0
        )

        # Calculate median merge time
        from statistics import median
        median_time_to_merge = (
            median([mr.time_to_merge_hours for mr in merged_mrs_with_time])
            if merged_mrs_with_time else 0
        )

        # Calculate detailed review response time metrics (if enabled)
        if settings.enable_review_metrics and settings.fetch_comment_details:
            review_response_metrics = self._calculate_review_response_metrics(mrs)
        else:
            # Return empty metrics when disabled
            review_response_metrics = {
                "avg_hours": 0,
                "median_hours": 0,
                "by_project": {},
                "by_group": {},
                "sample_size": 0
            }

        result = {
            "total": total,
            "merged": merged,
            "open": open_mrs,
            "closed": closed,
            "stale": stale_count,
            "stale_threshold_days": settings.stale_mr_days,
            "avg_time_to_merge_hours": round(avg_time_to_merge, 2),
            "median_time_to_merge_hours": round(median_time_to_merge, 2),
            "review_metrics_enabled": settings.enable_review_metrics and settings.fetch_comment_details,
            "avg_review_response_hours": round(review_response_metrics["avg_hours"], 2),
            "median_review_response_hours": round(review_response_metrics["median_hours"], 2),
            "review_response_by_project": {
                k: round(v, 2) for k, v in review_response_metrics["by_project"].items()
            },
            "review_response_by_group": {
                k: round(v, 2) for k, v in review_response_metrics["by_group"].items()
            },
            "merge_requests": [
                {
                    "id": mr.id,
                    "project_name": mr.project_name,
                    "title": mr.title,
                    "author": mr.author,
                    "state": mr.state,
                    "created_at": mr.created_at.isoformat(),
                    "merged_at": mr.merged_at.isoformat() if mr.merged_at else None,
                    "time_to_merge_hours": mr.time_to_merge_hours,
                    "web_url": mr.web_url,
                }
                for mr in mrs
            ]
        }

        # Include ALL currently open MRs for stale detection (not just date-filtered ones)
        # This ensures the stale MRs table shows all open MRs needing attention
        all_open_query = self.db.query(MergeRequest).filter(MergeRequest.state == "opened")
        if group_id or self.group_id:
            filter_group = group_id or self.group_id
            all_open_query = all_open_query.filter(MergeRequest.group_id == filter_group)

        all_open_mrs = all_open_query.all()

        # Add any open MRs that aren't already in the date-filtered list
        existing_ids = {mr.id for mr in mrs}
        additional_open_mrs = [
            {
                "id": mr.id,
                "project_name": mr.project_name,
                "title": mr.title,
                "author": mr.author,
                "state": mr.state,
                "created_at": mr.created_at.isoformat(),
                "merged_at": None,
                "time_to_merge_hours": None,
                "web_url": mr.web_url,
            }
            for mr in all_open_mrs if mr.id not in existing_ids
        ]

        result["merge_requests"].extend(additional_open_mrs)

        # Recalculate stale count from the actual MRs we're returning
        # This ensures the count matches what the frontend will display
        try:
            stale_threshold_dt = datetime.utcnow() - timedelta(days=settings.stale_mr_days)
            actual_stale_count = 0
            stale_mrs_debug = []

            for mr_dict in result["merge_requests"]:
                if mr_dict["state"] == "opened":
                    # Parse the ISO format datetime string
                    created_at_str = mr_dict["created_at"]
                    # Handle both with and without timezone
                    if created_at_str.endswith('+00:00') or created_at_str.endswith('Z'):
                        created_at_str = created_at_str.replace('Z', '+00:00')
                        created_dt = datetime.fromisoformat(created_at_str).replace(tzinfo=None)
                    else:
                        created_dt = datetime.fromisoformat(created_at_str)

                    age_days = (datetime.utcnow() - created_dt).total_seconds() / 86400

                    # Frontend uses: ageInDays > staleThreshold
                    # Backend original used: created_at < (now - threshold)
                    # These should be equivalent, so let's match frontend exactly
                    if age_days > settings.stale_mr_days:
                        actual_stale_count += 1
                        if len(stale_mrs_debug) < 30:  # Log first 30
                            stale_mrs_debug.append({
                                'title': mr_dict['title'][:50],
                                'age_days': round(age_days, 2)
                            })

            total_mrs_returned = len(result["merge_requests"])
            total_open_mrs = len([mr for mr in result["merge_requests"] if mr["state"] == "opened"])

            logger.info(f"Stale MR count recalculation: old={stale_count}, new={actual_stale_count}, total_MRs_in_response={total_mrs_returned}, total_open={total_open_mrs}, threshold={settings.stale_mr_days}")

            if actual_stale_count != stale_count:
                logger.warning(f"Stale count mismatch! Old={stale_count}, New={actual_stale_count}")
                logger.warning(f"First 5 stale MRs: {stale_mrs_debug[:5]}")

            # Log ALL stale MR ages sorted
            all_stale_ages = sorted([
                round((datetime.utcnow() - datetime.fromisoformat(mr_dict['created_at'].replace('Z', '+00:00').replace('+00:00', ''))).total_seconds() / 86400, 3)
                for mr_dict in result["merge_requests"]
                if mr_dict["state"] == "opened"
                and (datetime.utcnow() - datetime.fromisoformat(mr_dict['created_at'].replace('Z', '+00:00').replace('+00:00', ''))).total_seconds() / 86400 > settings.stale_mr_days
            ], reverse=True)
            logger.info(f"All {len(all_stale_ages)} stale MR ages: {all_stale_ages}")

            # Find MRs at the boundary (13.5 to 14.5 days)
            boundary_mrs = [
                {'title': mr_dict['title'][:50], 'age': round((datetime.utcnow() - datetime.fromisoformat(mr_dict['created_at'].replace('Z', '+00:00').replace('+00:00', ''))).total_seconds() / 86400, 3)}
                for mr_dict in result["merge_requests"]
                if mr_dict["state"] == "opened"
                and 13.5 < (datetime.utcnow() - datetime.fromisoformat(mr_dict['created_at'].replace('Z', '+00:00').replace('+00:00', ''))).total_seconds() / 86400 < 14.5
            ]
            if boundary_mrs:
                logger.info(f"MRs near 14-day boundary: {boundary_mrs}")

            result["stale"] = actual_stale_count
        except Exception as e:
            logger.error(f"Error recalculating stale count: {e}", exc_info=True)
            # Fall back to original count on error
            result["stale"] = stale_count

        # Add group breakdown if viewing all groups
        if not (group_id or self.group_id):
            result["by_group"] = self._get_group_breakdown(self.db.query(MergeRequest).all())

        return result

    def _get_group_breakdown(self, mrs: List[MergeRequest]) -> Dict[str, Any]:
        """Calculate per-group metrics."""
        groups = {}
        for mr in mrs:
            gid = mr.group_id or "default"
            if gid not in groups:
                groups[gid] = {"total": 0, "merged": 0, "open": 0, "closed": 0}

            groups[gid]["total"] += 1
            if mr.state == "merged":
                groups[gid]["merged"] += 1
            elif mr.state == "opened":
                groups[gid]["open"] += 1
            elif mr.state == "closed":
                groups[gid]["closed"] += 1

        return groups

    def _calculate_avg_review_response_time(self, mrs: List[MergeRequest]) -> float:
        """Calculate average time from MR creation to first comment (backward compatibility)."""
        detailed = self._calculate_review_response_metrics(mrs)
        return detailed["avg_hours"]

    def _calculate_review_response_metrics(self, mrs: List[MergeRequest]) -> Dict[str, Any]:
        """Calculate detailed review response time metrics."""
        from app.models.schemas import Comment
        from statistics import median, quantiles

        response_times = []
        by_project = {}
        by_group = {}

        for mr in mrs:
            # Get first comment on this MR (match both IID and project_id to avoid cross-project collisions)
            first_comment = self.db.query(Comment).filter(
                Comment.mr_id == mr.iid,
                Comment.project_id == mr.project_id
            ).order_by(Comment.created_at.asc()).first()

            if first_comment and mr.created_at:
                # Calculate hours from MR creation to first comment
                time_diff = first_comment.created_at - mr.created_at
                hours = time_diff.total_seconds() / 3600

                # Skip negative values (indicates data inconsistency - comment before MR creation)
                if hours < 0:
                    continue

                response_times.append(hours)

                # Track by project
                project = mr.project_name or "Unknown"
                if project not in by_project:
                    by_project[project] = []
                by_project[project].append(hours)

                # Track by group
                group = mr.group_id or "default"
                if group not in by_group:
                    by_group[group] = []
                by_group[group].append(hours)

        # Calculate aggregated metrics
        # Use 90th percentile instead of mean to avoid outlier skew
        if len(response_times) >= 10:
            # Use 90th percentile for sufficient data
            sorted_times = sorted(response_times)
            p90_hours = quantiles(sorted_times, n=10)[8]  # 90th percentile (9th of 10 quantiles)
            median_hours = median(sorted_times)
        elif len(response_times) >= 2:
            # Use max for small samples (quantiles requires at least 2 points)
            sorted_times = sorted(response_times)
            p90_hours = max(sorted_times)
            median_hours = median(sorted_times)
        elif len(response_times) == 1:
            # Single data point
            p90_hours = response_times[0]
            median_hours = response_times[0]
        else:
            # No data
            p90_hours = 0
            median_hours = 0

        # Calculate 90th percentile by project
        project_p90 = {}
        for project, times in by_project.items():
            if len(times) >= 10:
                # Use 90th percentile for projects with enough data
                project_p90[project] = quantiles(sorted(times), n=10)[8]
            elif len(times) > 0:
                # Use max for small samples (approximation of upper bound)
                project_p90[project] = max(times)

        # Calculate 90th percentile by group
        group_p90 = {}
        for group, times in by_group.items():
            if len(times) >= 10:
                # Use 90th percentile for groups with enough data
                group_p90[group] = quantiles(sorted(times), n=10)[8]
            elif len(times) > 0:
                # Use max for small samples (approximation of upper bound)
                group_p90[group] = max(times)

        return {
            "avg_hours": p90_hours,  # Now using 90th percentile
            "median_hours": median_hours,
            "by_project": project_p90,
            "by_group": group_p90,
            "sample_size": len(response_times)
        }

    def get_commit_metrics(
        self,
        days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        """Get commit metrics - derived from contributor stats (hybrid approach)."""
        # In hybrid mode, we don't populate the commits table (too slow)
        # Instead, derive totals from contributor commit_counts

        if self.should_refresh_cache("contributors"):
            self.refresh_contributors(days=days)

        contributors = self.db.query(Contributor).all()

        # Aggregate from contributor stats
        total_commits = sum(c.commit_count for c in contributors)

        # Note: We don't have by_project or by_day breakdown without fetching individual commits
        # This is a trade-off for speed
        commits_by_project = {}
        commits_by_day = {}

        return {
            "total": total_commits,
            "by_project": commits_by_project,
            "by_day": commits_by_day,
            "recent_commits": []  # Not available in hybrid mode (would be too slow)
        }

    def get_comment_metrics(
        self,
        days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_id: Optional[str] = None
    ):
        """Get comment/review metrics, optionally filtered by group and date range."""
        from datetime import datetime

        # Query comments from the database with date range filter
        query = self.db.query(Comment)

        # Apply group filter if specified
        if group_id or self.group_id:
            filter_group = group_id or self.group_id
            query = query.filter(Comment.group_id == filter_group)

        # Apply date range filter
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(
                Comment.created_at >= start_dt,
                Comment.created_at <= end_dt
            )
        else:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Comment.created_at >= cutoff_date)

        comments = query.all()

        # Calculate total and aggregate by author
        total_comments = len(comments)

        comments_by_author = {}
        for comment in comments:
            if comment.author in comments_by_author:
                comments_by_author[comment.author] += 1
            else:
                comments_by_author[comment.author] = 1

        # Note: We don't have by_day breakdown for now
        comments_by_day = {}

        return {
            "total": total_comments,
            "by_author": comments_by_author,
            "by_day": comments_by_day,
            "recent_comments": []  # Could be added later if needed
        }

    def _get_contributor_metrics_from_mrs(
        self,
        days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_id: Optional[str] = None
    ):
        """Calculate contributor metrics dynamically from filtered MRs (for custom date ranges)."""
        from datetime import datetime
        from collections import defaultdict

        # Get filtered MRs for the date range
        query = self.db.query(MergeRequest)

        if group_id or self.group_id:
            filter_group = group_id or self.group_id
            query = query.filter(MergeRequest.group_id == filter_group)

        # Apply date range filter
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(
                MergeRequest.created_at >= start_dt,
                MergeRequest.created_at <= end_dt
            )
        else:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(MergeRequest.created_at >= cutoff_date)

        mrs = query.all()

        # Calculate contributor stats from filtered MRs
        contributor_stats = defaultdict(lambda: {
            "name": None,
            "username": None,
            "mr_count": 0,
            "commit_count": 0,  # We don't have per-MR commit counts
            "comment_count": 0,
            "last_activity": None
        })

        for mr in mrs:
            author = mr.author
            stats = contributor_stats[author]
            if stats["name"] is None:
                stats["name"] = author  # Use username as name if not available
                stats["username"] = author
            stats["mr_count"] += 1

            # Track most recent activity
            if mr.created_at:
                if stats["last_activity"] is None or mr.created_at > stats["last_activity"]:
                    stats["last_activity"] = mr.created_at

        # Query comment counts for contributors if comment details are available
        from app.models.schemas import Comment
        if settings.fetch_comment_details:
            # Get all comments in the filtered date range
            comment_query = self.db.query(Comment.author, func.count(Comment.id).label('count'))

            if group_id or self.group_id:
                filter_group = group_id or self.group_id
                comment_query = comment_query.filter(Comment.group_id == filter_group)

            if start_date and end_date:
                comment_query = comment_query.filter(
                    Comment.created_at >= start_dt,
                    Comment.created_at <= end_dt
                )
            else:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                comment_query = comment_query.filter(Comment.created_at >= cutoff_date)

            comment_counts = comment_query.group_by(Comment.author).all()

            # Add comment counts to contributor stats
            for author, count in comment_counts:
                if author in contributor_stats:
                    contributor_stats[author]["comment_count"] = count

        # Convert to list
        aggregated_contributors = list(contributor_stats.values())

        total_contributors = len(aggregated_contributors)
        total_mrs = sum(c["mr_count"] for c in aggregated_contributors)

        # Create a map by username for lookup
        contributor_map = {c["username"]: c for c in aggregated_contributors}

        # Return ALL team members, including those with 0 contributions
        # Use get_team_members_with_names() to get display names
        team_members = settings.get_team_members_with_names()
        all_contributors = []

        for member in team_members:
            username = member["username"]
            display_name = member["name"]

            if username in contributor_map:
                c = contributor_map[username]
                all_contributors.append({
                    "name": display_name,  # Use configured display name
                    "username": c["username"],
                    "commit_count": 0,  # Not available for date-filtered view
                    "mr_count": c["mr_count"],
                    "comment_count": c["comment_count"],
                    "last_activity": c["last_activity"].isoformat() if c["last_activity"] else None,
                })
            else:
                # Team member with no activity in this date range
                all_contributors.append({
                    "name": display_name,  # Use configured display name
                    "username": username,
                    "commit_count": 0,
                    "mr_count": 0,
                    "comment_count": 0,
                    "last_activity": None,
                })

        # Top contributors for chart (top 10 by MRs)
        top_10 = sorted(aggregated_contributors, key=lambda c: c["mr_count"], reverse=True)[:10]

        # Calculate total comments from all contributors
        total_comments = sum(c["comment_count"] for c in aggregated_contributors)

        return {
            "total_contributors": total_contributors,
            "total_commits": 0,  # Not available for date-filtered view
            "total_mrs": total_mrs,
            "total_comments": total_comments,
            "top_contributors": [
                {
                    "name": c["name"],
                    "username": c["username"],
                    "commit_count": 0,
                    "mr_count": c["mr_count"],
                    "comment_count": c["comment_count"],
                    "last_activity": c["last_activity"].isoformat() if c["last_activity"] else None,
                }
                for c in top_10
            ],
            "all_contributors": all_contributors
        }

    def get_contributor_metrics(
        self,
        days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_id: Optional[str] = None
    ):
        """Get contributor metrics, optionally filtered by group or custom date range."""
        from datetime import datetime

        # Always calculate stats from filtered MRs for accurate date-based filtering
        # (Contributor table only has aggregated totals, not per-period breakdowns)
        return self._get_contributor_metrics_from_mrs(
            days=days,
            start_date=start_date,
            end_date=end_date,
            group_id=group_id
        )

        # Aggregate contributors by username (sum across all groups)
        from collections import defaultdict
        aggregated = defaultdict(lambda: {
            "name": None,
            "username": None,
            "commit_count": 0,
            "mr_count": 0,
            "comment_count": 0,
            "last_activity": None
        })

        for c in contributors:
            agg = aggregated[c.username]
            if agg["name"] is None:
                agg["name"] = c.name
                agg["username"] = c.username
            agg["commit_count"] += c.commit_count
            agg["mr_count"] += c.mr_count
            agg["comment_count"] += c.comment_count
            # Keep the most recent activity
            if c.last_activity:
                if agg["last_activity"] is None or c.last_activity > agg["last_activity"]:
                    agg["last_activity"] = c.last_activity

        # Convert to list
        aggregated_contributors = list(aggregated.values())

        total_contributors = len(aggregated_contributors)
        total_commits = sum(c["commit_count"] for c in aggregated_contributors)
        total_mrs = sum(c["mr_count"] for c in aggregated_contributors)
        total_comments = sum(c["comment_count"] for c in aggregated_contributors)

        # Create a map by username for lookup
        contributor_map = {c["username"]: c for c in aggregated_contributors}

        # Return ALL team members, including those with 0 contributions
        team_members = settings.get_team_members_with_names()
        all_contributors = []

        for member in team_members:
            username = member["username"]
            display_name = member["name"]

            if username in contributor_map:
                # Existing contributor with data
                c = contributor_map[username]
                all_contributors.append({
                    "name": display_name,  # Use configured display name
                    "username": c["username"],
                    "commit_count": c["commit_count"],
                    "mr_count": c["mr_count"],
                    "comment_count": c["comment_count"],
                    "last_activity": c["last_activity"].isoformat() if c["last_activity"] else None,
                })
            else:
                # Team member with no activity
                all_contributors.append({
                    "name": display_name,  # Use configured display name
                    "username": username,
                    "commit_count": 0,
                    "mr_count": 0,
                    "comment_count": 0,
                    "last_activity": None,
                })

        # Keep top_contributors for the chart (top 10 by MRs) - use aggregated data
        top_10_for_chart = sorted(aggregated_contributors, key=lambda c: c["mr_count"], reverse=True)[:10]

        return {
            "total_contributors": total_contributors,
            "total_commits": total_commits,
            "total_mrs": total_mrs,
            "total_comments": total_comments,
            "top_contributors": [
                {
                    "name": c["name"],
                    "username": c["username"],
                    "commit_count": c["commit_count"],
                    "mr_count": c["mr_count"],
                    "comment_count": c["comment_count"],
                    "last_activity": c["last_activity"].isoformat() if c["last_activity"] else None,
                }
                for c in top_10_for_chart
            ],
            "all_contributors": all_contributors
        }
