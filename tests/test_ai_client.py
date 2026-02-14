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
