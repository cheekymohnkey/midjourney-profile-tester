from services.ai_client import extract_json_from_text, chat_completion_parse_json, chat_completion_to_text


class DummyResponse:
    def __init__(self, content):
        class Msg:
            def __init__(self, content):
                self.content = content
        class Choice:
            def __init__(self, content):
                self.message = Msg(content)
        self.choices = [Choice(content)]


class FakeClient:
    def __init__(self, content):
        self._content = content
        class Completions:
            def __init__(self, content):
                self._content = content
            def create(self, *args, **kwargs):
                return DummyResponse(self._content)
        self.chat = type('C', (), {'completions': Completions(self._content)})


def test_extract_json_from_text_fenced():
    text = "Here is the result:\n```json\n{\"a\": 1}\n```"
    parsed = extract_json_from_text(text)
    assert parsed == {"a": 1}


def test_extract_json_from_text_embedded():
    text = "Some text before {\"b\": [1,2,3]} some after"
    parsed = extract_json_from_text(text)
    assert parsed == {"b": [1, 2, 3]}


def test_chat_completion_parse_json_happy_path():
    client = FakeClient('{"ratings": {"Foo": {"score": 7}}}')
    parsed, resp_text, resp_obj = chat_completion_parse_json(client, messages=[{"role": "user", "content": "x"}], model="m")
    assert isinstance(parsed, dict)
    assert 'ratings' in parsed


def test_chat_completion_to_text_returns_text():
    client = FakeClient('plain text output')
    text, obj = chat_completion_to_text(client, messages=[{"role": "user", "content": "x"}], model="m")
    assert 'plain text output' in text


def test_chat_completion_parse_json_accepts_max_completion_tokens_in_kwargs():
    # Recorder that captures kwargs passed to the create() call
    class RecorderCompletions:
        def __init__(self, content):
            self._content = content
            self.last_kwargs = None

        def create(self, *args, **kwargs):
            self.last_kwargs = kwargs
            return DummyResponse(self._content)

    class RecorderClient:
        def __init__(self, content):
            self.chat = type('C', (), {'completions': RecorderCompletions(content)})

    client = RecorderClient('{"ratings": {}}')

    # Pass max_completion_tokens via kwargs to ensure no duplicate-key error
    parsed, resp_text, resp_obj = chat_completion_parse_json(client, messages=[{"role": "user", "content": "x"}], max_completion_tokens=1234)

    # Ensure the recorder saw the value
    assert client.chat.completions.last_kwargs is not None
    assert client.chat.completions.last_kwargs.get('max_completion_tokens') == 1234
    assert isinstance(parsed, dict) or parsed is None


def test_chat_completion_parse_json_accepts_legacy_max_tokens_key():
    # Recorder that captures kwargs passed to the create() call
    class RecorderCompletions:
        def __init__(self, content):
            self._content = content
            self.last_kwargs = None

        def create(self, *args, **kwargs):
            self.last_kwargs = kwargs
            return DummyResponse(self._content)

    class RecorderClient:
        def __init__(self, content):
            self.chat = type('C', (), {'completions': RecorderCompletions(content)})

    client = RecorderClient('{"ratings": {}}')

    # Pass legacy `max_tokens` via kwargs to ensure it's accepted and translated
    parsed, resp_text, resp_obj = chat_completion_parse_json(client, messages=[{"role": "user", "content": "x"}], max_tokens=2222)

    assert client.chat.completions.last_kwargs is not None
    # The underlying call should receive `max_completion_tokens` (translated)
    assert client.chat.completions.last_kwargs.get('max_completion_tokens') == 2222
    assert isinstance(parsed, dict) or parsed is None
