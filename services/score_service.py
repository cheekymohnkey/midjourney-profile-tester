from typing import Dict, Any
from .analysis import score_v1_from_checks
from .test_data_service import get_test_data_service
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


def apply_scores_to_result(parsed_result: dict) -> dict:
    """Compute scores for each rating using authoritative rubric lookup.

    The scoring service accepts only the checks (pass/fail evidence) and a
    test identifier (guid/id/title). It looks up the authoritative rubric and
    weights from `test_prompts.json` via `test_prompts_manager` using that
    identifier. If the lookup fails the failure is logged at CRITICAL level.

    This function will not trust or use any client-supplied weights.
    """
    if not isinstance(parsed_result, dict):
        return parsed_result

    ratings = parsed_result.get('ratings') or {}
    for key, val in list(ratings.items()):
        try:
            checks = val.get('checks') or {'must': [], 'avoid': [], 'prefer': []}

            # Determine which identifier the client passed. Prefer explicit
            # `test_id`/`guid` fields, otherwise fall back to the rating key.
            guid = val.get('test_id') or val.get('guid') or key

            # Lookup authoritative test/rubric via centralized TestDataService
            test_obj = None
            weights: Dict[str, Any] = {}
            try:
                tds = get_test_data_service()
                test_obj = tds.get_by_guid(guid) or tds.get_by_id(guid) or tds.get_by_title(guid)
            except Exception:
                test_obj = None

            if not test_obj:
                _safe_log(logger.critical, "Scoring lookup failed for test id/guid='%s' rating_key='%s'", guid, key)
                weights = {}
            else:
                weights = (test_obj.get('rubric') or {}).get('weights') or {}

            # Only compute if score missing
            if 'score' not in val or val.get('score') is None:
                out = compute_score_and_metrics(checks, weights)
                val['score'] = out.get('score')
                val['affinity'] = out.get('affinity')
                val['confidence'] = out.get('confidence')
                val['metrics_v1'] = out.get('metrics_v1')
                ratings[key] = val
        except Exception:
            _safe_log(logger.exception, "Failed to compute score for rating %s", key)

    parsed_result['ratings'] = ratings
    return parsed_result
