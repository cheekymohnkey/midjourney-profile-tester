from typing import Dict, Any
from .analysis import score_v1_from_checks


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
    ambiguous_kw = ["unclear", "ambiguous", "uncertain", "hard to tell", "not clear", "difficult to see"]
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
        'weights': rubric_weights or {},
        'scoring_version': 'v1_group_weighted'
    }

    return {
        'score': score,
        'affinity': affinity,
        'confidence': confidence,
        'metrics_v1': metrics_v1,
    }
