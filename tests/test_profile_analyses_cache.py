import os
import shutil
import time

from storage import get_storage
import profile_analyses_manager as pam


def test_profile_analyses_cache_invalidation(tmp_path, monkeypatch):
    # Ensure we use the project's storage (local) with base_path = cwd
    storage = get_storage()

    # Prepare profile_analyses directory
    pa_dir = tmp_path / "profile_analyses"
    pa_dir.mkdir()

    # Monkeypatch storage base path to tmp_path so storage operations go there
    if hasattr(storage, 'base_path'):
        monkeypatch.setattr(storage, 'base_path', tmp_path)

    filename = 'test_profile_analysis.json'
    path = f'profile_analyses/{filename}'

    # Ensure cache is clear
    pam.clear_cache()

    # Write initial analysis
    data_v1 = {'profile_id': 'test_profile', 'profile_label': 'v1'}
    storage.write_json(path, data_v1)

    # Load analyses to populate cache
    analyses = pam.load_all_analyses()
    assert 'test_profile' in analyses
    assert analyses['test_profile'].get('profile_label') == 'v1'

    # Now write updated content
    data_v2 = {'profile_id': 'test_profile', 'profile_label': 'v2'}
    storage.write_json(path, data_v2)

    # Give a moment for filesystem timestamp propagation
    time.sleep(0.01)

    # Reload analyses - cache should have been invalidated and reflect v2
    analyses2 = pam.load_all_analyses()
    assert 'test_profile' in analyses2
    assert analyses2['test_profile'].get('profile_label') == 'v2'

    # Cleanup
    try:
        # remove created files
        full_path = tmp_path / path
        if full_path.exists():
            full_path.unlink()
        # remove directory
        if pa_dir.exists():
            shutil.rmtree(pa_dir)
    except Exception:
        pass
