import logging
import json
import re
from typing import Any, Dict, Optional, Tuple

from services.gpt_config import DEFAULT_MODEL

logger = logging.getLogger(__name__)


def _extract_text_from_response_obj(response_obj: Any) -> str:
    """Safely extract textual content from a ChatCompletion-like response object."""
    try:
        return getattr(response_obj.choices[0].message, "content", "") or ""
    except Exception:
        try:
            # Fallback for other response shapes
            return str(response_obj)
        except Exception:
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
        except Exception as e:
            logger.debug("Fence JSON parse failed: %s", e)
    if "```" in s:
        try:
            return json.loads(s.split("```")[1].split("```")[0].strip())
        except Exception:
            pass

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
    max_completion_tokens: int = 4000,
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

    response_obj = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=effective_max,
        **kwargs,
    )
    text = _extract_text_from_response_obj(response_obj)
    return text, response_obj


def chat_completion_parse_json(
    client: Any,
    messages: Any,
    *,
    model: str = DEFAULT_MODEL,
    max_completion_tokens: int = 4000,
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

    response_obj = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=effective_max,
        **kwargs,
    )

    response_text = _extract_text_from_response_obj(response_obj).strip()

    # Attempt JSON extraction; return None if it fails
    try:
        parsed = extract_json_from_text(response_text)
    except Exception:
        parsed = None

    return parsed, response_text, response_obj
