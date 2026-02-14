import streamlit as st
from midjourney_profile_tester import _set_ai_rated_session_flags


def test_set_ai_rated_session_flags_defaults():
    # Clear any existing session state keys
    st.session_state.clear()

    _set_ai_rated_session_flags('UI Test')

    assert st.session_state.get('just_ai_rated_UI Test') is True
    assert st.session_state.get('ai_rated_message_UI Test') == '✨ AI rating completed for UI Test'


def test_set_ai_rated_session_flags_custom_message():
    st.session_state.clear()

    _set_ai_rated_session_flags('Custom', message='Done ✅')

    assert st.session_state.get('just_ai_rated_Custom') is True
    assert st.session_state.get('ai_rated_message_Custom') == 'Done ✅'