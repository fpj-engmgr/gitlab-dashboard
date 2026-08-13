#!/usr/bin/env python3
"""
Setup verification script for gitlab-dashboard.
Checks environment, authentication, API access, and database connectivity.

Usage:
    python scripts/test_setup.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import json
import requests

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

PASS = f"{GREEN}✓{RESET}"
FAIL = f"{RED}✗{RESET}"
WARN = f"{YELLOW}!{RESET}"


def section(title):
    print(f"\n{BOLD}{'=' * 50}")
    print(f" {title}")
    print(f"{'=' * 50}{RESET}")


def check_env_file():
    section("1. Environment & Configuration")
    ok = True

    env_path = Path(".env")
    if env_path.exists():
        print(f"  {PASS} .env file found")
    else:
        print(f"  {FAIL} .env file not found — copy .env.example to .env and configure it")
        return False

    try:
        from app.config import settings
        print(f"  {PASS} Settings loaded successfully")
    except Exception as e:
        print(f"  {FAIL} Failed to load settings: {e}")
        return False

    if settings.gitlab_token in ("your-gitlab-personal-access-token-here", ""):
        print(f"  {FAIL} GITLAB_TOKEN is not set — add your GitLab personal access token to .env")
        ok = False
    else:
        masked = settings.gitlab_token[:8] + "..." + settings.gitlab_token[-4:]
        print(f"  {PASS} GITLAB_TOKEN is set ({masked})")

    print(f"  {PASS} GITLAB_URL = {settings.gitlab_url}")

    try:
        members = settings.get_team_members()
        print(f"  {PASS} team_members.json loaded — {len(members)} members")
    except FileNotFoundError:
        print(f"  {FAIL} team_members.json not found — copy team_members.json.example and configure it")
        ok = False
    except ValueError as e:
        print(f"  {FAIL} team_members.json invalid: {e}")
        ok = False

    try:
        groups = settings.get_groups()
        enabled = [g for g in groups if g.get("enabled", True)]
        print(f"  {PASS} groups.json loaded — {len(enabled)} enabled source(s)")
        for g in enabled:
            src_type = g.get("type", "group")
            print(f"      - {g['name']} ({src_type}: {g['path']})")

        paths = [(g['id'], g['name'], g['path']) for g in enabled]
        for i, (id1, name1, p1) in enumerate(paths):
            for id2, name2, p2 in paths[i + 1:]:
                if p1.startswith(p2 + '/'):
                    parent_name, child_name = name2, name1
                    parent_path, child_path = p2, p1
                elif p2.startswith(p1 + '/'):
                    parent_name, child_name = name1, name2
                    parent_path, child_path = p1, p2
                else:
                    continue
                print(f"  {WARN} Overlapping paths (duplicates will be auto-deduplicated):")
                print(f"      Parent: {parent_name} ({parent_path})")
                print(f"      Child:  {child_name} ({child_path})")
    except FileNotFoundError:
        print(f"  {WARN} groups.json not found — will use GITLAB_GROUP env var as fallback")
    except ValueError as e:
        print(f"  {FAIL} groups.json invalid: {e}")
        ok = False

    return ok


def check_gitlab_rest_api():
    section("2. GitLab REST API Authentication")

    from app.config import settings
    import gitlab

    try:
        gl = gitlab.Gitlab(settings.gitlab_url, private_token=settings.gitlab_token)
        gl.auth()
        user = gl.user
        print(f"  {PASS} Authenticated as: {user.name} (@{user.username})")
        return gl
    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"  {FAIL} Authentication failed — check your GITLAB_TOKEN")
        print(f"      Token needs 'read_api' and 'read_repository' scopes")
        return None
    except Exception as e:
        print(f"  {FAIL} Connection failed: {e}")
        print(f"      Check that GITLAB_URL ({settings.gitlab_url}) is reachable")
        return None


def check_gitlab_graphql():
    section("3. GitLab GraphQL API")

    from app.config import settings

    query = '{ currentUser { username name } }'
    headers = {
        'Authorization': f'Bearer {settings.gitlab_token}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(
            f'{settings.gitlab_url}/api/graphql',
            json={'query': query},
            headers=headers,
            timeout=15,
        )

        if response.status_code == 401:
            print(f"  {FAIL} GraphQL authentication failed (401)")
            return False

        if response.status_code != 200:
            print(f"  {FAIL} GraphQL request failed with status {response.status_code}")
            return False

        data = response.json()
        if 'errors' in data and not data.get('data'):
            print(f"  {FAIL} GraphQL errors: {data['errors'][0].get('message', data['errors'])}")
            return False

        user = data.get('data', {}).get('currentUser', {})
        print(f"  {PASS} GraphQL API working — user: {user.get('name')} (@{user.get('username')})")
        return True

    except requests.ConnectionError:
        print(f"  {FAIL} Could not connect to {settings.gitlab_url}/api/graphql")
        return False
    except Exception as e:
        print(f"  {FAIL} GraphQL check failed: {e}")
        return False


def check_group_access(gl):
    section("4. Group & Project Access")

    from app.config import settings

    if gl is None:
        print(f"  {WARN} Skipping — REST API authentication failed")
        return True

    groups = settings.get_groups()
    enabled = [g for g in groups if g.get("enabled", True)]
    all_ok = True

    for g in enabled:
        src_type = g.get("type", "group")
        path = g["path"]
        try:
            if src_type == "project":
                gl.projects.get(path)
            else:
                gl.groups.get(path)
            print(f"  {PASS} {g['name']} ({src_type}: {path})")
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                print(f"  {FAIL} {g['name']} — not found at '{path}'")
            elif "403" in error_msg:
                print(f"  {FAIL} {g['name']} — access denied (check token scopes)")
            else:
                print(f"  {FAIL} {g['name']} — {error_msg}")
            all_ok = False

    return all_ok


def check_database():
    section("5. Database")

    from app.config import settings
    from sqlalchemy import create_engine, text

    try:
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"  {PASS} SQLite connection OK ({settings.database_url})")
    except Exception as e:
        print(f"  {FAIL} Database connection failed: {e}")
        return False

    try:
        from app.models.schemas import MergeRequest, Commit, Comment, Contributor, CacheMetadata
        from app.models.database import Base

        Base.metadata.create_all(bind=engine)
        print(f"  {PASS} All tables created/verified")
        return True
    except Exception as e:
        print(f"  {FAIL} Table creation failed: {e}")
        return False


def check_team_members(gl):
    section("6. Team Member Verification")

    from app.config import settings

    if gl is None:
        print(f"  {WARN} Skipping — REST API authentication failed")
        return True

    try:
        members = settings.get_team_members()
    except Exception:
        print(f"  {WARN} Skipping — team_members.json not loaded")
        return True

    sample = members[:3]
    found = 0
    for username in sample:
        try:
            users = gl.users.list(username=username)
            if users:
                print(f"  {PASS} @{username} — found in GitLab")
                found += 1
            else:
                print(f"  {WARN} @{username} — not found (check username spelling)")
        except Exception as e:
            print(f"  {WARN} @{username} — lookup failed: {e}")

    remaining = len(members) - len(sample)
    if remaining > 0:
        print(f"      ({remaining} more members not checked)")

    return True


def main():
    print(f"\n{BOLD}GitLab Dashboard — Setup Verification{RESET}")
    print(f"{'─' * 50}")

    results = {}

    results["env"] = check_env_file()

    if not results["env"]:
        print(f"\n{RED}{BOLD}Setup verification failed.{RESET}")
        print("Fix the configuration issues above before continuing.")
        sys.exit(1)

    gl = check_gitlab_rest_api()
    results["rest"] = gl is not None
    results["graphql"] = check_gitlab_graphql()
    results["groups"] = check_group_access(gl)
    results["database"] = check_database()
    results["team"] = check_team_members(gl)

    section("Summary")
    critical_checks = ["env", "rest", "graphql", "database"]
    critical_ok = all(results[k] for k in critical_checks)

    for name, passed in results.items():
        icon = PASS if passed else FAIL
        print(f"  {icon} {name}")

    if critical_ok:
        print(f"\n{GREEN}{BOLD}All critical checks passed. Ready to start the dashboard.{RESET}")
        sys.exit(0)
    else:
        failed = [k for k in critical_checks if not results[k]]
        print(f"\n{RED}{BOLD}Critical checks failed: {', '.join(failed)}{RESET}")
        print("Fix the issues above before starting the dashboard.")
        sys.exit(1)


if __name__ == "__main__":
    main()
