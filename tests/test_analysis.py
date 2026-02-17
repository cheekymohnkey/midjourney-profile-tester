from services.analysis import score_v1_from_checks


def test_score_base_no_checks():
    out = score_v1_from_checks({}, {})
    assert out['score_0_10'] == 10.0
    assert out['affinity'] in ('native_fit', 'workable', 'resistant')


def test_score_must_fail_penalty():
    checks = {"must": [{"label": "face_visible", "pass": False}], "avoid": [], "prefer": []}
    out = score_v1_from_checks(checks, {})
    # weighted scoring: one MUST failed -> low composite -> score 2.5 with default weights
    assert out['score_0_10'] == 2.5
    assert out['counts']['must_total'] == 1


def test_score_avoid_and_prefer():
    checks = {
        "must": [{"label": "face_visible", "pass": True}],
        "avoid": [{"label": "bad_bg", "present": True}],
        "prefer": [{"label": "vibrant", "rating": 2}, {"label": "texture", "rating": 1}]
    }
    out = score_v1_from_checks(checks, {})
    # weighted scoring: must_pass_rate=1, avoid_clean_rate=0, prefer_rate=3/(2*2)=0.75
    # composite = 0.6*1 + 0.25*0 + 0.15*0.75 = 0.7125 -> score = 7.125
    assert round(out['score_0_10'], 2) == 7.12
    assert out['counts']['avoid_present'] == 1
    assert out['counts']['prefer_sum'] == 3


def test_affinity_mapping():
    # Many musts passed -> high must_pass_rate -> workable/native_fit depending on score
    checks = {"must": [{"pass": True} for _ in range(5)], "avoid": [], "prefer": []}
    out = score_v1_from_checks(checks, {})
    assert out['must_pass_rate'] == 1.0
    assert 0.0 <= out['score_0_10'] <= 10.0
