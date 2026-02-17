"""Centralized test prompts data service.

Provides a singleton wrapper around loading/saving test prompt data. This
central location makes it easy to change caching, invalidation, and provides
convenient lookup helpers used across the app.
"""
from typing import List, Dict, Optional
import logging

# results service is a consumer-only dependency; import lazily where needed
try:
    from services.results_data_service import get_results_data_service
except Exception:
    get_results_data_service = None

logger = logging.getLogger(__name__)


class TestDataService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # lazy-import to avoid circular imports at module import time
        try:
            import test_prompts_manager as tpm
            self._tpm = tpm
        except Exception:
            self._tpm = None

    def list_tests(self, status_filter: Optional[str] = None) -> List[Dict]:
        """Return list of tests; delegates to `test_prompts_manager.load_tests`.

        `status_filter` may be passed through if supported.
        """
        if not self._tpm:
            logger.error("test_prompts_manager not available")
            return []
        try:
            return self._tpm.load_tests(status_filter)
        except Exception:
            logger.exception("Failed to load tests from test_prompts_manager")
            return []

    def get_by_guid(self, guid: str) -> Optional[Dict]:
        tests = self.list_tests()
        for t in tests:
            if t.get("guid") == guid:
                return t
        return None

    def get_by_id(self, id_: str) -> Optional[Dict]:
        tests = self.list_tests()
        for t in tests:
            if t.get("id") == id_:
                return t
        return None

    def get_by_title(self, title: str) -> Optional[Dict]:
        # delegate to tpm if available (they have a helper)
        if self._tpm:
            try:
                return self._tpm.get_test_by_title(title)
            except Exception:
                logger.exception("get_test_by_title failed")
        # fallback to scanning
        tests = self.list_tests()
        for t in tests:
            if t.get("title") == title:
                return t
        return None

    def save_tests(self, tests: List[Dict]):
        if not self._tpm:
            logger.error("test_prompts_manager not available for save")
            return
        try:
            self._tpm.save_tests(tests)
        except Exception:
            logger.exception("Failed to save tests via test_prompts_manager")

    def add_test(self, title: str, prompt: str, section: str, params: str,
                 status: str = 'current', version: str = 'v2',
                 analysis_spec_version: str = None,
                 taxonomy_version: str = None,
                 intent: str = None,
                 analysis_family: str = None,
                 rubric: Dict = None) -> Optional[Dict]:
        if not self._tpm:
            logger.error("test_prompts_manager not available for add_test")
            return None
        try:
            return self._tpm.add_test(title=title, prompt=prompt, section=section, params=params,
                                      status=status, version=version,
                                      analysis_spec_version=analysis_spec_version,
                                      taxonomy_version=taxonomy_version,
                                      intent=intent,
                                      analysis_family=analysis_family,
                                      rubric=rubric)
        except Exception:
            logger.exception("add_test failed")
            return None

    def update_test(self, test_id: str, **kwargs) -> Optional[Dict]:
        if not self._tpm:
            logger.error("test_prompts_manager not available for update_test")
            return None
        try:
            updated = self._tpm.update_test(test_id, **kwargs)
            # If the test was archived, trigger results archiving for related ratings
            try:
                status = kwargs.get('status') or (updated or {}).get('status')
                if status == 'archived' and updated:
                    guid = updated.get('guid') or updated.get('id')
                    if guid and get_results_data_service:
                        try:
                            get_results_data_service().archive_ratings_for_test(guid, dry_run=False)
                        except Exception:
                            logger.exception("Failed to archive ratings for test guid=%s", guid)
            except Exception:
                logger.exception("Error checking archive post-update for %s", test_id)
            return updated
        except Exception:
            logger.exception("update_test failed")
            return None

    def delete_test(self, test_id: str) -> bool:
        if not self._tpm:
            logger.error("test_prompts_manager not available for delete_test")
            return False
        try:
            return self._tpm.delete_test(test_id)
        except Exception:
            logger.exception("delete_test failed")
            return False

    def archive_test(self, test_id: str) -> bool:
        if not self._tpm:
            logger.error("test_prompts_manager not available for archive_test")
            return False
        try:
            # capture the test guid before archiving
            try:
                existing = self.get_by_id(test_id)
                guid = existing.get('guid') if existing else None
            except Exception:
                guid = None

            res = self._tpm.archive_test(test_id)
            if res and guid and get_results_data_service:
                try:
                    get_results_data_service().archive_ratings_for_test(guid, dry_run=False)
                except Exception:
                    logger.exception("Failed to archive ratings for test guid=%s", guid)
            return res
        except Exception:
            logger.exception("archive_test failed")
            return False

    def duplicate_test(self, test_id: str, new_version: Optional[str] = None) -> Optional[Dict]:
        if not self._tpm:
            logger.error("test_prompts_manager not available for duplicate_test")
            return None
        try:
            return self._tpm.duplicate_test(test_id, new_version=new_version)
        except Exception:
            logger.exception("duplicate_test failed")
            return None


def get_test_data_service() -> TestDataService:
    return TestDataService()
