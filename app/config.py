from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import json
from pathlib import Path


class Settings(BaseSettings):
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str
    gitlab_group: str = "redhat/rhel-ai"
    database_url: str = "sqlite:///./gitlab_metrics.db"
    cache_duration_hours: int = 6
    team_members_file: str = "team_members.json"
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


settings = Settings()
