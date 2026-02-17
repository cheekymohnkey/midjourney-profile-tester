"""Profile analyses caching manager.

Provides a process-local cache for files under `profile_analyses/` using
storage.get_metadata() for invalidation (ETag -> last_modified/mtime -> size).
Logs cache events via `services.console_logger`.
"""
from typing import Dict
from storage import get_storage

_cached_analyses: Dict[str, Dict] = {}
_cached_meta: Dict[str, Dict] = {}


def _meta_changed(old: Dict | None, new: Dict | None) -> bool:
    old = old or {}
    new = new or {}
    old_etag = old.get('etag')
    new_etag = new.get('etag')
    if old_etag is not None or new_etag is not None:
        return (old_etag or None) != (new_etag or None)

    old_lm = old.get('last_modified') or old.get('mtime')
    new_lm = new.get('last_modified') or new.get('mtime')
    if old_lm is not None or new_lm is not None:
        try:
            return float(old_lm or 0) != float(new_lm or 0)
        except Exception:
            pass

    old_size = old.get('size')
    new_size = new.get('size')
    if old_size is not None or new_size is not None:
        try:
            return int(old_size or 0) != int(new_size or 0)
        except Exception:
            pass

    return old != new


def load_all_analyses() -> Dict[str, Dict]:
    """Load all analyses with per-file metadata-aware caching.

    Returns a dict mapping `profile_id` -> analysis dict.
    """
    storage = get_storage()
    try:
        from services.console_logger import log_cache_hit, log_cache_miss, log_cache_invalidate
    except Exception:
        def log_cache_hit(_):
            pass
        def log_cache_miss(_):
            pass
        def log_cache_invalidate(_, __, ___):
            pass

    analysis_files = storage.list_files('profile_analyses', '*_analysis.json')
    results: Dict[str, Dict] = {}

    for file_path in analysis_files:
        try:
            current_meta = storage.get_metadata(file_path) or {}
        except Exception:
            current_meta = {}

        cached = _cached_analyses.get(file_path)
        cached_meta = _cached_meta.get(file_path)

        if cached is not None:
            if _meta_changed(cached_meta, current_meta):
                try:
                    log_cache_invalidate(file_path, cached_meta, current_meta)
                except Exception:
                    pass
                try:
                    log_cache_miss(file_path)
                except Exception:
                    pass
                try:
                    # Prefer ResultsDataService for reads so authoritative path is centralized
                    from services.results_data_service import get_results_data_service
                    rds = get_results_data_service()
                    # derive profile id from filename
                    file_name = file_path.split('/')[-1]
                    profile_id = file_name.replace('_analysis.json', '')
                    data = rds.read_analysis(profile_id) or {}
                except Exception:
                    try:
                        data = storage.read_json(file_path) or {}
                    except Exception:
                        data = {}
                _cached_analyses[file_path] = data
                try:
                    _cached_meta[file_path] = storage.get_metadata(file_path) or {}
                except Exception:
                    _cached_meta[file_path] = {}
            else:
                try:
                    log_cache_hit(file_path)
                except Exception:
                    pass
                data = cached
        else:
            try:
                log_cache_miss(file_path)
            except Exception:
                pass
            try:
                # Use ResultsDataService to read analysis content when possible
                from services.results_data_service import get_results_data_service
                rds = get_results_data_service()
                file_name = file_path.split('/')[-1]
                profile_id = file_name.replace('_analysis.json', '')
                data = rds.read_analysis(profile_id) or {}
            except Exception:
                try:
                    data = storage.read_json(file_path) or {}
                except Exception:
                    data = {}
            _cached_analyses[file_path] = data
            try:
                _cached_meta[file_path] = storage.get_metadata(file_path) or {}
            except Exception:
                _cached_meta[file_path] = {}

        file_name = file_path.split('/')[-1]
        profile_id = data.get('profile_id', file_name.replace('_analysis.json', ''))
        results[profile_id] = data

    return results


def load_analysis(profile_id: str) -> Dict:
    """Load a single profile analysis using the cache if possible."""
    analyses = load_all_analyses()
    return analyses.get(profile_id) or {}


def invalidate(path: str) -> None:
    """Invalidate cached entries that match `path`.

    `path` may be a filesystem path or S3 key; we perform suffix and exact
    matching against cached keys to remove relevant entries.
    """
    global _cached_analyses, _cached_meta
    try:
        from services.console_logger import log_cache_invalidate
    except Exception:
        def log_cache_invalidate(*args, **kwargs):
            pass

    key = str(path)
    removed = []
    for k in list(_cached_analyses.keys()):
        try:
            if k == key or k.endswith(key) or key.endswith(k):
                old_meta = _cached_meta.get(k)
                _cached_analyses.pop(k, None)
                _cached_meta.pop(k, None)
                removed.append(k)
                try:
                    log_cache_invalidate(k, old_meta, {})
                except Exception:
                    pass
        except Exception:
            continue


def clear_cache() -> None:
    """Clear the entire profile analyses cache."""
    global _cached_analyses, _cached_meta
    _cached_analyses.clear()
    _cached_meta.clear()
