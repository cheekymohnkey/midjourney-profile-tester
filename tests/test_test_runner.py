import sys
import types
from pathlib import Path

import pytest


def make_fake_storage(tmp_path):
    class FakeStorage:
        def __init__(self):
            self._data = {}

        def read_json(self, path):
            return self._data.get(path)

        def write_json(self, path, data):
            self._data[path] = data

        def list_files(self, path, pattern):
            return []

        def delete(self, path):
            pass

    mod = types.ModuleType("storage")
    def get_storage():
        return FakeStorage()
    mod.get_storage = get_storage
    return mod


def test_no_images_for_void(monkeypatch, tmp_path):
    # Inject fake storage module so run_test_for_profile falls back safely
    monkeypatch.setitem(sys.modules, 'storage', make_fake_storage(tmp_path))

    from services.test_runner import run_test_for_profile

    # find_image_file always returns None
    def find_image_file(output_dir, profile_id, test_name, image_num=None):
        return None

    def batch_ai_rate_images(*args, **kwargs):
        pytest.skip("Should not be called when no images")

    def save_analysis(profile, data):
        pytest.skip("Should not be called when no images")

    test = {'title': 'Null Prompt (Photo)'}
    res = run_test_for_profile(test, 'prof1', find_image_file, save_analysis)
    assert res['status'] == 'no_images'
    assert res['saved'] is False


def test_single_image_saved_with_guid(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'storage', make_fake_storage(tmp_path))

    from services.test_runner import run_test_for_profile

    # find_image_file returns a fake Path for single-image test
    fake_path = tmp_path / "prof1_test.jpg"
    fake_path.write_text("jpg")

    def find_image_file(output_dir, profile_id, test_name, image_num=None):
        return fake_path

    # batch returns a rating keyed by the test title
    def batch_ai_rate_images(single_test, profile_id_check, existing_ratings=None):
        title = single_test[0][0]
        return {'ratings': {title: {'test_name': title, 'checks': {}, 'score': 5}}}

    saved = {}

    def save_analysis(profile, data):
        saved['profile'] = profile
        saved['data'] = data

    test = {'title': 'My Test', 'guid': 'a'*32}
    res = run_test_for_profile(test, 'prof1', find_image_file, save_analysis)
    assert res['status'] == 'ok'
    assert res['saved'] is True
    # Check save_analysis received ratings keyed by GUID
    assert saved['profile'] == 'prof1'
    assert 'a'*32 in saved['data']['ratings']
    assert saved['data']['ratings']['a'*32]['test_name'] == 'My Test'


def test_batch_error_propagates(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'storage', make_fake_storage(tmp_path))

    from services.test_runner import run_test_for_profile

    fake_path = tmp_path / "prof1_test.jpg"
    fake_path.write_text("jpg")

    def find_image_file(output_dir, profile_id, test_name, image_num=None):
        return fake_path

    def batch_ai_rate_images(single_test, profile_id_check, existing_ratings=None):
        raise RuntimeError("AI backend failure")

    def save_analysis(profile, data):
        pytest.skip("Should not be called on batch error")

    test = {'title': 'My Test'}
    res = run_test_for_profile(test, 'prof1', find_image_file, save_analysis)
    assert res['status'] == 'error'
    assert res['saved'] is False
    assert 'AI backend failure' in res['error']
