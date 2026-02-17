import json
import datetime
import os
import logging
from typing import Any, Optional
from services.gpt_config import LOG_TO_CONSOLE

logger = logging.getLogger(__name__)

# Read S3 console logging flag at call time so it can be toggled at runtime
def _s3_console_logs_enabled() -> bool:
    # Default to false so S3-related logs remain off unless explicitly enabled
    return os.environ.get('S3_CONSOLE_LOGS', 'false').lower() in ('1', 'true', 'yes')


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
        logger.info("[OPENAI REQUEST] time=%s payload_len=%d extras=%s", _now(), len(payload_str), json.dumps(extra or {}))
        logger.info(payload_str)
    except Exception as e:
        logger.exception("[OPENAI REQUEST] time=%s failed to serialize payload", _now())


def log_openai_response(response_text: str, response_obj: Any = None) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        text_len = len(response_text or "")
        logger.info("[OPENAI RESPONSE] time=%s text_len=%d", _now(), text_len)
        logger.info(response_text)
    except Exception as e:
        logger.exception("[OPENAI RESPONSE] time=%s failed to log response", _now())


def log_s3_write(path: str, length: int, response: Any = None) -> None:
    if not LOG_TO_CONSOLE:
        return
    if not _s3_console_logs_enabled():
        return
    try:
        logger.info("[S3 WRITE] time=%s path=%s bytes=%d response=%s", _now(), path, length, str(response)[:1000])
    except Exception as e:
        logger.exception("[S3 WRITE] time=%s failed to log", _now())


def log_file_write(path: str, length: int) -> None:
    if not LOG_TO_CONSOLE:
        return
    try:
        logger.info("[FILE WRITE] time=%s path=%s bytes=%d", _now(), path, length)
    except Exception as e:
        logger.exception("[FILE WRITE] time=%s failed to log", _now())


def log_json_read(path: str, length: int) -> None:
    if not LOG_TO_CONSOLE:
        return
    # gate JSON read logs behind S3 logging toggle as they are often noisy when using S3
    if not _s3_console_logs_enabled():
        return
    try:
        logger.info("[JSON READ] time=%s path=%s bytes=%d", _now(), path, length)
    except Exception as e:
        logger.exception("[JSON READ] time=%s failed to log", _now())


def log_cache_hit(key: str) -> None:
    # Cache-hit logging can be noisy; enable via env var MJPT_LOG_CACHE_HITS=1
    if not LOG_TO_CONSOLE:
        return
    if not _s3_console_logs_enabled():
        return
    if os.environ.get("MJPT_LOG_CACHE_HITS", "0") != "1":
        return
    try:
        logger.info("[CACHE HIT] time=%s key=%s", _now(), key)
    except Exception as e:
        logger.exception("[CACHE HIT] time=%s failed to log", _now())


def log_cache_miss(key: str) -> None:
    if not LOG_TO_CONSOLE:
        return
    if not _s3_console_logs_enabled():
        return
    try:
        logger.info("[CACHE MISS] time=%s key=%s", _now(), key)
    except Exception as e:
        logger.exception("[CACHE MISS] time=%s failed to log", _now())


def log_cache_invalidate(key: str, old_meta: dict | None, new_meta: dict | None) -> None:
    if not LOG_TO_CONSOLE:
        return
    if not _s3_console_logs_enabled():
        return
    try:
        logger.info("[CACHE INVALIDATE] time=%s key=%s old_meta=%s new_meta=%s", _now(), key, json.dumps(old_meta or {}), json.dumps(new_meta or {}))
    except Exception as e:
        logger.exception("[CACHE INVALIDATE] time=%s failed to log", _now())
