"""Test prompts management module."""
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from storage import get_storage

TEST_PROMPTS_FILE = "test_prompts.json"

def load_tests(status_filter: Optional[str] = None) -> List[Dict]:
    """Load test prompts from JSON file.
    
    Args:
        status_filter: Filter by status ('current', 'archived', or None for all)
    
    Returns:
        List of test prompt dictionaries
    """
    storage = get_storage()
    data = storage.read_json(TEST_PROMPTS_FILE)
    tests = data if isinstance(data, list) else []
    
    if status_filter:
        tests = [t for t in tests if t.get('status') == status_filter]
    
    return tests

def save_tests(tests: List[Dict]):
    """Save test prompts to JSON file."""
    storage = get_storage()
    storage.write_json(TEST_PROMPTS_FILE, tests)

def add_test(title: str, prompt: str, section: str, params: str, 
             status: str = 'current', version: str = 'v2') -> Dict:
    """Add a new test prompt."""
    tests = load_tests()
    
    test_id = title.replace(' ', '_').replace('/', '_')
    
    new_test = {
        'id': test_id,
        'title': title,
        'prompt': prompt,
        'section': section,
        'params': params,
        'status': status,
        'version': version,
        'created_date': datetime.now().strftime('%Y-%m-%d')
    }
    
    tests.append(new_test)
    save_tests(tests)
    
    return new_test

def update_test(test_id: str, **kwargs) -> Optional[Dict]:
    """Update an existing test prompt."""
    tests = load_tests()
    
    for test in tests:
        if test['id'] == test_id:
            test.update(kwargs)
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
