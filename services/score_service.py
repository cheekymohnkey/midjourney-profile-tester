from typing import Dict, Any
from .analysis import score_v1_from_checks
import logging
import sys
import traceback

logger = logging.getLogger(__name__)


def _safe_log(func, *args, **kwargs):
    """Call a logging function safely; on failure print traceback to stderr."""
    try:
        func(*args, **kwargs)
    except Exception:
        traceback.print_exc(file=sys.stderr)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _evidence_contains_any(evidence: str, keywords) -> bool:
    if not evidence:
        return False
    e = evidence.lower()
    for k in keywords:
        if k in e:
            return True
    return False


def compute_confidence_from_checks(checks: Dict[str, Any]) -> float:
    """Heuristic confidence calculation based on check evidence strings.

    Rules (approximation of the doc):
    - base 0.85
    - ambiguous MUST cues -> -0.10 (evidence contains words like unclear/ambiguous/uncertain)
    - multiple MUST items clearly satisfied/violated -> +0.05 (all MUST either pass or all fail)
    - low clarity (blur/low resolution/small subject) -> -0.10
    """
    base = 0.85
    adj = 0.0

    must = checks.get("must") or []
    # ambiguous keywords
    ambiguous_kw = [
        "unclear",
        "ambiguous",
        "uncertain",
        "hard to tell",
        "not clear",
        "difficult to see",
        "insufficient visible cues",
        "insufficient cues",
        "cannot determine",
        "not visible",
    ]
    low_clarity_kw = ["blur", "blurry", "low res", "low resolution", "small subject", "tiny subject", "too small", "pixel", "out of focus"]

    # Check MUST evidence for ambiguous phrases
    ambiguous_count = 0
    clear_count = 0
    for m in must:
        ev = (m.get("evidence") or "")
        if _evidence_contains_any(ev, ambiguous_kw):
            ambiguous_count += 1
        elif _evidence_contains_any(ev, low_clarity_kw):
            # low clarity also reduces confidence
            adj -= 0.10
        else:
            # treat as clear evidence
            clear_count += 1

    if ambiguous_count > 0:
        adj -= 0.10

    # If all MUST items are clearly satisfied or clearly failed (no ambiguous evidence), boost confidence
    if must and ambiguous_count == 0 and (clear_count == len(must)):
        adj += 0.05

    conf = _clamp(base + adj, 0.60, 0.95)
    return round(conf, 3)


def compute_score_and_metrics(checks: Dict[str, Any], rubric_weights: Dict[str, Any]) -> Dict[str, Any]:
    """Compute deterministic score, affinity and confidence from structured checks.

    Returns a dict with keys: score (0-10 float), affinity, confidence, metrics_v1.
    """
    v1 = score_v1_from_checks(checks, rubric_weights)

    score = float(v1.get("score_0_10", 0.0))
    affinity = v1.get("affinity", "resistant")

    confidence = compute_confidence_from_checks(checks)

    metrics_v1 = {
        'must_pass_rate': round(float(v1['must_pass_rate']), 3),
        'avoid_clean_rate': round(float(v1['avoid_clean_rate']), 3),
        'prefer_rate': round(float(v1['prefer_rate']), 3),
        'counts': v1['counts'],
        'weights': v1.get('weights') or (rubric_weights or {}),
        'scoring_version': 'v1_weighted_only'
    }

    result = {
        'score': score,
        'affinity': affinity,
        'confidence': confidence,
        'metrics_v1': metrics_v1,
    }

    # Emit an informational log so scoring outputs appear in console logs
    _safe_log(logger.info, "Computed score: %s, affinity: %s, confidence: %s", score, affinity, confidence)
    _safe_log(logger.debug, "Scoring details: %s", result)

    return result


