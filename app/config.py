from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Dict, Any
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str
    gitlab_group: str = "redhat/rhel-ai"
    database_url: str = "sqlite:///./gitlab_metrics.db"
    cache_duration_hours: int = 6
    team_members_file: str = "team_members.json"
    groups_file: str = "groups.json"  # Multi-group configuration
    max_parallel_requests: int = 10  # Limit concurrent API requests
    fetch_commit_details: bool = False  # Set True to fetch individual commit details (slower)
    fetch_comment_details: bool = False  # Set True to fetch MR comments (slower)

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    def get_team_members(self) -> List[str]:
        """Load team member usernames from JSON file. Required for dashboard operation."""
        team_file = Path(self.team_members_file)
        if not team_file.exists():
            raise FileNotFoundError(
                f"Team members file '{self.team_members_file}' not found. "
                f"Create it from team_members.json.example with your team's GitLab usernames."
            )

        try:
            with open(team_file, 'r') as f:
                data = json.load(f)
                members = data.get('team_members', [])

                if not members:
                    raise ValueError(
                        f"No team members found in {self.team_members_file}. "
                        f"Add GitLab usernames to the 'team_members' array."
                    )

                return members
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {self.team_members_file}: {e}")

    def get_groups(self) -> List[Dict[str, Any]]:
        """Load group configurations from groups.json or fall back to single group from env."""
        groups_file = Path(self.groups_file)

        # If groups.json doesn't exist, use legacy single-group mode
        if not groups_file.exists():
            logger.info(f"No {self.groups_file} found - using single-group mode from GITLAB_GROUP env var")
            return [{
                "id": "default",
                "name": self.gitlab_group.split('/')[-1].title(),
                "path": self.gitlab_group,
                "description": "Default group",
                "enabled": True
            }]

        try:
            with open(groups_file, 'r') as f:
                data = json.load(f)
                groups = data.get('groups', [])

                if not groups:
                    logger.warning(f"No groups defined in {self.groups_file} - falling back to env var")
                    return self._get_default_group_config()

                # Validate group structure
                for group in groups:
                    required = ['id', 'name', 'path']
                    if not all(k in group for k in required):
                        raise ValueError(f"Group missing required fields {required}: {group}")

                logger.info(f"Loaded {len(groups)} groups from {self.groups_file}")
                return groups

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {self.groups_file}: {e}")

    def _get_default_group_config(self) -> List[Dict[str, Any]]:
        """Generate single-group config from GITLAB_GROUP env var."""
        return [{
            "id": "default",
            "name": self.gitlab_group.split('/')[-1].title(),
            "path": self.gitlab_group,
            "description": "Default group from GITLAB_GROUP env var",
            "enabled": True
        }]


settings = Settings()
