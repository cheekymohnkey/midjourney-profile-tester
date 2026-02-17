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
            from services.results_data_service import get_results_data_service
            rsvc = get_results_data_service()
            analysis_data = rsvc.read_analysis(profile_id_check) or {"ratings": {}}
        except Exception:
            analysis_data = {"ratings": {}}

        test_title = test.get('title')

        # Use collect_test_image_paths to find images (supports void vs single-image)
        out_dir = Path(f"profile_results/{prof if prof else 'baseline'}")
        collected = collect_test_image_paths(out_dir, prof if prof else 'baseline', test_title, find_image_file)
        if not collected:
            return {"status": "no_images", "profile": profile_id_check, "saved": False}

        single_test = [(test_title, collected, {'Section': '', 'Prompt': '', 'Parameter Values': ''})]

        # Internal minimal single-test runner implementation: delegate to batch runner
        try:
            from services.batch_runner import batch_ai_rate_images

            # existing_ratings passed so the batch runner can skip already-rated tests
            try:
                result = batch_ai_rate_images(single_test, profile_id_check, existing_ratings=analysis_data.get('ratings', {}))
            except Exception as e:
                # Propagate batch/AI errors to caller
                return {"status": "error", "profile": profile_id_check, "saved": False, "error": str(e)}

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
            # Prefer caller-provided save_analysis callback so tests and UI can intercept
            try:
                save_analysis(profile_id_check, analysis_data)
            except Exception:
                # If callback fails or is not intended, fall back to ResultsDataService
                try:
                    from services.results_data_service import get_results_data_service
                    rsvc = get_results_data_service()
                    rsvc.write_analysis(profile_id_check, analysis_data, make_backup=True)
                except Exception:
                    logger.exception("Failed to persist analysis for %s", profile_id_check)
        except Exception as e:
            return {"status": "error", "profile": profile_id_check, "saved": False, "error": str(e)}

        return {"status": "ok", "profile": profile_id_check, "saved": True}

    except Exception as e:
        return {"status": "error", "profile": prof if prof else 'baseline', "saved": False, "error": str(e)}
