from services.analysis import score_v1_from_checks


def test_score_base_no_checks():
    out = score_v1_from_checks({}, {})
    assert out['score_0_10'] == 10.0
    assert out['affinity'] in ('native_fit', 'workable', 'resistant')


def test_score_must_fail_penalty():
    checks = {"must": [{"label": "face_visible", "pass": False}], "avoid": [], "prefer": []}
    out = score_v1_from_checks(checks, {})
    # one must failed => -2 from 10
    assert out['score_0_10'] == 8.0
    assert out['counts']['must_total'] == 1


def test_score_avoid_and_prefer():
    checks = {
        "must": [{"label": "face_visible", "pass": True}],
        "avoid": [{"label": "bad_bg", "present": True}],
        "prefer": [{"label": "vibrant", "rating": 2}, {"label": "texture", "rating": 1}]
    }
    out = score_v1_from_checks(checks, {})
    # start 10, -1.5 for avoid, +0.5 for rating 2, +0.25 for rating 1 => 9.25
    assert round(out['score_0_10'], 2) == 9.25
    assert out['counts']['avoid_present'] == 1
    assert out['counts']['prefer_sum'] == 3


def test_affinity_mapping():
    # Many musts passed -> high must_pass_rate -> workable/native_fit depending on score
    checks = {"must": [{"pass": True} for _ in range(5)], "avoid": [], "prefer": []}
    out = score_v1_from_checks(checks, {})
    assert out['must_pass_rate'] == 1.0
    assert 0.0 <= out['score_0_10'] <= 10.0
