"""Centralized results/analysis data service.

Provides a small service to list/add/delete profile test results. It will
delegate to an existing `results_manager` if available; otherwise it returns
safe defaults so callers don't crash during incremental migration.
"""
from typing import List, Dict, Optional
import logging
from datetime import datetime

from storage import get_storage

logger = logging.getLogger(__name__)


class ResultsDataService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        try:
            import results_manager as rm
            self._rm = rm
        except Exception:
            self._rm = None

    def list_results_for_profile(self, profile_id: str) -> List[Dict]:
        if not self._rm:
            logger.debug("results_manager not available; returning empty list")
            return []
        try:
            if hasattr(self._rm, 'list_results_for_profile'):
                return self._rm.list_results_for_profile(profile_id)
            return []
        except Exception:
            logger.exception("Failed to list results via results_manager")
            return []

    def get_result_by_id(self, result_id: str) -> Optional[Dict]:
        if not self._rm:
            return None
        try:
            if hasattr(self._rm, 'get_result_by_id'):
                return self._rm.get_result_by_id(result_id)
            return None
        except Exception:
            logger.exception("get_result_by_id failed")
            return None

    def add_result(self, profile_id: str, test_id: str, payload: Dict) -> Optional[Dict]:
        if not self._rm:
            logger.error("results_manager not available for add_result")
            return None
        try:
            return self._rm.add_result(profile_id=profile_id, test_id=test_id, payload=payload)
        except Exception:
            logger.exception("add_result failed")
            return None

    # High-level analysis file helpers ------------------------------------
    def _analysis_paths(self, profile_id: str):
        base = f"profile_analyses/{profile_id}_analysis.json"
        backup_dir = f"profile_analyses/backups"
        archive = f"profile_analyses/{profile_id}_analysis_archive.json"
        return base, backup_dir, archive

    def read_analysis(self, profile_id: str) -> Dict:
        """Return the full analysis dict for a profile (may be empty dict)."""
        # Prefer results_manager if it exposes read_analysis
        if self._rm and hasattr(self._rm, 'read_analysis'):
            try:
                return self._rm.read_analysis(profile_id) or {}
            except Exception:
                logger.exception("read_analysis via results_manager failed for %s", profile_id)
                return {}

        # Fallback to storage-backed file
        try:
            storage = get_storage()
            path, _, _ = self._analysis_paths(profile_id)
            return storage.read_json(path) or {}
        except Exception:
            logger.exception("read_analysis failed for %s", profile_id)
            return {}

    def write_analysis(self, profile_id: str, analysis: Dict, make_backup: bool = True) -> bool:
        """Write the full analysis dict for a profile, optionally making a timestamped backup of the prior file."""
        if self._rm and hasattr(self._rm, 'write_analysis'):
            try:
                return self._rm.write_analysis(profile_id, analysis, make_backup=make_backup)
            except Exception:
                logger.exception("write_analysis via results_manager failed for %s", profile_id)
                return False

        try:
            storage = get_storage()
            path, backup_dir, _ = self._analysis_paths(profile_id)
            # Backup prior if requested
            if make_backup:
                try:
                    prior = storage.read_json(path) or {}
                    if prior:
                        import datetime
                        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        backup_name = f"{profile_id}_analysis_backup_{ts}.json"
                        backup_path = f"{backup_dir}/{backup_name}"
                        storage.write_json(backup_path, prior)
                except Exception:
                    logger.exception("Failed to write analysis backup for %s", profile_id)

            storage.write_json(path, analysis)
            return True
        except Exception:
            logger.exception("write_analysis failed for %s", profile_id)
            return False

    def delete_result(self, result_id: str) -> bool:
        if not self._rm:
            logger.error("results_manager not available for delete_result")
            return False
        try:
            return self._rm.delete_result(result_id)
        except Exception:
            logger.exception("delete_result failed")
            return False

    # Analysis / profile_analyses helpers ---------------------------------
    def _analysis_paths(self, profile_id: str):
        base = f"profile_analyses/{profile_id}_analysis.json"
        backup_dir = f"profile_analyses/backups"
        archive = f"profile_analyses/{profile_id}_analysis_archive.json"
        return base, backup_dir, archive

    def archive_orphaned_ratings(self, profile_id: str, active_test_guids: Optional[set] = None, dry_run: bool = False) -> Dict:
        """Move ratings from a profile analysis file into an archive if their keys are not in `active_test_guids`.

        Returns dict with counts and list of moved keys.
        """
        storage = get_storage()
        base_path, backup_dir, archive_path = self._analysis_paths(profile_id)
        try:
            analysis = storage.read_json(base_path) or {}
        except Exception:
            logger.debug("No analysis file for %s", profile_id)
            return {"moved": 0, "moved_keys": []}

        ratings = analysis.get('ratings', {}) or {}
        if not ratings:
            return {"moved": 0, "moved_keys": []}

        active = set(active_test_guids or [])
        orphan_keys = [k for k in ratings.keys() if (active and k not in active) or (not active and False)]
        # If active set is empty, nothing to consider orphaned
        if not orphan_keys:
            return {"moved": 0, "moved_keys": []}

        # Load or create archive
        try:
            archive = storage.read_json(archive_path) or {}
        except Exception:
            archive = {}

        archive_ratings = archive.get('ratings', {}) or {}

        moved = 0
        moved_keys = []
        for k in orphan_keys:
            archive_ratings[k] = ratings.pop(k)
            moved += 1
            moved_keys.append(k)

        if not dry_run:
            # persist changes
            analysis['ratings'] = ratings
            archive['ratings'] = archive_ratings
            # record metadata
            archive.setdefault('archived_at', {})
            archive['archived_at'][datetime.utcnow().isoformat()] = len(moved_keys)
            try:
                storage.write_json(base_path, analysis)
                storage.write_json(archive_path, archive)
            except Exception:
                logger.exception("Failed to persist archived ratings for %s", profile_id)

        return {"moved": moved, "moved_keys": moved_keys}

    def archive_ratings_for_test(self, test_guid: str, dry_run: bool = False) -> Dict:
        """Scan all profile analyses and move any rating with key==test_guid to the per-profile archive.

        Returns dict mapping profile_id -> moved count.
        """
        storage = get_storage()
        # List files under profile_analyses; storage.list_files may support glob
        try:
            files = storage.list_files('profile_analyses', '*')
        except Exception:
            logger.exception("Failed to list profile_analyses")
            return {}

        results = {}
        for fp in files:
            # expect filenames like '{profile_id}_analysis.json' or backups; skip archives
            if not fp.endswith('_analysis.json') or fp.endswith('_analysis_archive.json'):
                continue
            # derive profile id
            filename = fp.split('/')[-1]
            profile_id = filename.replace('_analysis.json', '')
            base_path, backup_dir, archive_path = self._analysis_paths(profile_id)
            try:
                analysis = storage.read_json(base_path) or {}
            except Exception:
                continue
            ratings = analysis.get('ratings', {}) or {}
            if test_guid in ratings:
                # move it
                try:
                    archive = storage.read_json(archive_path) or {}
                except Exception:
                    archive = {}
                archive_ratings = archive.get('ratings', {}) or {}
                archive_ratings[test_guid] = ratings.pop(test_guid)
                archive['ratings'] = archive_ratings
                if not dry_run:
                    analysis['ratings'] = ratings
                    archive.setdefault('archived_at', {})
                    archive['archived_at'][datetime.utcnow().isoformat()] = archive['archived_at'].get(datetime.utcnow().isoformat(), 0) + 1
                    try:
                        storage.write_json(base_path, analysis)
                        storage.write_json(archive_path, archive)
                    except Exception:
                        logger.exception("Failed to persist archive for %s/%s", profile_id, test_guid)
                results[profile_id] = 1

        return results


def get_results_data_service() -> ResultsDataService:
    return ResultsDataService()