def apply_scores_to_result(parsed_result: dict, default_weights: dict | None = None) -> dict:
    """Ensure each rating in `parsed_result['ratings']` has computed score/metrics.

    This mutates and returns the parsed_result for convenience. If a rating
    already contains a `score` field, it is left unchanged.
    """
    if not isinstance(parsed_result, dict):
        return parsed_result

    ratings = parsed_result.get('ratings') or {}
    for key, val in list(ratings.items()):
        try:
            checks = val.get('checks') or {'must': [], 'avoid': [], 'prefer': []}
            # Enforce authoritative weights from `test_prompts.json` via test_prompts_manager.
            # Do NOT trust client-supplied weights. Look up the test by key (title/id/guid)
            # and use its `rubric.weights`. If unavailable, fall back to provided default_weights.
            weights = {}
            test_obj = None
            try:
                import test_prompts_manager as tpm
                try:
                    test_obj = tpm.get_test_by_title(key)
                except Exception:
                    test_obj = None
                if not test_obj:
                    try:
                        tests = tpm.load_tests()
                        for t in tests:
                            if (t.get('id') == key) or (t.get('guid') == key):
                                test_obj = t
                                break
                    except Exception:
                        test_obj = None
                if test_obj:
                    weights = (test_obj.get('rubric', {}) or {}).get('weights') or {}
            except Exception:
                weights = {}

            # Log what authoritative test/rubric (if any) was found for this rating key
            _safe_log(
                logger.info,
                "Lookup for rating '%s' returned test id=%s title=%s rubric.weights=%s",
                key,
                (test_obj.get('id') if test_obj else None),
                (test_obj.get('title') if test_obj else None),
                weights,
            )
            _safe_log(logger.debug, "Full retrieved test object for '%s': %s", key, test_obj)
            # If authoritative weights not found, use caller-provided default_weights
            initial_client_weights = (val.get('metrics_v1') or {}).get('weights') or {}
            if not weights:
                weights = default_weights or {}
            # Determine source of the weights for logging/audit
            if test_obj and weights:
                weight_source = 'authoritative'
            elif (not test_obj) and default_weights:
                weight_source = 'default'
            elif initial_client_weights:
                weight_source = 'client_supplied'
            else:
                weight_source = 'none'
            # Overwrite any client-supplied weights in the rating so saved analysis is authoritative
            try:
                mv = val.get('metrics_v1') or {}
                mv['weights'] = weights
                val['metrics_v1'] = mv
            except Exception:
                pass
            # Print/log enforcement/source so it's visible in server logs
            _safe_log(logger.info, "Enforced test-level weights for rating '%s' (source=%s): %s", key, weight_source, weights)
            # Only compute if score missing
            if 'score' not in val or val.get('score') is None:
                # Dump everything the scoring algorithm needs before scoring
                must_list = (test_obj.get('rubric') or {}).get('must') if test_obj else None
                avoid_list = (test_obj.get('rubric') or {}).get('avoid') if test_obj else None
                prefer_list = (test_obj.get('rubric') or {}).get('prefer') if test_obj else None
                must_total = len(checks.get('must') or [])
                avoid_total = len(checks.get('avoid') or [])
                prefer_total = len(checks.get('prefer') or [])
                _safe_log(logger.info, "[SCORER PREP] rating='%s'", key)
                _safe_log(logger.info, "  test_id=%s title=%s", (test_obj.get('id') if test_obj else None), (test_obj.get('title') if test_obj else None))
                _safe_log(logger.info, "  rubric.must=%s", must_list)
                _safe_log(logger.info, "  rubric.avoid=%s", avoid_list)
                _safe_log(logger.info, "  rubric.prefer=%s", prefer_list)
                _safe_log(logger.info, "  initial_client_weights=%s", initial_client_weights)
                _safe_log(logger.info, "  default_weights=%s", default_weights)
                _safe_log(logger.info, "  resolved_weights=%s", weights)
                _safe_log(logger.info, "  weight_source=%s", weight_source)
                _safe_log(logger.debug, "  checks=%s", checks)
                _safe_log(logger.info, "  counts: must_total=%d avoid_total=%d prefer_total=%d", must_total, avoid_total, prefer_total)
                _safe_log(logger.info, "  treat_empty_as_workable=%s", False)
                out = compute_score_and_metrics(checks, weights)
                # merge computed fields into rating
                val['score'] = out.get('score')
                val['affinity'] = out.get('affinity')
                val['confidence'] = out.get('confidence')
                val['metrics_v1'] = out.get('metrics_v1')
                ratings[key] = val
        except Exception:
            _safe_log(logger.exception, "Failed to compute score for rating %s", key)

    parsed_result['ratings'] = ratings
    return parsed_result
