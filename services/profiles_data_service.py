"""Centralized profiles data service.

Provides a singleton wrapper around profile storage/manager. This mirrors the
TestDataService pattern: lazy-import an existing manager if present, otherwise
provide a minimal safe surface that returns empty defaults.
"""
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ProfilesDataService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        try:
            import profiles_manager as pm
            self._pm = pm
        except Exception:
            self._pm = None

    def list_profiles(self, status_filter: Optional[str] = None) -> List[Dict]:
        if not self._pm:
            logger.debug("profiles_manager not available; returning empty list")
            return []
        try:
            # Many managers provide load_profiles or load_profiles_by_status
            if hasattr(self._pm, 'load_profiles'):
                return self._pm.load_profiles(status_filter)
            return []
        except Exception:
            logger.exception("Failed to list profiles via profiles_manager")
            return []

    def get_by_id(self, profile_id: str) -> Optional[Dict]:
        profiles = self.list_profiles()
        for p in profiles:
            if p.get('id') == profile_id:
                return p
        return None

    def add_profile(self, name: str, metadata: Dict = None) -> Optional[Dict]:
        if not self._pm:
            logger.error("profiles_manager not available for add_profile")
            return None
        try:
            return self._pm.add_profile(name=name, metadata=metadata)
        except Exception:
            logger.exception("add_profile failed")
            return None

    def update_profile(self, profile_id: str, **kwargs) -> Optional[Dict]:
        if not self._pm:
            logger.error("profiles_manager not available for update_profile")
            return None
        try:
            return self._pm.update_profile(profile_id, **kwargs)
        except Exception:
            logger.exception("update_profile failed")
            return None

    def delete_profile(self, profile_id: str) -> bool:
        if not self._pm:
            logger.error("profiles_manager not available for delete_profile")
            return False
        try:
            return self._pm.delete_profile(profile_id)
        except Exception:
            logger.exception("delete_profile failed")
            return False


def get_profiles_data_service() -> ProfilesDataService:
    return ProfilesDataService()
