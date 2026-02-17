import logging
import json
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
        import test_prompts_manager as tpm
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

    message_content = [{"type": "text", "text": prompt_text}]

    # Limit the batch to a reasonable size
    tests_to_send = (uploaded_tests or [])[:15]

    sendable = []
    skipped = []
    for name, path, row in tests_to_send:
        try:
            t_obj = tpm.get_test_by_title(name)
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

    # Call the AI parser. Many tests monkeypatch this function, so we pass a
    # simple `client=None` here — the parser implementation can ignore it.
    try:
        parsed, response_text, response_obj = chat_completion_parse_json(
            client=None,
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
        # Ensure parsed ratings carry test rubric weights when missing. The AI parser
        # may omit `metrics_v1.weights`; inject from `sendable` test objects before
        # applying deterministic scoring.
        for name, filepath_or_list, row, test_obj in sendable:
            try:
                key = (test_obj.get('guid') or test_obj.get('id')) if isinstance(test_obj, dict) else name.replace(' ', '_').replace('/', '_')
                ratings = parsed.get('ratings', {}) if isinstance(parsed, dict) else {}
                rating = ratings.get(key)
                if rating:
                    metrics = rating.get('metrics_v1') or rating.get('metrics') or {}
                    if not metrics.get('weights'):
                        w = (test_obj.get('rubric', {}) or {}).get('weights', {})
                        metrics['weights'] = w
                        rating['metrics_v1'] = metrics
                        ratings[key] = rating
                        parsed['ratings'] = ratings
            except Exception:
                # Non-fatal: continue injecting other tests
                pass

        from services.score_service import apply_scores_to_result
        parsed = apply_scores_to_result(parsed)
    except Exception:
        logger.exception("Failed to apply deterministic scoring to parsed result")

    return parsed
