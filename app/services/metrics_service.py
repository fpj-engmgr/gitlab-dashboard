from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.schemas import MergeRequest, Commit, Comment, Contributor, CacheMetadata
from app.services.gitlab_client import GitLabClient
from app.config import settings


class MetricsService:
    def __init__(self, db: Session):
        self.db = db
        self.gitlab_client = GitLabClient()

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
        mrs_data = self.gitlab_client.get_merge_requests(days=days)

        self.db.query(MergeRequest).delete()

        for mr_data in mrs_data:
            mr = MergeRequest(**mr_data)
            self.db.add(mr)

        self.db.commit()
        self.update_cache_metadata("merge_requests")

    def refresh_commits(self, days: int = 30):
        """Refresh commits cache."""
        commits_data = self.gitlab_client.get_commits(days=days)

        self.db.query(Commit).delete()

        for commit_data in commits_data:
            commit = Commit(**commit_data)
            self.db.add(commit)

        self.db.commit()
        self.update_cache_metadata("commits")

    def refresh_comments(self, days: int = 30):
        """Refresh comments cache."""
        comments_data = self.gitlab_client.get_comments(days=days)

        self.db.query(Comment).delete()

        for comment_data in comments_data:
            comment = Comment(**comment_data)
            self.db.add(comment)

        self.db.commit()
        self.update_cache_metadata("comments")

    def refresh_contributors(self, days: int = 30):
        """Refresh contributors cache."""
        commits_data = self.gitlab_client.get_commits(days=days)
        mrs_data = self.gitlab_client.get_merge_requests(days=days)
        comments_data = self.gitlab_client.get_comments(days=days)

        contributors_data = self.gitlab_client.get_contributor_stats(commits_data, mrs_data, comments_data)

        self.db.query(Contributor).delete()

        for contrib_data in contributors_data:
            contributor = Contributor(**contrib_data)
            self.db.add(contributor)

        self.db.commit()
        self.update_cache_metadata("contributors")

    def get_merge_request_metrics(self, days: int = 30):
        """Get merge request metrics from cache or refresh if needed."""
        if self.should_refresh_cache("merge_requests"):
            self.refresh_merge_requests(days=days)

        mrs = self.db.query(MergeRequest).all()

        total = len(mrs)
        merged = len([mr for mr in mrs if mr.state == "merged"])
        open_mrs = len([mr for mr in mrs if mr.state == "opened"])
        closed = len([mr for mr in mrs if mr.state == "closed"])

        merged_mrs_with_time = [mr for mr in mrs if mr.time_to_merge_hours is not None]
        avg_time_to_merge = (
            sum(mr.time_to_merge_hours for mr in merged_mrs_with_time) / len(merged_mrs_with_time)
            if merged_mrs_with_time else 0
        )

        return {
            "total": total,
            "merged": merged,
            "open": open_mrs,
            "closed": closed,
            "avg_time_to_merge_hours": round(avg_time_to_merge, 2),
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

    def get_commit_metrics(self, days: int = 30):
        """Get commit metrics from cache or refresh if needed."""
        if self.should_refresh_cache("commits"):
            self.refresh_commits(days=days)

        commits = self.db.query(Commit).all()

        total_commits = len(commits)

        commits_by_project = {}
        for commit in commits:
            if commit.project_name not in commits_by_project:
                commits_by_project[commit.project_name] = 0
            commits_by_project[commit.project_name] += 1

        commits_by_day = {}
        for commit in commits:
            day = commit.committed_date.date().isoformat()
            if day not in commits_by_day:
                commits_by_day[day] = 0
            commits_by_day[day] += 1

        return {
            "total": total_commits,
            "by_project": commits_by_project,
            "by_day": commits_by_day,
            "recent_commits": [
                {
                    "id": commit.id,
                    "project_name": commit.project_name,
                    "author_name": commit.author_name,
                    "title": commit.title,
                    "committed_date": commit.committed_date.isoformat(),
                    "web_url": commit.web_url,
                }
                for commit in sorted(commits, key=lambda c: c.committed_date, reverse=True)[:20]
            ]
        }

    def get_comment_metrics(self, days: int = 30):
        """Get comment/review metrics from cache or refresh if needed."""
        if self.should_refresh_cache("comments"):
            self.refresh_comments(days=days)

        comments = self.db.query(Comment).all()

        total_comments = len(comments)

        comments_by_author = {}
        for comment in comments:
            if comment.author not in comments_by_author:
                comments_by_author[comment.author] = 0
            comments_by_author[comment.author] += 1

        comments_by_day = {}
        for comment in comments:
            day = comment.created_at.date().isoformat()
            if day not in comments_by_day:
                comments_by_day[day] = 0
            comments_by_day[day] += 1

        return {
            "total": total_comments,
            "by_author": comments_by_author,
            "by_day": comments_by_day,
            "recent_comments": [
                {
                    "author": comment.author,
                    "mr_title": comment.mr_title,
                    "body": comment.body[:200],  # Truncate long comments
                    "created_at": comment.created_at.isoformat(),
                    "web_url": comment.web_url,
                }
                for comment in sorted(comments, key=lambda c: c.created_at, reverse=True)[:20]
            ]
        }

    def get_contributor_metrics(self, days: int = 30):
        """Get contributor metrics from cache or refresh if needed."""
        if self.should_refresh_cache("contributors"):
            self.refresh_contributors(days=days)

        contributors = self.db.query(Contributor).all()

        total_contributors = len(contributors)
        total_commits = sum(c.commit_count for c in contributors)
        total_mrs = sum(c.mr_count for c in contributors)
        total_comments = sum(c.comment_count for c in contributors)

        top_contributors = sorted(contributors, key=lambda c: c.commit_count, reverse=True)[:10]

        return {
            "total_contributors": total_contributors,
            "total_commits": total_commits,
            "total_mrs": total_mrs,
            "total_comments": total_comments,
            "top_contributors": [
                {
                    "name": c.name,
                    "username": c.username,
                    "commit_count": c.commit_count,
                    "mr_count": c.mr_count,
                    "comment_count": c.comment_count,
                    "last_activity": c.last_activity.isoformat() if c.last_activity else None,
                }
                for c in top_contributors
            ]
        }
