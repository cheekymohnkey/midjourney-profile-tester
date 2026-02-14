from typing import Dict, Any


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def score_v1_from_checks(checks: Dict[str, Any], rubric_weights: Dict[str, Any], *, base_score: float = 10.0) -> Dict[str, Any]:
    """Deterministic V1 scoring used by the app.

    Accepts structured `checks` (must/avoid/prefer) and returns a dictionary with
    computed score and derived metrics. This function is pure and easily unit
    testable.
    """
    must = checks.get("must") or []
    avoid = checks.get("avoid") or []
    prefer = checks.get("prefer") or []

    must_total = len(must)
    must_pass = sum(1 for item in must if bool(item.get("pass")))
    avoid_total = len(avoid)
    avoid_present = sum(1 for item in avoid if bool(item.get("present")))
    prefer_total = len(prefer)
    prefer_sum = sum((item.get("rating") or 0) for item in prefer)

    # Compute simple rates
    must_pass_rate = (must_pass / must_total) if must_total else 1.0
    avoid_clean_rate = (1.0 - (avoid_present / avoid_total)) if avoid_total else 1.0
    prefer_rate = (prefer_sum / (2.0 * prefer_total)) if prefer_total else 0.0

    # Score rules
    score = float(base_score)
    score -= (must_total - must_pass) * 2.0
    score -= avoid_present * 1.5
    for p in prefer:
        r = (p.get("rating") or 0)
        if r >= 2:
            score += 0.5
        elif r == 1:
            score += 0.25

    score = _clamp(score, 0.0, 10.0)

    # Affinity mapping
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

    return {
        "score_0_10": score,
        "affinity": affinity,
        "must_pass_rate": must_pass_rate,
        "avoid_clean_rate": avoid_clean_rate,
        "prefer_rate": prefer_rate,
        "counts": counts,
        "weights": rubric_weights or {},
    }
