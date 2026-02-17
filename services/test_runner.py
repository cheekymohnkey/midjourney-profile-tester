from pathlib import Path
import datetime
import json
from services.test_io import collect_test_image_paths
import logging

logger = logging.getLogger(__name__)


def run_test_for_profile(test: dict, prof: str, find_image_file, save_analysis):
    """Run analysis for a single test against a single profile.

    Returns a dict with keys: status ('ok','no_images','error'), profile_id, saved (bool), error (opt)
    """
    try:
        profile_id_check = prof if prof else 'baseline'
        analysis_file = Path("profile_analyses") / f"{profile_id_check}_analysis.json"
        # Load existing analysis (if any)
        try:
            from storage import get_storage
            storage = get_storage()
            analysis_data = storage.read_json(str(analysis_file)) or {"ratings": {}}
        except Exception:
            analysis_data = {"ratings": {}}

        test_title = test.get('title')

        # Use collect_test_image_paths to find images (supports void vs single-image)
        out_dir = Path(f"profile_results/{prof if prof else 'baseline'}")
        collected = collect_test_image_paths(out_dir, prof if prof else 'baseline', test_title, find_image_file)
        if not collected:
            return {"status": "no_images", "profile": profile_id_check, "saved": False}

        single_test = [(test_title, collected, {'Section': '', 'Prompt': '', 'Parameter Values': ''})]

        # Internal minimal single-test runner implementation (decoupled from UI batch function)
        try:
            import openai
            from openai import OpenAI
            import config
            from services.test_payload import prepare_test_message
            from services.ai_client import chat_completion_parse_json
            from services.gpt_config import DEFAULT_MODEL, DEFAULT_MAX_COMPLETION_TOKENS

            api_key = config.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set in .env file")

            client = OpenAI(api_key=api_key)

            # Load prompt template
            template_path = Path(__file__).parent.parent / "analysis_prompt_template.txt"
            prompt_text = ""
            try:
                prompt_text = template_path.read_text()
                prompt_text = prompt_text.replace("{profile_id}", str(profile_id_check))
            except Exception:
                prompt_text = f"Analysis for profile {profile_id_check}" + "\n\n**Test Images:**"

            message_content = [{"type": "text", "text": prompt_text + "\n\n**Test Images:**"}]

            # Prepare parts for the single test
            try:
                parts = prepare_test_message(test_title, collected, {'Section': '', 'Prompt': '', 'Parameter Values': ''}, test)
                if parts:
                    message_content.extend(parts)
            except Exception as e:
                logger.exception("prepare_test_message failed for %s: %s", test_title, e)

            parsed, response_text, response_obj = chat_completion_parse_json(
                client=client,
                messages=[{"role": "user", "content": message_content}],
                model=DEFAULT_MODEL,
                max_completion_tokens=DEFAULT_MAX_COMPLETION_TOKENS,
            )

            if parsed is None:
                dump_file = None
                try:
                    dump_dir = Path("profile_analyses/backups")
                    dump_dir.mkdir(parents=True, exist_ok=True)
                    dump_file = dump_dir / f"{profile_id_check}_bad_response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    dump_payload = {
                        "test": "single",
                        "profile": profile_id_check,
                        "prompt_preview": str(message_content)[:8000],
                        "response_text": response_text,
                    }
                    dump_file.write_text(json.dumps(dump_payload, indent=2))
                except Exception as e:
                    logger.exception("Failed to write single-test bad-response dump for %s: %s", profile_id_check, e)
                result = {"error": "no_json_response", "dump_file": str(dump_file) if dump_file is not None else None, "response_text_snippet": (response_text or '')[:2000]}
            else:
                result = parsed
                try:
                    from services.score_service import apply_scores_to_result
                    # Provide test-level default weights so scoring uses the test's rubric when
                    # the AI-parsed rating omits metrics/weights.
                    default_weights = (test.get('rubric', {}) or {}).get('weights', {})
                    result = apply_scores_to_result(result, default_weights=default_weights)
                except Exception:
                    logger.exception("Failed to apply deterministic scoring to single-test result")
        except Exception as e:
            return {"status": "error", "profile": profile_id_check, "saved": False, "error": str(e)}

        if not result or 'ratings' not in result:
            # If batch returned structured error info, surface it
            try:
                if isinstance(result, dict) and result.get('error'):
                    return {"status": "error", "profile": profile_id_check, "saved": False, "error": result.get('error'), "dump_file": result.get('dump_file'), "response_text_snippet": result.get('response_text_snippet')}
            except Exception as e:
                logger.exception("Error while checking structured error in result: %s", e)
            return {"status": "error", "profile": profile_id_check, "saved": False, "error": 'no_rating_returned'}

        # Resolve returned rating: prefer test title key, else any value
        returned_rating = None
        try:
            returned_rating = result['ratings'].get(test_title)
        except Exception as e:
            logger.exception("Error while fetching returned rating for test %s: %s", test_title, e)
            returned_rating = None

        if not returned_rating:
            try:
                vals = list(result.get('ratings', {}).values())
                if vals:
                    returned_rating = vals[0]
            except Exception as e:
                logger.exception("Error while extracting first rating value: %s", e)
                returned_rating = None

        if not returned_rating:
            return {"status": "error", "profile": profile_id_check, "saved": False, "error": 'empty_rating_object'}

        # Write rating under canonical key (prefer id/guid if available in test)
        write_key = test.get('id') or test.get('guid') or test_title
        analysis_data.setdefault('ratings', {})
        analysis_data['ratings'][write_key] = returned_rating
        # Remove legacy title key if different
        if write_key != test_title and test_title in analysis_data['ratings']:
            try:
                del analysis_data['ratings'][test_title]
            except Exception:
                pass

        # Save analysis with a timestamped backup of existing file when present
        try:
            try:
                from storage import get_storage
                storage = get_storage()
            except Exception:
                storage = None

            # If a prior analysis file existed, write a timestamped backup
            try:
                if storage is not None:
                    analysis_path = f"profile_analyses/{profile_id_check}_analysis.json"
                    prior = storage.read_json(analysis_path)
                    if prior:
                        # Ensure backup directory exists in storage APIs that support listing/writing
                        backup_dir = f"profile_analyses/backups"
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        backup_name = f"{profile_id_check}_analysis_backup_{timestamp}.json"
                        backup_path = f"{backup_dir}/{backup_name}"
                        try:
                            storage.write_json(backup_path, prior)
                        except Exception:
                            # Best-effort: if storage backend can't write nested paths, try top-level
                            try:
                                storage.write_json(str(Path('profile_analyses') / 'backups' / backup_name), prior)
                            except Exception:
                                pass
            except Exception:
                pass

            # Finally, save the new analysis via provided callback
            save_analysis(profile_id_check, analysis_data)
        except Exception as e:
            return {"status": "error", "profile": profile_id_check, "saved": False, "error": str(e)}

        return {"status": "ok", "profile": profile_id_check, "saved": True}

    except Exception as e:
        return {"status": "error", "profile": prof if prof else 'baseline', "saved": False, "error": str(e)}
