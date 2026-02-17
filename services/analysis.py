from typing import Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _to_int(x) -> int:
    try:
        return int(x)
    except Exception:
        return 0

def _get_weights(rubric_weights: Dict[str, Any]) -> Dict[str, float]:
    """Extract and normalize weights. Defaults to 0.6/0.25/0.15."""
    w = rubric_weights or {}
    must_w = float(w.get("must", 0.6) or 0.6)
    avoid_w = float(w.get("avoid", 0.25) or 0.25)
    prefer_w = float(w.get("prefer", 0.15) or 0.15)

    # prevent negative weights
    must_w = max(0.0, must_w)
    avoid_w = max(0.0, avoid_w)
    prefer_w = max(0.0, prefer_w)

    s = must_w + avoid_w + prefer_w
    if s <= 0:
        # fallback to defaults
        return {"must": 0.6, "avoid": 0.25, "prefer": 0.15}

    # normalize to sum to 1.0
    return {"must": must_w / s, "avoid": avoid_w / s, "prefer": prefer_w / s}


def score_v1_from_checks(
    checks: Dict[str, Any],
    rubric_weights: Dict[str, Any],
    *,
    treat_empty_as_workable: bool = False
) -> Dict[str, Any]:
    """
    Deterministic V1 scoring (weighted-only).

    score_0_10 = 10 * (wm*must_pass_rate + wa*avoid_clean_rate + wp*prefer_rate)

    must_pass_rate: pass/total, default 1.0 if no MUST
    avoid_clean_rate: 1 - present/total, default 1.0 if no AVOID
    prefer_rate: prefer_sum/(2*prefer_total), default 0.0 if no PREFER
    """
    # Log incoming inputs (console)
    try:
        logger.info("score_v1_from_checks INPUTS: checks=%s, rubric_weights=%s, treat_empty_as_workable=%s",
                    json.dumps(checks, default=str), json.dumps(rubric_weights, default=str), treat_empty_as_workable)
    except Exception:
        # Fallback to repr if JSON serialization fails
        logger.info("score_v1_from_checks INPUTS (repr): checks=%r, rubric_weights=%r, treat_empty_as_workable=%r",
                    checks, rubric_weights, treat_empty_as_workable)
    # Also log a non-serialized raw input line for visibility
    try:
        logger.info("score_v1_from_checks RAW_INPUT: checks=%s rubric_weights=%s treat_empty_as_workable=%s",
                    json.dumps(checks, default=str), json.dumps(rubric_weights, default=str), treat_empty_as_workable)
    except Exception:
        logger.info("score_v1_from_checks RAW_INPUT (repr): checks=%r rubric_weights=%r treat_empty_as_workable=%r",
                    checks, rubric_weights, treat_empty_as_workable)

    must = checks.get("must") or []
    avoid = checks.get("avoid") or []
    prefer = checks.get("prefer") or []

    must_total = len(must)
    must_pass = sum(1 for item in must if bool(item.get("pass")))

    avoid_total = len(avoid)
    avoid_present = sum(1 for item in avoid if bool(item.get("present")))

    prefer_total = len(prefer)
    prefer_sum = sum(_to_int(item.get("rating")) for item in prefer)

    # Guard: no checks at all (e.g., VOID/no-rubric).
    # - If `treat_empty_as_workable` is True, return a non-scored workable result (score 0).
    # - Otherwise (default), treat empty-rubric as perfect (score 10.0) to preserve prior behavior.
    if must_total == 0 and avoid_total == 0 and prefer_total == 0:
        if treat_empty_as_workable:
            counts = {
                "must_total": 0, "must_pass": 0,
                "avoid_total": 0, "avoid_present": 0,
                "prefer_total": 0, "prefer_sum": 0,
            }
            result = {
                "score_0_10": 0.0,
                "affinity": "workable",
                "must_pass_rate": 1.0,
                "avoid_clean_rate": 1.0,
                "prefer_rate": 0.0,
                "counts": counts,
                "weights": _get_weights(rubric_weights),
            }
            try:
                logger.info("score_v1_from_checks OUTPUT: %s", json.dumps(result, default=str))
            except Exception:
                logger.info("score_v1_from_checks OUTPUT (repr): %r", result)
            return result
        # default: no checks -> perfect score (preserve prior behavior)
        counts = {
            "must_total": 0, "must_pass": 0,
            "avoid_total": 0, "avoid_present": 0,
            "prefer_total": 0, "prefer_sum": 0,
        }
        result = {
            "score_0_10": 10.0,
            "affinity": "native_fit",
            "must_pass_rate": 1.0,
            "avoid_clean_rate": 1.0,
            "prefer_rate": 0.0,
            "counts": counts,
            "weights": _get_weights(rubric_weights),
        }
        try:
            logger.info("score_v1_from_checks OUTPUT: %s", json.dumps(result, default=str))
        except Exception:
            logger.info("score_v1_from_checks OUTPUT (repr): %r", result)
        return result

    must_pass_rate = (must_pass / must_total) if must_total else 1.0
    avoid_clean_rate = (1.0 - (avoid_present / avoid_total)) if avoid_total else 1.0
    prefer_rate = (prefer_sum / (2.0 * prefer_total)) if prefer_total else 0.0

    weights = _get_weights(rubric_weights)
    composite = (
        weights["must"] * must_pass_rate +
        weights["avoid"] * avoid_clean_rate +
        weights["prefer"] * prefer_rate
    )

    score = _clamp(10.0 * composite, 0.0, 10.0)

    # Affinity mapping (same logic as before)
    if score >= 8.0 and must_pass_rate >= 0.80 and avoid_present <= 1:
        affinity = "native_fit"
    elif (5.0 <= score < 8.0) or (must_pass_rate >= 0.60):
        affinity = "workable"
    else:
        affinity = "resistant"

    counts = {
        "must_total": must_total,
        "must_pass": must_pass,
        "avoid_total": avoid_total,
        "avoid_present": avoid_present,
        "prefer_total": prefer_total,
        "prefer_sum": prefer_sum,
    }

    result = {
        "score_0_10": float(score),
        "affinity": affinity,
        "must_pass_rate": float(must_pass_rate),
        "avoid_clean_rate": float(avoid_clean_rate),
        "prefer_rate": float(prefer_rate),
        "counts": counts,
        "weights": weights,
    }
    try:
        logger.info("score_v1_from_checks OUTPUT: %s", json.dumps(result, default=str))
    except Exception:
        logger.info("score_v1_from_checks OUTPUT (repr): %r", result)
    return result
