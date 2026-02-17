import unittest

from services.test_data_service import get_test_data_service
from services.score_service import apply_scores_to_result


class FakeTPM:
    def __init__(self, tests=None):
        self._tests = tests or []

    def load_tests(self, status_filter=None):
        if status_filter:
            return [t for t in self._tests if t.get('status') == status_filter]
        return list(self._tests)

    def get_test_by_title(self, title):
        for t in self._tests:
            if t.get('title') == title:
                return t
        return None


class TestScoreIntegration(unittest.TestCase):
    def setUp(self):
        self.tds = get_test_data_service()

    def test_score_uses_authoritative_weights(self):
        tests = [
            {
                'id': 't1',
                'guid': 'g1',
                'title': 'T1',
                'rubric': {'weights': {'must': 0.6, 'avoid': 0.25, 'prefer': 0.15}},
                'status': 'current'
            }
        ]
        fake = FakeTPM(tests=tests)
        self.tds._tpm = fake

        parsed = {'ratings': {'r1': {'checks': {'must': [], 'avoid': [], 'prefer': []}, 'test_id': 'g1'}}}
        out = apply_scores_to_result(parsed)
        r = out['ratings']['r1']
        self.assertEqual(r['score'], 10.0)
        self.assertIn('metrics_v1', r)
        weights = r['metrics_v1'].get('weights')
        self.assertIsInstance(weights, dict)
        # Expect the authoritative weights normalized to same values
        self.assertAlmostEqual(weights.get('must'), 0.6)
        self.assertAlmostEqual(weights.get('avoid'), 0.25)
        self.assertAlmostEqual(weights.get('prefer'), 0.15)

    def test_score_logs_critical_and_uses_defaults_when_missing(self):
        # Ensure no tests available
        fake = FakeTPM(tests=[])
        self.tds._tpm = fake

        parsed = {'ratings': {'rX': {'checks': {'must': [], 'avoid': [], 'prefer': []}, 'test_id': 'missing-guid'}}}
        with self.assertLogs('services.score_service', level='CRITICAL') as cm:
            out = apply_scores_to_result(parsed)
        # Verify critical message emitted
        found = any('Scoring lookup failed' in m for m in cm.output)
        self.assertTrue(found, f"Expected critical log about missing test, got: {cm.output}")

        r = out['ratings']['rX']
        # With no rubric, analysis._get_weights should supply defaults 0.6/0.25/0.15
        weights = r['metrics_v1'].get('weights')
        self.assertAlmostEqual(weights.get('must'), 0.6)
        self.assertAlmostEqual(weights.get('avoid'), 0.25)
        self.assertAlmostEqual(weights.get('prefer'), 0.15)


if __name__ == '__main__':
    unittest.main()
