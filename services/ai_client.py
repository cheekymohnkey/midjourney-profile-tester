import logging
import json
import re
from typing import Any, Dict, Optional, Tuple

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
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = 1500,
    **kwargs,
) -> Tuple[str, Any]:
    """Call the provided OpenAI client and return (response_text, response_obj).

    `client` should expose `chat.completions.create(...)` API.
    """
    response_obj = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs,
    )
    text = _extract_text_from_response_obj(response_obj)
    return text, response_obj


def chat_completion_parse_json(
    client: Any,
    messages: Any,
    *,
    model: str = "gpt-5-mini",
    temperature: float = 0.0,
    max_tokens: int = 2000,
    **kwargs,
) -> Tuple[Optional[Any], str, Any]:
    """Call chat completion and attempt to parse JSON from the returned text.

    Returns a tuple: (parsed_json_or_None, response_text, response_obj).
    Does NOT raise on parse failure — caller can decide how to handle None.
    """
    response_obj = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=max_tokens if 'max_completion_tokens' in kwargs else None,
        max_tokens=max_tokens,
        temperature=temperature,
        **{k: v for k, v in kwargs.items() if k != 'max_completion_tokens'},
    )

    response_text = _extract_text_from_response_obj(response_obj).strip()

    # Attempt JSON extraction; return None if it fails
    try:
        parsed = extract_json_from_text(response_text)
    except Exception:
        parsed = None

    return parsed, response_text, response_obj
