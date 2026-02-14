import json
from PIL import Image
import streamlit as st
import config
from midjourney_profile_tester import batch_ai_rate_images, _set_ai_rated_session_flags


def make_image(path):
    img = Image.new('RGB', (160, 120), (200, 50, 120))
    img.save(path, format='JPEG')


def test_expander_stays_open_after_ai_rate(tmp_path, monkeypatch):
    # Prepare image and test row
    img_path = tmp_path / 'expander_test.jpg'
    make_image(img_path)

    test_name = 'Expander Test'
    row = {
        'Title': test_name,
        'Prompt': 'Prompt for expander test',
        'Section': 'Test',
        'rubric': {'must': ['face']}
    }

    single_test = [(test_name, str(img_path), row)]

    # Ensure OpenAI key present and local storage
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'test-key')
    monkeypatch.setenv('USE_S3', 'false')
    from storage import init_storage
    init_storage(use_s3=False)

    # Mock AI parser to return checks that will trigger deterministic scoring
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

    # Ensure session state is clean
    st.session_state.clear()

    # Run the batch rating (simulates the AI Rate action)
    result = batch_ai_rate_images(single_test, profile_id='expander-profile', existing_ratings=None)
    assert result and 'ratings' in result and test_name in result['ratings']

    # Simulate the UI updating session flags after AI rating
    _set_ai_rated_session_flags(test_name)

    # UI logic: if just_ai_rated flag is set, force_expanded should be True
    just_ai_rated = st.session_state.get(f'just_ai_rated_{test_name}', False)
    force_expanded = True if just_ai_rated else False

    assert just_ai_rated is True
    assert force_expanded is True
    assert st.session_state.get(f'ai_rated_message_{test_name}') is not None