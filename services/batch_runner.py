import logging
import json
import datetime
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


def batch_ai_rate_images(uploaded_tests: List[Tuple[str, object, dict]], profile_id: str, profile_label: str = "", existing_ratings: dict | None = None):
    """
    Minimal, service-side batch AI runner.

    This implementation is intentionally small: it prepares a compact
    message payload (using `services.test_payload.prepare_test_message`) and
    delegates parsing to `services.ai_client.chat_completion_parse_json`.

    It returns whatever JSON the AI parser returned (or a structured error
    dict on parse-failure) so callers (including the UI) can handle results
    the same way as the prior in-file implementation.
    """
    try:
        from services.test_payload import prepare_test_message
        from services.ai_client import chat_completion_parse_json
        from services.gpt_config import DEFAULT_MODEL, DEFAULT_MAX_COMPLETION_TOKENS
        from services.test_data_service import get_test_data_service
        tpm = get_test_data_service()
    except Exception as e:
        logger.exception("Failed to import batch helpers: %s", e)
        raise

    # Build a minimal prompt template
    try:
        template_path = Path(__file__).parent / "analysis_prompt_template.txt"
        prompt_template = template_path.read_text()
        prompt_text = prompt_template.replace("{profile_id}", str(profile_id))
    except Exception:
        prompt_text = f"Analyze images for profile {profile_id}.\n\n**Test Images:**"

    # Base message content from the template (or fallback)
    message_content = [{"type": "text", "text": prompt_text}]

    # Also include any project-level analysis instructions from
    # `analyse_test_result.txt` at the repo root (optional).
    try:
        extra_path = Path("analyse_test_result.txt")
        if extra_path.exists():
            extra_text = extra_path.read_text()
            # Keep the same message-part shape as other parts
            message_content.append({"type": "text", "text": "\n\n" + extra_text})
    except Exception:
        # Don't fail the whole batch if this extra file can't be read
        pass

    # Limit the batch to a reasonable size
    tests_to_send = (uploaded_tests or [])[:15]

    sendable = []
    skipped = []
    for name, path, row in tests_to_send:
        try:
            t_obj = tpm.get_by_title(name)
        except Exception:
            t_obj = None
        rubric = None
        try:
            if isinstance(t_obj, dict):
                rubric = t_obj.get('rubric')
        except Exception:
            rubric = None
        try:
            if not rubric and isinstance(row, dict):
                rubric = row.get('rubric')
        except Exception:
            pass

        if rubric:
            sendable.append((name, path, row, t_obj))
        else:
            skipped.append((name, path, row, t_obj))

    # If nothing to send to the LLM, return deterministic stubs for skipped tests
    if not sendable and skipped:
        result = {"ratings": {}}
        for name, path, row, test_obj in skipped:
            key = (test_obj.get('guid') or test_obj.get('id')) if isinstance(test_obj, dict) else name.replace(' ', '_').replace('/', '_')
            result['ratings'][key] = {
                'test_name': name,
                'checks': {'must': [], 'avoid': [], 'prefer': []},
                'failure_modes': [],
                'color_palette': {},
                'notes': 'No rubric provided; skipped LLM and recorded as signature-only.'
            }
        return result

    # Prepare message parts for each sendable test
    for name, filepath_or_list, row, test_obj in sendable:
        try:
            parts = prepare_test_message(name, filepath_or_list, row, test_obj)
            if parts:
                message_content.extend(parts)
        except Exception:
            logger.exception("prepare_test_message failed for %s", name)

    # Call the AI parser. Many tests monkeypatch this function and pass
    # `client=None`. In normal runtime, create a default OpenAI client when
    # one isn't provided so we don't attempt to call methods on `None`.
    try:
        # Default to an initialized OpenAI client if caller passed None
        client_to_use = None
        try:
            # Import lazily to avoid heavy deps during test monkeypatches
            from openai import OpenAI  # type: ignore
            import config
            api_key = getattr(config, 'OPENAI_API_KEY', None)
            if api_key:
                client_to_use = OpenAI(api_key=api_key)
            else:
                # No API key configured — fail fast with clear log so callers
                # (UI) get a descriptive error instead of an AttributeError later.
                logger.critical("OpenAI API key not configured; cannot perform AI batch analysis")
                raise RuntimeError("OPENAI_API_KEY not set; enable AI features or configure key in .env")
        except Exception:
            # If we couldn't construct a client, fall back to None and let
            # the called parser handle test-time monkeypatches or raise.
            client_to_use = None

        parsed, response_text, response_obj = chat_completion_parse_json(
            client=client_to_use,
            messages=[{"role": "user", "content": message_content}],
            model=DEFAULT_MODEL,
            max_completion_tokens=DEFAULT_MAX_COMPLETION_TOKENS,
        )
    except Exception as e:
        logger.exception("AI client error: %s", e)
        raise

    if parsed is None:
        # Write a small debug dump and return a structured error for callers
        try:
            dump_dir = Path("profile_analyses/backups")
            dump_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            dump_file = dump_dir / f"{profile_id or 'baseline'}_bad_response_{ts}.json"
            dump_payload = {
                'time': datetime.datetime.utcnow().isoformat() + 'Z',
                'response_text_snippet': (response_text or '')[:10000],
            }
            dump_file.write_text(json.dumps(dump_payload, indent=2))
        except Exception:
            dump_file = None
        return {"error": "no_json_response", "dump_file": str(dump_file) if dump_file is not None else None, "response_text_snippet": (response_text or '')[:2000]}

    try:
        # Normalize AI outputs: older prompts return an array of outputs
        # (one per test). The scoring service expects a dict with a
        # `ratings` mapping keyed by a test identifier. Convert lists
        # into that shape so downstream scoring is deterministic.
        if isinstance(parsed, list):
            ratings = {}
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                key = item.get('test_guid') or item.get('guid') or item.get('test_id') or item.get('test_name')
                if not key:
                    # fallback to test_name or a generated key
                    key = item.get('test_name') or f"test_{len(ratings)+1}"
                ratings[str(key)] = item
            parsed = {'ratings': ratings}

        # Delegate scoring to the scoring service which will lookup authoritative
        # rubrics itself; do not inject test rubrics/weights here.
        from services.score_service import apply_scores_to_result
        parsed = apply_scores_to_result(parsed)
    except Exception:
        logger.exception("Failed to apply deterministic scoring to parsed result")

    return parsed
