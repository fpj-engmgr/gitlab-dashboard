from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import json
from pathlib import Path


class Settings(BaseSettings):
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str
    gitlab_group: str = "redhat/rhel-ai"
    database_url: str = "sqlite:///./gitlab_metrics.db"
    cache_duration_hours: int = 1
    team_members_file: str = "team_members.json"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    def get_team_members(self) -> Optional[List[str]]:
        """Load team member usernames from JSON file. Returns None if file doesn't exist (no filtering)."""
        team_file = Path(self.team_members_file)
        if not team_file.exists():
            return None

        try:
            with open(team_file, 'r') as f:
                data = json.load(f)
                return data.get('team_members', [])
        except (json.JSONDecodeError, KeyError):
            return None


settings = Settings()
