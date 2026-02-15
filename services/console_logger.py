import json
import datetime
from typing import Any, Optional
from services.gpt_config import LOG_TO_CONSOLE


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + 'Z'


def _safe_len(obj: Any) -> int:
    try:
        if isinstance(obj, (str, bytes)):
            return len(obj)
        return len(json.dumps(obj))
    except Exception:
        return 0


def _sanitize_openai_messages(messages: Any) -> Any:
    """Remove or redact base64 image data inside message structures.

    Replaces any long base64 strings with a placeholder that includes length.
    Works on nested lists/dicts.
    """
    def _sanitize(value):
        if isinstance(value, str):
            # Heuristic: very long strings that look like data URLs
            if value.startswith('data:image') and 'base64,' in value:
                try:
                    b64 = value.split('base64,', 1)[1]
                    return f"<BASE64_REMOVED len={len(b64)}>"
                except Exception:
                    return "<BASE64_REMOVED>"
            # Also redact raw large base64 strings which may not have data: prefix
            if len(value) > 1000 and all(c.isalnum() or c in '+/=' for c in value[:200]):
                return f"<LONG_STRING_REMOVED len={len(value)}>"
            return value
        if isinstance(value, dict):
            return {k: _sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_sanitize(v) for v in value]
        return value

    return _sanitize(messages)


def log_openai_request(messages: Any, extra: Optional[dict] = None) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        sanitized = _sanitize_openai_messages(messages)
        payload_str = json.dumps(sanitized)
        print(f"[OPENAI REQUEST] time={_now()} payload_len={len(payload_str)} extras={json.dumps(extra or {})}")
        print(payload_str)
    except Exception as e:
        print(f"[OPENAI REQUEST] time={_now()} failed to serialize payload: {e}")


def log_openai_response(response_text: str, response_obj: Any = None) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        text_len = len(response_text or "")
        print(f"[OPENAI RESPONSE] time={_now()} text_len={text_len}")
        print(response_text)
    except Exception as e:
        print(f"[OPENAI RESPONSE] time={_now()} failed to log response: {e}")


def log_s3_write(path: str, length: int, response: Any = None) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        print(f"[S3 WRITE] time={_now()} path={path} bytes={length} response={str(response)[:1000]}")
    except Exception as e:
        print(f"[S3 WRITE] time={_now()} failed to log: {e}")


def log_file_write(path: str, length: int) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        print(f"[FILE WRITE] time={_now()} path={path} bytes={length}")
    except Exception as e:
        print(f"[FILE WRITE] time={_now()} failed to log: {e}")


def log_json_read(path: str, length: int) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        print(f"[JSON READ] time={_now()} path={path} bytes={length}")
    except Exception as e:
        print(f"[JSON READ] time={_now()} failed to log: {e}")


def log_cache_hit(key: str) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        print(f"[CACHE HIT] time={_now()} key={key}")
    except Exception as e:
        print(f"[CACHE HIT] time={_now()} failed to log: {e}")


def log_cache_miss(key: str) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        print(f"[CACHE MISS] time={_now()} key={key}")
    except Exception as e:
        print(f"[CACHE MISS] time={_now()} failed to log: {e}")


def log_cache_invalidate(key: str, old_meta: dict | None, new_meta: dict | None) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        print(f"[CACHE INVALIDATE] time={_now()} key={key} old_meta={json.dumps(old_meta or {})} new_meta={json.dumps(new_meta or {})}")
    except Exception as e:
        print(f"[CACHE INVALIDATE] time={_now()} failed to log: {e}")
