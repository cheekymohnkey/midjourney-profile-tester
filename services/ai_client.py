import logging
import json
import re
import pathlib
import datetime
from typing import Any, Dict, Optional, Tuple

from services.gpt_config import DEFAULT_MODEL, DEFAULT_MAX_COMPLETION_TOKENS
from services.console_logger import log_openai_request, log_openai_response

logger = logging.getLogger(__name__)


def _extract_text_from_response_obj(response_obj: Any) -> str:
    """Safely extract textual content from a ChatCompletion-like response object."""
    try:
        return getattr(response_obj.choices[0].message, "content", "") or ""
    except Exception:
        logger.exception("Failed to extract message content from response_obj; falling back to str()")
        try:
            # Fallback for other response shapes
            return str(response_obj)
        except Exception:
            logger.exception("Failed to stringify response_obj while extracting text")
            return ""


def extract_json_from_text(response_text: str) -> Any:
    """Try to extract JSON object/array from a text blob.

    Handles fenced code blocks (```json ... ``` and ``` ... ```), plain JSON,
    or JSON substring embedded inside other text.
    Returns parsed JSON on success or raises ValueError.
    """
    if not isinstance(response_text, str):
        raise ValueError("response_text must be a string")

    s = response_text.strip()

    # Strip fenced JSON blocks if present
    if "```json" in s:
        try:
            return json.loads(s.split("```json")[1].split("```")[0].strip())
        except Exception:
            logger.exception("Fence JSON parse failed")
    if "```" in s:
        try:
            return json.loads(s.split("```")[1].split("```")[0].strip())
        except Exception:
            logger.exception("Fenced code block JSON parse failed")

    # Try to parse entire string as JSON
    try:
        return json.loads(s)
    except Exception:
        pass

    # Try to find a JSON object or array substring
    # Find first `{` and last `}` and try to parse
    first_obj = s.find("{")
    last_obj = s.rfind("}")
    if first_obj != -1 and last_obj != -1 and last_obj > first_obj:
        candidate = s[first_obj:last_obj + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # Try array
    first_arr = s.find("[")
    last_arr = s.rfind("]")
    if first_arr != -1 and last_arr != -1 and last_arr > first_arr:
        candidate = s[first_arr:last_arr + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # No JSON found
    raise ValueError("No JSON object found in response text")


def chat_completion_to_text(
    client: Any,
    messages: Any,
    *,
    model: str = DEFAULT_MODEL,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
    **kwargs,
) -> Tuple[str, Any]:
    """Call the provided OpenAI client and return (response_text, response_obj).

    `client` should expose `chat.completions.create(...)` API.

    Defensive behaviour: if the caller passed `max_completion_tokens` inside `kwargs`,
    prefer that value and avoid passing the same keyword twice (which raises).
    """
    # Prefer explicit kwargs if provided by the caller; accept either
    # `max_completion_tokens` (newer parameter) or `max_tokens` (legacy).
    effective_max = kwargs.pop('max_completion_tokens', kwargs.pop('max_tokens', max_completion_tokens))

    # Log outbound payload (sanitized) and then call API; also write a sanitized debug dump for inspection
    try:
        log_openai_request(messages, extra={"model": model, "max_completion_tokens": effective_max})
    except Exception:
        logger.exception("log_openai_request failed")
    try:
        # Always attempt to write a small sanitized request dump for debugging
        from services.console_logger import _sanitize_openai_messages
        dump_dir = pathlib.Path("profile_analyses/backups")
        dump_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dump_file = dump_dir / f"openai_request_{ts}.json"
        try:
            sanitized = _sanitize_openai_messages(messages)
            payload = {"time": datetime.datetime.utcnow().isoformat() + 'Z', "model": model, "max_completion_tokens": effective_max, "messages_preview": sanitized}
            dump_file.write_text(json.dumps(payload, indent=2))
        except Exception:
            logger.exception("Failed to write sanitized openai request dump; attempting minimal dump")
            try:
                dump_file.write_text(json.dumps({"time": ts, "model": model}))
            except Exception:
                logger.exception("Failed to write minimal openai request dump")
    except Exception:
        logger.exception("Failed while preparing openai request dump")

    response_obj = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=effective_max,
        **kwargs,
    )
    text = _extract_text_from_response_obj(response_obj)

    try:
        log_openai_response(text, response_obj=response_obj)
    except Exception:
        logger.exception("log_openai_response failed")
    try:
        # Write sanitized response dump for debugging
        from services.console_logger import _sanitize_openai_messages
        dump_dir = pathlib.Path("profile_analyses/backups")
        dump_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        resp_file = dump_dir / f"openai_response_{ts}.json"
        try:
            usage = getattr(response_obj, 'usage', None) or (response_obj.get('usage') if isinstance(response_obj, dict) else None)
            choices = getattr(response_obj, 'choices', None)
            finish_reason = None
            if choices and len(choices) > 0:
                ch = choices[0]
                finish_reason = getattr(ch, 'finish_reason', None) or (ch.get('finish_reason') if isinstance(ch, dict) else None)
            payload = {"time": datetime.datetime.utcnow().isoformat() + 'Z', "response_text_snippet": (text or '')[:10000], "finish_reason": finish_reason, "usage": usage}
            resp_file.write_text(json.dumps(payload, indent=2))
        except Exception:
            logger.exception("Failed to write detailed openai response dump; attempting minimal dump")
            try:
                resp_file.write_text(json.dumps({"time": ts}))
            except Exception:
                logger.exception("Failed to write minimal openai response dump")
    except Exception:
        logger.exception("Failed while preparing openai response dump")

    return text, response_obj


def chat_completion_parse_json(
    client: Any,
    messages: Any,
    *,
    model: str = DEFAULT_MODEL,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
    **kwargs,
) -> Tuple[Optional[Any], str, Any]:
    """Call chat completion and attempt to parse JSON from the returned text.

    Returns a tuple: (parsed_json_or_None, response_text, response_obj).
    Does NOT raise on parse failure — caller can decide how to handle None.

    Defensive behaviour: prefer `max_completion_tokens` from kwargs when present
    and ensure we never pass the same keyword argument twice to the client.
    """
    # Accept both `max_completion_tokens` and legacy `max_tokens` from kwargs.
    effective_max = kwargs.pop('max_completion_tokens', kwargs.pop('max_tokens', max_completion_tokens))

    # Log outbound payload (sanitized) before calling the API
    try:
        log_openai_request(messages, extra={"model": model, "max_completion_tokens": effective_max})
    except Exception:
        logger.exception("log_openai_request failed")

    response_obj = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=effective_max,
        **kwargs,
    )

    response_text = _extract_text_from_response_obj(response_obj).strip()
    try:
        # Log full response text (user requested). Keep response_obj available for callers.
        log_openai_response(response_text, response_obj=response_obj)
    except Exception:
        logger.exception("log_openai_response failed")

    # Attempt JSON extraction; return None if it fails
    try:
        parsed = extract_json_from_text(response_text)
    except Exception:
        parsed = None
        # Write a lightweight debug dump so callers can inspect finish reason and token usage
        try:
            dump_dir = pathlib.Path("profile_analyses/backups")
            dump_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            dump_file = dump_dir / f"bad_parse_{ts}.json"
            # Try to extract finish_reason and usage if present
            finish_reason = None
            usage = None
            try:
                choices = getattr(response_obj, 'choices', None)
                if choices and len(choices) > 0:
                    # Some clients store finish_reason in different places
                    ch = choices[0]
                    finish_reason = getattr(ch, 'finish_reason', None) or (ch.get('finish_reason') if isinstance(ch, dict) else None)
            except Exception:
                finish_reason = None
            try:
                usage = getattr(response_obj, 'usage', None) or (response_obj.get('usage') if isinstance(response_obj, dict) else None)
            except Exception:
                usage = None

            payload = {
                'time': datetime.datetime.utcnow().isoformat() + 'Z',
                'response_text_snippet': (response_text or '')[:10000],
                'finish_reason': finish_reason,
                'usage': usage,
                'response_obj_repr': None,
            }
            try:
                payload['response_obj_repr'] = str(response_obj)[:20000]
            except Exception:
                payload['response_obj_repr'] = None

            dump_file.write_text(json.dumps(payload, indent=2))
            logger.error("Wrote parse-failure debug dump: %s", str(dump_file))
        except Exception:
            logger.exception("Failed to write parse-failure debug dump")

    return parsed, response_text, response_obj
