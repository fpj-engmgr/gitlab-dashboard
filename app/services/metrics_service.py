from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from app.models.schemas import MergeRequest, Commit, Comment, Contributor, CacheMetadata
from app.services.gitlab_client import GitLabClient
from app.services.multi_group_client import MultiGroupGitLabClient
from app.config import settings


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

    def get_merge_request_metrics(self, days: int = 30, group_id: Optional[str] = None):
        """Get merge request metrics, optionally filtered by group."""
        if self.should_refresh_cache("merge_requests"):
            self.refresh_merge_requests(days=days)

        # Build query with optional group filter
        query = self.db.query(MergeRequest)
        if group_id or self.group_id:
            filter_group = group_id or self.group_id
            query = query.filter(MergeRequest.group_id == filter_group)

        mrs = query.all()

        total = len(mrs)
        merged = len([mr for mr in mrs if mr.state == "merged"])
        open_mrs = len([mr for mr in mrs if mr.state == "opened"])
        closed = len([mr for mr in mrs if mr.state == "closed"])

        merged_mrs_with_time = [mr for mr in mrs if mr.time_to_merge_hours is not None]
        avg_time_to_merge = (
            sum(mr.time_to_merge_hours for mr in merged_mrs_with_time) / len(merged_mrs_with_time)
            if merged_mrs_with_time else 0
        )

        # Calculate detailed review response time metrics
        review_response_metrics = self._calculate_review_response_metrics(mrs)

        result = {
            "total": total,
            "merged": merged,
            "open": open_mrs,
            "closed": closed,
            "avg_time_to_merge_hours": round(avg_time_to_merge, 2),
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
        from statistics import median

        response_times = []
        by_project = {}
        by_group = {}

        for mr in mrs:
            # Get first comment on this MR (match GitLab IID, not auto-increment id)
            first_comment = self.db.query(Comment).filter(
                Comment.mr_id == mr.iid
            ).order_by(Comment.created_at.asc()).first()

            if first_comment and mr.created_at:
                # Calculate hours from MR creation to first comment
                time_diff = first_comment.created_at - mr.created_at
                hours = time_diff.total_seconds() / 3600

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
        avg_hours = sum(response_times) / len(response_times) if response_times else 0
        median_hours = median(response_times) if response_times else 0

        # Calculate averages by project
        project_avgs = {
            project: sum(times) / len(times)
            for project, times in by_project.items()
        }

        # Calculate averages by group
        group_avgs = {
            group: sum(times) / len(times)
            for group, times in by_group.items()
        }

        return {
            "avg_hours": avg_hours,
            "median_hours": median_hours,
            "by_project": project_avgs,
            "by_group": group_avgs,
            "sample_size": len(response_times)
        }

    def get_commit_metrics(self, days: int = 30):
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

    def get_comment_metrics(self, days: int = 30, group_id: Optional[str] = None):
        """Get comment/review metrics, optionally filtered by group."""
        # In hybrid mode, we don't populate the comments table (too slow)
        # Instead, derive totals from contributor comment_counts

        if self.should_refresh_cache("contributors"):
            self.refresh_contributors(days=days)

        # Build query with optional group filter
        query = self.db.query(Contributor)
        if group_id or self.group_id:
            filter_group = group_id or self.group_id
            query = query.filter(Contributor.group_id == filter_group)

        contributors = query.all()

        # Aggregate from contributor stats
        total_comments = sum(c.comment_count for c in contributors)

        comments_by_author = {
            c.username: c.comment_count
            for c in contributors
            if c.comment_count > 0
        }

        # Note: We don't have by_day breakdown without fetching individual comments
        # This is a trade-off for speed
        comments_by_day = {}

        return {
            "total": total_comments,
            "by_author": comments_by_author,
            "by_day": comments_by_day,
            "recent_comments": []  # Not available in hybrid mode (would be too slow)
        }

    def get_contributor_metrics(self, days: int = 30, group_id: Optional[str] = None):
        """Get contributor metrics, optionally filtered by group."""
        if self.should_refresh_cache("contributors"):
            self.refresh_contributors(days=days)

        # Build query with optional group filter
        query = self.db.query(Contributor)
        if group_id or self.group_id:
            filter_group = group_id or self.group_id
            query = query.filter(Contributor.group_id == filter_group)

        contributors = query.all()

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
        team_members = settings.get_team_members()
        all_contributors = []

        for username in team_members:
            if username in contributor_map:
                # Existing contributor with data
                c = contributor_map[username]
                all_contributors.append({
                    "name": c["name"],
                    "username": c["username"],
                    "commit_count": c["commit_count"],
                    "mr_count": c["mr_count"],
                    "comment_count": c["comment_count"],
                    "last_activity": c["last_activity"].isoformat() if c["last_activity"] else None,
                })
            else:
                # Team member with no activity
                all_contributors.append({
                    "name": username,
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
