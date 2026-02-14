import json
from PIL import Image
import config
from midjourney_profile_tester import batch_ai_rate_images


def make_image(path):
    img = Image.new('RGB', (120, 200), (10, 120, 200))
    img.save(path, format='JPEG')


def test_single_image_ai_rate_applies_deterministic_scoring(tmp_path, monkeypatch):
    # Create image file used by single-image UI flow
    img_path = tmp_path / 'single_test.jpg'
    make_image(img_path)

    test_name = 'Single Test UI'
    row = {
        'Title': test_name,
        'Prompt': 'A single-image prompt',
        'Section': 'Test',
        'rubric': {'must': ['face']}
    }

    single_test = [(test_name, str(img_path), row)]

    # Ensure OpenAI key exists so code proceeds to AI parsing path
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'test-key')

    # Force local storage backend for this test
    monkeypatch.setenv('USE_S3', 'false')
    from storage import init_storage
    init_storage(use_s3=False)

    # Fake parsed AI response including checks -> deterministic score expected
    parsed_response = {
        'ratings': {
            test_name: {
                'test_guid': None,
                'test_name': test_name,
                'checks': {
                    'must': [{'label': 'face_visible', 'pass': True}],
                    'avoid': [],
                    'prefer': []
                }
            }
        }
    }

    def fake_parse_json(client, messages, **kwargs):
        return parsed_response, json.dumps(parsed_response), object()

    monkeypatch.setattr('services.ai_client.chat_completion_parse_json', fake_parse_json)

    result = batch_ai_rate_images(single_test, profile_id='single-profile', existing_ratings=None)

    assert result is not None
    assert 'ratings' in result
    assert test_name in result['ratings']

    rating = result['ratings'][test_name]
    # Deterministic scoring should be applied when checks are present
    assert rating.get('metrics_v1') is not None
    assert rating['metrics_v1']['scoring_version'] == 'v1_group_weighted'
    # Score should be a float between 1 and 10
    assert isinstance(rating.get('score'), (int, float))
    assert 1 <= rating['score'] <= 10