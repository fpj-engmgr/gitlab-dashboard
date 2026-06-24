"""
Multi-group GitLab client for parallel fetching across multiple groups.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import logging

from app.config import settings
from app.services.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class MultiGroupGitLabClient:
    """Orchestrates fetching from multiple GitLab groups in parallel."""

    def __init__(self):
        self.groups = settings.get_groups()
        self.clients = {
            group['id']: GitLabClient(
                group_path=group['path'],
                group_id=group['id'],
                source_type=group.get('type', 'group')  # Support both "group" and "project" types
            )
            for group in self.groups if group.get('enabled', True)
        }
        logger.info(f"Initialized multi-group client with {len(self.clients)} sources (groups/projects)")

    def get_all_merge_requests(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch MRs from all groups in parallel."""
        all_mrs = []
        max_workers = min(len(self.clients), 5)  # Cap at 5 concurrent groups

        logger.info(f"Fetching MRs from {len(self.clients)} groups in parallel (max {max_workers} workers)")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(client.get_merge_requests, days): group_id
                for group_id, client in self.clients.items()
            }

            for future in as_completed(futures):
                group_id = futures[future]
                try:
                    mrs = future.result()
                    all_mrs.extend(mrs)
                    logger.info(f"Group {group_id}: fetched {len(mrs)} MRs")
                except Exception as e:
                    logger.error(f"Error fetching MRs for group {group_id}: {e}")

        logger.info(f"Total MRs fetched from all groups: {len(all_mrs)}")
        return all_mrs

    def get_contributor_stats_from_mrs(self, mrs_data: List[Dict[str, Any]], days: int = 30, fetch_details: bool = True) -> List[Dict[str, Any]]:
        """
        Get contributor stats from MR data across all groups.
        Since MRs already have group_id, we can process them directly.
        """
        # Group MRs by group_id
        mrs_by_group = {}
        for mr in mrs_data:
            group_id = mr.get('group_id', 'default')
            if group_id not in mrs_by_group:
                mrs_by_group[group_id] = []
            mrs_by_group[group_id].append(mr)

        all_contributors = []

        # Process each group's MRs with its corresponding client
        for group_id, group_mrs in mrs_by_group.items():
            if group_id not in self.clients:
                logger.warning(f"No client for group {group_id}, skipping")
                continue

            client = self.clients[group_id]
            try:
                contributors = client.get_contributor_stats_from_mrs(group_mrs, days=days, fetch_details=fetch_details)
                all_contributors.extend(contributors)
                logger.info(f"Group {group_id}: processed {len(contributors)} contributors")
            except Exception as e:
                logger.error(f"Error processing contributors for group {group_id}: {e}")

        logger.info(f"Total contributors across all groups: {len(all_contributors)}")
        return all_contributors
