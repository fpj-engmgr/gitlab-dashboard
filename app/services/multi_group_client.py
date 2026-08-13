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
                source_type=group.get('type', 'group')
            )
            for group in self.groups if group.get('enabled', True)
        }
        self._group_paths = self._build_group_path_map()
        logger.info(f"Initialized multi-group client with {len(self.clients)} sources (groups/projects)")

        for parent_id, parent_path, child_id, child_path in self._detect_overlaps():
            logger.warning(
                f"Overlapping group paths: '{parent_id}' ({parent_path}) contains "
                f"'{child_id}' ({child_path}). Duplicates will be auto-deduplicated."
            )

    def _build_group_path_map(self) -> Dict[str, str]:
        return {
            group['id']: group['path']
            for group in self.groups if group.get('enabled', True)
        }

    def _detect_overlaps(self) -> List:
        paths = list(self._group_paths.items())
        overlaps = []
        for i, (id1, p1) in enumerate(paths):
            for id2, p2 in paths[i + 1:]:
                if p1.startswith(p2 + '/'):
                    overlaps.append((id2, p2, id1, p1))
                elif p2.startswith(p1 + '/'):
                    overlaps.append((id1, p1, id2, p2))
        return overlaps

    def _dedup_merge_requests(self, mrs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = {}
        for mr in mrs:
            key = (mr['project_id'], mr['iid'])
            if key not in seen:
                seen[key] = mr
            else:
                existing_path = self._group_paths.get(seen[key].get('group_id', ''), '')
                new_path = self._group_paths.get(mr.get('group_id', ''), '')
                if len(new_path) > len(existing_path):
                    seen[key] = mr
        return list(seen.values())

    def _dedup_comments(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = {}
        for comment in comments:
            key = comment['note_id']
            if key not in seen:
                seen[key] = comment
            else:
                existing_path = self._group_paths.get(seen[key].get('group_id', ''), '')
                new_path = self._group_paths.get(comment.get('group_id', ''), '')
                if len(new_path) > len(existing_path):
                    seen[key] = comment
        return list(seen.values())

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

        before_dedup = len(all_mrs)
        all_mrs = self._dedup_merge_requests(all_mrs)
        if before_dedup != len(all_mrs):
            logger.info(f"Dedup removed {before_dedup - len(all_mrs)} duplicate MRs (overlapping groups)")
        logger.info(f"Total MRs fetched from all groups: {len(all_mrs)}")
        return all_mrs

    def get_all_comments(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch comments from all groups in parallel."""
        all_comments = []
        max_workers = min(len(self.clients), 5)  # Cap at 5 concurrent groups

        logger.info(f"Fetching comments from {len(self.clients)} groups in parallel (max {max_workers} workers)")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(client.get_comments, days): group_id
                for group_id, client in self.clients.items()
            }

            for future in as_completed(futures):
                group_id = futures[future]
                try:
                    comments = future.result()
                    all_comments.extend(comments)
                    logger.info(f"Group {group_id}: fetched {len(comments)} comments")
                except Exception as e:
                    logger.error(f"Error fetching comments for group {group_id}: {e}")

        before_dedup = len(all_comments)
        all_comments = self._dedup_comments(all_comments)
        if before_dedup != len(all_comments):
            logger.info(f"Dedup removed {before_dedup - len(all_comments)} duplicate comments (overlapping groups)")
        logger.info(f"Total comments fetched from all groups: {len(all_comments)}")
        return all_comments

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
