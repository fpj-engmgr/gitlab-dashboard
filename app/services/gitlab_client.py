import gitlab
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.config import settings


class GitLabClient:
    def __init__(self):
        self.gl = gitlab.Gitlab(settings.gitlab_url, private_token=settings.gitlab_token)
        self.group_path = settings.gitlab_group
        self.team_members = settings.get_team_members()

    def is_team_member(self, username: str) -> bool:
        """Check if a username is in the team members list. Returns True if no filter is set."""
        if self.team_members is None:
            return True
        return username in self.team_members

    def get_group(self):
        """Get the GitLab group."""
        return self.gl.groups.get(self.group_path)

    def get_all_projects(self) -> List[Any]:
        """Get all projects under the group tree."""
        group = self.get_group()
        projects = group.projects.list(include_subgroups=True, get_all=True)
        return projects

    def get_merge_requests(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch merge requests from all projects in the group."""
        projects = self.get_all_projects()
        all_mrs = []

        since = datetime.utcnow() - timedelta(days=days)

        for project in projects:
            try:
                full_project = self.gl.projects.get(project.id)
                mrs = full_project.mergerequests.list(
                    updated_after=since.isoformat(),
                    get_all=True
                )

                for mr in mrs:
                    author_username = mr.author.get('username', 'unknown')

                    if not self.is_team_member(author_username):
                        continue

                    mr_data = {
                        'project_id': project.id,
                        'project_name': project.name,
                        'iid': mr.iid,
                        'title': mr.title,
                        'state': mr.state,
                        'author': author_username,
                        'created_at': datetime.fromisoformat(mr.created_at.replace('Z', '+00:00')),
                        'updated_at': datetime.fromisoformat(mr.updated_at.replace('Z', '+00:00')),
                        'merged_at': datetime.fromisoformat(mr.merged_at.replace('Z', '+00:00')) if mr.merged_at else None,
                        'closed_at': datetime.fromisoformat(mr.closed_at.replace('Z', '+00:00')) if mr.closed_at else None,
                        'source_branch': mr.source_branch,
                        'target_branch': mr.target_branch,
                        'web_url': mr.web_url,
                    }

                    if mr_data['merged_at'] and mr_data['created_at']:
                        time_diff = mr_data['merged_at'] - mr_data['created_at']
                        mr_data['time_to_merge_hours'] = time_diff.total_seconds() / 3600
                    else:
                        mr_data['time_to_merge_hours'] = None

                    all_mrs.append(mr_data)
            except Exception as e:
                print(f"Error fetching MRs for project {project.name}: {e}")
                continue

        return all_mrs

    def get_commits(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch commits from all projects in the group."""
        projects = self.get_all_projects()
        all_commits = []

        since = datetime.utcnow() - timedelta(days=days)

        for project in projects:
            try:
                full_project = self.gl.projects.get(project.id)
                commits = full_project.commits.list(
                    since=since.isoformat(),
                    get_all=True
                )

                for commit in commits:
                    commit_data = {
                        'id': commit.id,
                        'project_id': project.id,
                        'project_name': project.name,
                        'author_name': commit.author_name,
                        'author_email': commit.author_email,
                        'committed_date': datetime.fromisoformat(commit.committed_date.replace('Z', '+00:00')),
                        'title': commit.title,
                        'message': commit.message,
                        'web_url': commit.web_url,
                    }
                    all_commits.append(commit_data)
            except Exception as e:
                print(f"Error fetching commits for project {project.name}: {e}")
                continue

        return all_commits

    def get_contributor_stats(self, commits: List[Dict[str, Any]], mrs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate contributor statistics from commits and MRs."""
        contributors = {}
        username_to_email = {}

        for commit in commits:
            email = commit['author_email']
            username = commit['author_email'].split('@')[0]

            if not self.is_team_member(username):
                continue

            if email not in contributors:
                contributors[email] = {
                    'username': username,
                    'name': commit['author_name'],
                    'email': email,
                    'commit_count': 0,
                    'mr_count': 0,
                    'last_activity': commit['committed_date']
                }
                username_to_email[username] = email

            contributors[email]['commit_count'] += 1
            if commit['committed_date'] > contributors[email]['last_activity']:
                contributors[email]['last_activity'] = commit['committed_date']

        for mr in mrs:
            author = mr['author']
            if author in username_to_email:
                email = username_to_email[author]
                contributors[email]['mr_count'] += 1

        return list(contributors.values())
