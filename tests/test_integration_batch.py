import json
from PIL import Image
from services import analysis
import config
import pathlib

from midjourney_profile_tester import batch_ai_rate_images


def make_image(path):
    img = Image.new('RGB', (200, 120), (123, 222, 111))
    img.save(path, format='JPEG')


def test_batch_ai_rate_images_applies_deterministic_scoring(tmp_path, monkeypatch):
    # Prepare a real image file (the function will load it)
    img_path = tmp_path / 'test_img.jpg'
    make_image(img_path)

    test_name = 'Integration Test A'
    # Minimal row with rubric so the test is not skipped by the guard
    row = {
        'Title': test_name,
        'Prompt': 'A prompt',
        'Section': 'Test',
        'rubric': {'must': ['face']}
    }

    uploaded_tests = [(test_name, str(img_path), row)]

    # Ensure config has an API key so batch function proceeds to call ai_client
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'test-key')
    # Ensure local storage is used during tests (avoid S3 calls)
    monkeypatch.setenv('USE_S3', 'false')
    # Re-init storage backend to local (some modules initialize storage at import time)
    from storage import init_storage
    init_storage(use_s3=False)

    # Prepare a parsed AI response that includes `checks` with a MUST failure -> deterministic score should be 8.0
    parsed_response = {
        'ratings': {
            test_name: {
                'test_guid': None,
                'test_name': test_name,
                'checks': {
                    'must': [{'label': 'face_visible', 'pass': False}],
                    'avoid': [],
                    'prefer': []
                }
            }
        }
    }

    # Monkeypatch the ai_client parser to return our fake parsed response
    def fake_parse_json(client, messages, **kwargs):
        return parsed_response, json.dumps(parsed_response), object()

    monkeypatch.setattr('services.ai_client.chat_completion_parse_json', fake_parse_json)

    # Run batch
    result = batch_ai_rate_images(uploaded_tests, profile_id='test-profile', profile_label='', existing_ratings=None)

    assert result is not None
    assert 'ratings' in result
    assert test_name in result['ratings']

    rating = result['ratings'][test_name]
    # Deterministic scoring should have been applied
    assert rating.get('score') == 8.0
    assert rating.get('metrics_v1') is not None
    assert rating['metrics_v1']['scoring_version'] == 'v1_group_weighted'