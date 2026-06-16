import gitlab
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class GitLabClient:
    def __init__(self):
        self.gl = gitlab.Gitlab(settings.gitlab_url, private_token=settings.gitlab_token)
        self.group_path = settings.gitlab_group
        self.team_members = settings.get_team_members()
        logger.info(f"Initialized GitLab client for group: {self.group_path}")
        logger.info(f"Tracking {len(self.team_members)} team members: {', '.join(self.team_members)}")

    def get_group(self):
        """Get the GitLab group."""
        return self.gl.groups.get(self.group_path)

    def get_merge_requests_for_member(self, username: str, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch merge requests authored by a specific team member."""
        group = self.get_group()
        mrs = []

        since = datetime.utcnow() - timedelta(days=days)

        try:
            # Query group-level MRs filtered by author
            group_mrs = group.mergerequests.list(
                author_username=username,
                updated_after=since.isoformat(),
                get_all=True
            )

            logger.info(f"Found {len(group_mrs)} MRs for {username}")

            for mr in group_mrs:
                try:
                    mr_data = {
                        'project_id': mr.project_id,
                        'project_name': getattr(mr, 'references', {}).get('full', 'unknown').split('!')[0],
                        'iid': mr.iid,
                        'title': mr.title,
                        'state': mr.state,
                        'author': username,
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

                    mrs.append(mr_data)
                except Exception as e:
                    logger.warning(f"Error processing MR {mr.iid} for {username}: {e}")
                    continue

        except gitlab.exceptions.GitlabAuthenticationError as e:
            logger.error(f"Authentication error fetching MRs for {username}: {e}")
        except gitlab.exceptions.GitlabGetError as e:
            logger.error(f"Error fetching MRs for {username}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching MRs for {username}: {e}")

        return mrs

    def get_merge_requests(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch ALL merge requests in one pass, then filter to team members."""
        all_mrs = []

        since = datetime.utcnow() - timedelta(days=days)
        team_members_set = set(self.team_members)

        try:
            group = self.get_group()

            # Single API call to get ALL MRs in the group
            logger.info(f"Fetching all MRs from group {self.group_path} (single pass)")
            group_mrs = group.mergerequests.list(
                updated_after=since.isoformat(),
                get_all=True
            )

            logger.info(f"Fetched {len(group_mrs)} total MRs, filtering to team members")

            # Filter to team members
            for mr in group_mrs:
                try:
                    author = mr.author.get('username', 'unknown')

                    # Skip if not a team member
                    if author not in team_members_set:
                        continue

                    mr_data = {
                        'project_id': mr.project_id,
                        'project_name': getattr(mr, 'references', {}).get('full', 'unknown').split('!')[0],
                        'iid': mr.iid,
                        'title': mr.title,
                        'state': mr.state,
                        'author': author,
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
                    logger.warning(f"Error processing MR {mr.iid}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching MRs: {e}")

        logger.info(f"Found {len(all_mrs)} MRs from {len(team_members_set)} team members")
        return all_mrs

    def get_commits_for_member(self, username: str, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch commits using user events API filtered by date range, then filter to our group."""
        all_commits = {}  # Use dict to deduplicate by commit ID

        since = datetime.utcnow() - timedelta(days=days)

        try:
            # Get the user object
            users = self.gl.users.list(username=username)
            if not users:
                logger.warning(f"User {username} not found")
                return []

            user = users[0]

            # Fetch user events filtered by date range using 'after' parameter
            # This is efficient - GitLab filters server-side
            events = self.gl.users.get(user.id).events.list(
                after=since.date().isoformat(),
                get_all=True
            )

            logger.info(f"Fetched {len(events)} events for {username} since {since.date()}")

            # Filter to push events within our group
            for event in events:
                # Only process push events
                if event.action_name != 'pushed to':
                    continue

                try:
                    # Get push event details
                    push_data = event.push_data
                    if not push_data:
                        continue

                    project_id = event.project_id
                    commit_to = push_data.get('commit_to')

                    if not commit_to:
                        continue

                    # Fetch the project to check if it's in our group
                    project = self.gl.projects.get(project_id)

                    # Filter to projects within our group
                    if not project.path_with_namespace.startswith(self.group_path):
                        continue

                    # Fetch the actual commit
                    commit = project.commits.get(commit_to)
                    commit_date = datetime.fromisoformat(commit.committed_date.replace('Z', '+00:00'))

                    # Double-check date is within range (events API might return slightly outside)
                    if commit_date < since:
                        continue

                    commit_data = {
                        'id': commit.id,
                        'project_id': project_id,
                        'project_name': project.name,
                        'author_name': commit.author_name,
                        'author_email': commit.author_email,
                        'committed_date': commit_date,
                        'title': commit.title,
                        'message': commit.message,
                        'web_url': commit.web_url,
                    }
                    all_commits[commit.id] = commit_data

                except gitlab.exceptions.GitlabGetError as e:
                    if e.response_code == 403:
                        continue
                    logger.debug(f"Error fetching commit details: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Error processing push event: {e}")
                    continue

            logger.info(f"Found {len(all_commits)} commits for {username} in group {self.group_path}")

        except Exception as e:
            logger.error(f"Unexpected error fetching commits for {username}: {e}")

        return list(all_commits.values())

    def get_commits(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch commits for all team members in a single optimized pass."""
        all_commits = {}  # Use dict to deduplicate by commit ID

        since = datetime.utcnow() - timedelta(days=days)
        team_members_set = set(self.team_members)

        logger.info(f"Fetching commits for {len(self.team_members)} team members (optimized single pass)")

        # Strategy: Fetch events for each user, but batch the processing
        # Unfortunately GitLab doesn't have a multi-user events endpoint,
        # but we can optimize by processing events more efficiently

        for username in self.team_members:
            try:
                # Get the user object
                users = self.gl.users.list(username=username)
                if not users:
                    logger.debug(f"User {username} not found")
                    continue

                user = users[0]

                # Fetch user events filtered by date range using 'after' parameter
                events = self.gl.users.get(user.id).events.list(
                    after=since.date().isoformat(),
                    get_all=True
                )

                # Filter to push events within our group
                for event in events:
                    if event.action_name != 'pushed to':
                        continue

                    try:
                        push_data = event.push_data
                        if not push_data:
                            continue

                        project_id = event.project_id
                        commit_to = push_data.get('commit_to')

                        if not commit_to or commit_to in all_commits:
                            continue

                        # Fetch the project to check if it's in our group
                        project = self.gl.projects.get(project_id)

                        # Filter to projects within our group
                        if not project.path_with_namespace.startswith(self.group_path):
                            continue

                        # Fetch the actual commit
                        commit = project.commits.get(commit_to)
                        commit_date = datetime.fromisoformat(commit.committed_date.replace('Z', '+00:00'))

                        if commit_date < since:
                            continue

                        commit_data = {
                            'id': commit.id,
                            'project_id': project_id,
                            'project_name': project.name,
                            'author_name': commit.author_name,
                            'author_email': commit.author_email,
                            'committed_date': commit_date,
                            'title': commit.title,
                            'message': commit.message,
                            'web_url': commit.web_url,
                        }
                        all_commits[commit.id] = commit_data

                    except gitlab.exceptions.GitlabGetError as e:
                        if e.response_code == 403:
                            continue
                        logger.debug(f"Error fetching commit details: {e}")
                        continue
                    except Exception as e:
                        logger.debug(f"Error processing push event: {e}")
                        continue

            except Exception as e:
                logger.debug(f"Error fetching commits for {username}: {e}")
                continue

        logger.info(f"Found {len(all_commits)} unique commits across all team members")
        return list(all_commits.values())

    def get_comments_for_member(self, username: str, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch MR comments/notes authored by a specific team member."""
        all_comments = []

        since = datetime.utcnow() - timedelta(days=days)

        try:
            group = self.get_group()

            # Get all MRs in the group (not just the member's MRs, since they may comment on others' MRs)
            group_mrs = group.mergerequests.list(
                updated_after=since.isoformat(),
                get_all=True
            )

            logger.info(f"Scanning {len(group_mrs)} MRs for {username}'s comments")

            for mr in group_mrs:
                try:
                    # Get the full project to access MR notes
                    project = self.gl.projects.get(mr.project_id)
                    full_mr = project.mergerequests.get(mr.iid)

                    # Get all notes/comments on this MR
                    notes = full_mr.notes.list(get_all=True)

                    for note in notes:
                        # Filter to comments by this team member
                        if note.author.get('username') == username:
                            # Skip system notes (like "changed the title")
                            if note.system:
                                continue

                            comment_data = {
                                'note_id': note.id,
                                'mr_id': mr.id,
                                'project_id': mr.project_id,
                                'project_name': getattr(mr, 'references', {}).get('full', 'unknown').split('!')[0],
                                'author': username,
                                'body': note.body,
                                'created_at': datetime.fromisoformat(note.created_at.replace('Z', '+00:00')),
                                'updated_at': datetime.fromisoformat(note.updated_at.replace('Z', '+00:00')),
                                'mr_title': mr.title,
                                'web_url': note.noteable_iid and f"{project.web_url}/-/merge_requests/{mr.iid}#note_{note.id}" or mr.web_url,
                            }
                            all_comments.append(comment_data)

                except gitlab.exceptions.GitlabGetError as e:
                    if e.response_code == 403:
                        continue  # Skip inaccessible projects
                    logger.debug(f"Error accessing MR notes: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Error processing MR {mr.iid}: {e}")
                    continue

            logger.info(f"Found {len(all_comments)} comments for {username}")

        except Exception as e:
            logger.error(f"Unexpected error fetching comments for {username}: {e}")

        return all_comments

    def get_comments(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch comments for all team members in a single pass through MRs."""
        all_comments = []

        since = datetime.utcnow() - timedelta(days=days)
        team_members_set = set(self.team_members)

        try:
            group = self.get_group()

            # Single API call to get all MRs
            logger.info(f"Fetching all MRs to scan for team member comments (single pass)")
            group_mrs = group.mergerequests.list(
                updated_after=since.isoformat(),
                get_all=True
            )

            logger.info(f"Scanning {len(group_mrs)} MRs for comments from {len(self.team_members)} team members")

            for mr in group_mrs:
                try:
                    # Get the full project to access MR notes
                    project = self.gl.projects.get(mr.project_id)
                    full_mr = project.mergerequests.get(mr.iid)

                    # Get all notes/comments on this MR
                    notes = full_mr.notes.list(get_all=True)

                    for note in notes:
                        # Filter to comments by team members
                        author = note.author.get('username')
                        if author not in team_members_set:
                            continue

                        # Skip system notes (like "changed the title")
                        if note.system:
                            continue

                        comment_data = {
                            'note_id': note.id,
                            'mr_id': mr.id,
                            'project_id': mr.project_id,
                            'project_name': getattr(mr, 'references', {}).get('full', 'unknown').split('!')[0],
                            'author': author,
                            'body': note.body,
                            'created_at': datetime.fromisoformat(note.created_at.replace('Z', '+00:00')),
                            'updated_at': datetime.fromisoformat(note.updated_at.replace('Z', '+00:00')),
                            'mr_title': mr.title,
                            'web_url': f"{project.web_url}/-/merge_requests/{mr.iid}#note_{note.id}",
                        }
                        all_comments.append(comment_data)

                except gitlab.exceptions.GitlabGetError as e:
                    if e.response_code == 403:
                        continue  # Skip inaccessible projects
                    logger.debug(f"Error accessing MR notes: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Error processing MR {mr.iid}: {e}")
                    continue

            logger.info(f"Found {len(all_comments)} total comments from team members")

        except Exception as e:
            logger.error(f"Unexpected error fetching comments: {e}")

        return all_comments

    def get_contributor_stats(self, commits: List[Dict[str, Any]], mrs: List[Dict[str, Any]], comments: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Calculate contributor statistics from commits, MRs, and comments."""
        contributors = {}
        if comments is None:
            comments = []

        # Process commits
        for commit in commits:
            email = commit['author_email']
            username = commit['author_email'].split('@')[0]

            if email not in contributors:
                contributors[email] = {
                    'username': username,
                    'name': commit['author_name'],
                    'email': email,
                    'commit_count': 0,
                    'mr_count': 0,
                    'comment_count': 0,
                    'last_activity': commit['committed_date']
                }

            contributors[email]['commit_count'] += 1
            if commit['committed_date'] > contributors[email]['last_activity']:
                contributors[email]['last_activity'] = commit['committed_date']

        # Process MRs
        for mr in mrs:
            author = mr['author']
            # Find matching contributor by username
            for email, contrib in contributors.items():
                if contrib['username'] == author or email.startswith(author + '@'):
                    contrib['mr_count'] += 1
                    break
            else:
                # MR author not in commits, create entry
                contributors[f"{author}@unknown"] = {
                    'username': author,
                    'name': author,
                    'email': f"{author}@unknown",
                    'commit_count': 0,
                    'mr_count': 1,
                    'comment_count': 0,
                    'last_activity': mr['updated_at']
                }

        # Process comments
        for comment in comments:
            author = comment['author']
            # Find matching contributor by username
            for email, contrib in contributors.items():
                if contrib['username'] == author or email.startswith(author + '@'):
                    contrib['comment_count'] += 1
                    if comment['created_at'] > contrib['last_activity']:
                        contrib['last_activity'] = comment['created_at']
                    break
            else:
                # Comment author not in commits/MRs, create entry
                contributors[f"{author}@unknown"] = {
                    'username': author,
                    'name': author,
                    'email': f"{author}@unknown",
                    'commit_count': 0,
                    'mr_count': 0,
                    'comment_count': 1,
                    'last_activity': comment['created_at']
                }

        return list(contributors.values())
