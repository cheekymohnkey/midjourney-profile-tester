import math

from services.score_service import compute_score_and_metrics, compute_confidence_from_checks


def test_compute_score_with_empty_checks():
    out = compute_score_and_metrics({}, {})
    # No checks -> base score should remain 10.0
    assert math.isclose(out['score'], 10.0, rel_tol=1e-6)
    assert out['affinity'] == 'native_fit'
    assert math.isclose(out['confidence'], 0.85, rel_tol=1e-6)
    assert 'metrics_v1' in out


def test_compute_score_with_failures_and_prefer():
    checks = {
        'must': [
            {'label': 'face_visible', 'pass': False, 'evidence': 'no face visible'}
        ],
        'avoid': [
            {'label': 'overly_saturated', 'present': True, 'evidence': 'very saturated colors'}
        ],
        'prefer': [
            {'label': 'soft_lighting', 'rating': 2, 'evidence': 'soft directional light'}
        ]
    }

    out = compute_score_and_metrics(checks, {})
    # Weighted computation: must_pass_rate=0, avoid_clean_rate=0, prefer_rate=1.0
    # composite = 0.6*0 + 0.25*0 + 0.15*1 = 0.15 -> score = 1.5
    assert math.isclose(out['score'], 1.5, rel_tol=1e-6)
    assert out['affinity'] == 'resistant'
    # Confidence should be boosted because the MUST item has clear evidence
    assert math.isclose(out['confidence'], 0.9, rel_tol=1e-6)


def test_compute_confidence_ambiguous_and_low_clarity():
    checks = {
        'must': [
            {'label': 'gaze_direction', 'pass': True, 'evidence': 'gaze is unclear and ambiguous'},
            {'label': 'subject_size', 'pass': True, 'evidence': 'tiny subject, too small to tell'}
        ]
    }

    conf = compute_confidence_from_checks(checks)
    # ambiguous -> -0.10, low clarity -> -0.10 => base 0.85 - 0.20 = 0.65
    assert math.isclose(conf, 0.65, rel_tol=1e-6)
