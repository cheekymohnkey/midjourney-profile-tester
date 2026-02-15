"""Test prompts management module."""
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from storage import get_storage

TEST_PROMPTS_FILE = "test_prompts.json"

# Simple in-memory cache to avoid expensive repeated reads (e.g. Streamlit reruns)
_cached_tests: List[Dict] | None = None
# Metadata for cached object (etag/mtime/size) to support cross-process invalidation checks
_cached_tests_meta: Dict | None = None


def load_tests(status_filter: Optional[str] = None) -> List[Dict]:
    """Load test prompts from JSON file.

    Uses a simple process-local cache to avoid repeated disk/S3 reads during
    frequent reruns (for example in Streamlit). The cache is invalidated by
    `save_tests()`.

    Args:
        status_filter: Filter by status ('current', 'archived', or None for all)

    Returns:
        List of test prompt dictionaries
    """
    global _cached_tests, _cached_tests_meta
    storage = get_storage()

    # If we have a cached value, verify remote metadata hasn't changed.
    if _cached_tests is not None:
        try:
            current_meta = storage.get_metadata(TEST_PROMPTS_FILE) or {}
        except Exception:
            current_meta = {}

        def _meta_changed(old: dict | None, new: dict | None) -> bool:
            # Prefer ETag if present
            old = old or {}
            new = new or {}
            old_etag = old.get('etag')
            new_etag = new.get('etag')
            if old_etag is not None or new_etag is not None:
                return (old_etag or None) != (new_etag or None)

            # Fallback to last_modified (float timestamps)
            old_lm = old.get('last_modified') or old.get('mtime')
            new_lm = new.get('last_modified') or new.get('mtime')
            if old_lm is not None or new_lm is not None:
                try:
                    return float(old_lm or 0) != float(new_lm or 0)
                except Exception:
                    pass

            # Finally, compare size
            old_size = old.get('size')
            new_size = new.get('size')
            if old_size is not None or new_size is not None:
                return int(old_size or 0) != int(new_size or 0)

            # As last resort, consider metadata changed if dicts differ
            return old != new

        changed = _meta_changed(_cached_tests_meta, current_meta)
        if changed:
            try:
                from services.console_logger import log_cache_invalidate
                log_cache_invalidate(TEST_PROMPTS_FILE, _cached_tests_meta, current_meta)
            except Exception:
                pass
            try:
                from services.console_logger import log_cache_miss
                log_cache_miss(TEST_PROMPTS_FILE)
            except Exception:
                pass
            data = storage.read_json(TEST_PROMPTS_FILE)
            _cached_tests = data if isinstance(data, list) else []
            try:
                _cached_tests_meta = storage.get_metadata(TEST_PROMPTS_FILE) or {}
            except Exception:
                _cached_tests_meta = {}
        else:
            try:
                from services.console_logger import log_cache_hit
                log_cache_hit(TEST_PROMPTS_FILE)
            except Exception:
                pass

    else:
        try:
            from services.console_logger import log_cache_miss
            log_cache_miss(TEST_PROMPTS_FILE)
        except Exception:
            pass
        data = storage.read_json(TEST_PROMPTS_FILE)
        _cached_tests = data if isinstance(data, list) else []
        try:
            _cached_tests_meta = storage.get_metadata(TEST_PROMPTS_FILE) or {}
        except Exception:
            _cached_tests_meta = {}

    tests = _cached_tests

    if status_filter:
        tests = [t for t in tests if t.get('status') == status_filter]

    return tests


def save_tests(tests: List[Dict]):
    """Save test prompts to JSON file and invalidate cache."""
    global _cached_tests, _cached_tests_meta
    storage = get_storage()
    storage.write_json(TEST_PROMPTS_FILE, tests)
    # Update cache to reflect the newly saved content so next reads are hits
    _cached_tests = tests
    try:
        _cached_tests_meta = storage.get_metadata(TEST_PROMPTS_FILE) or {}
    except Exception:
        _cached_tests_meta = None

def add_test(title: str, prompt: str, section: str, params: str, 
             status: str = 'current', version: str = 'v2',
             analysis_spec_version: str = None,
             taxonomy_version: str = None,
             intent: str = None,
             analysis_family: str = None,
             rubric: Dict = None) -> Dict:
    """Add a new test prompt."""
    tests = load_tests()
    
    test_id = title.replace(' ', '_').replace('/', '_')
    guid = uuid.uuid4().hex

    new_test = {
        'id': test_id,
        'guid': guid,
        'title': title,
        'prompt': prompt,
        'section': section,
        'params': params,
        'status': status,
        'version': version,
        'created_date': datetime.now().strftime('%Y-%m-%d')
    }
    # Optional new metadata
    if analysis_spec_version:
        new_test['analysis_spec_version'] = analysis_spec_version
    if taxonomy_version:
        new_test['taxonomy_version'] = taxonomy_version
    if intent:
        new_test['intent'] = intent
    if analysis_family:
        new_test['analysis_family'] = analysis_family
    if rubric:
        new_test['rubric'] = rubric
    
    tests.append(new_test)
    save_tests(tests)
    
    return new_test

def update_test(test_id: str, **kwargs) -> Optional[Dict]:
    """Update an existing test prompt."""
    tests = load_tests()
    
    for test in tests:
        if test['id'] == test_id:
            # Preserve existing guid if present
            guid = test.get('guid')
            test.update(kwargs)
            if guid:
                test['guid'] = guid
            save_tests(tests)
            return test
    
    return None

def delete_test(test_id: str) -> bool:
    """Delete a test prompt."""
    tests = load_tests()
    original_len = len(tests)
    
    tests = [t for t in tests if t['id'] != test_id]
    
    if len(tests) < original_len:
        save_tests(tests)
        return True
    
    return False

def archive_test(test_id: str) -> bool:
    """Archive a test (set status to 'archived')."""
    return update_test(test_id, status='archived') is not None

def duplicate_test(test_id: str, new_version: Optional[str] = None) -> Optional[Dict]:
    """Duplicate a test with a new version."""
    tests = load_tests()
    
    for test in tests:
        if test['id'] == test_id:
            new_test = test.copy()
            new_test['id'] = f"{test_id}_copy"
            new_test['guid'] = uuid.uuid4().hex
            new_test['title'] = f"{test['title']} (Copy)"
            if new_version:
                new_test['version'] = new_version
            new_test['created_date'] = datetime.now().strftime('%Y-%m-%d')
            
            tests.append(new_test)
            save_tests(tests)
            
            return new_test
    
    return None

def get_test_by_title(title: str) -> Optional[Dict]:
    """Get a test by its title."""
    tests = load_tests()
    for test in tests:
        if test['title'] == title:
            return test
    return None
