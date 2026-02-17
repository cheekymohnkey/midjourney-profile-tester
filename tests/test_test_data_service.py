import unittest

from services.test_data_service import get_test_data_service


class FakeTPM:
    def __init__(self, tests=None):
        self._tests = tests or []
        self.saved = None

    def load_tests(self, status_filter=None):
        if status_filter:
            return [t for t in self._tests if t.get('status') == status_filter]
        return list(self._tests)

    def get_test_by_title(self, title):
        for t in self._tests:
            if t.get('title') == title:
                return t
        return None

    def save_tests(self, tests):
        self.saved = list(tests)


class TestTestDataService(unittest.TestCase):
    def setUp(self):
        # prepare a fake TPM with sample tests
        self.sample_tests = [
            {'id': 't1', 'guid': 'g1', 'title': 'Title One', 'rubric': {'weights': {'must': 0.5}}, 'status': 'current'},
            {'id': 't2', 'guid': 'g2', 'title': 'Title Two', 'rubric': {}, 'status': 'archived'},
        ]
        self.fake = FakeTPM(tests=self.sample_tests)
        self.tds = get_test_data_service()
        # inject fake test_prompts_manager
        self.tds._tpm = self.fake

    def test_list_tests_returns_all(self):
        out = self.tds.list_tests()
        self.assertEqual(len(out), 2)

    def test_list_tests_with_filter(self):
        out = self.tds.list_tests(status_filter='current')
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['id'], 't1')

    def test_get_by_guid(self):
        t = self.tds.get_by_guid('g1')
        self.assertIsNotNone(t)
        self.assertEqual(t['id'], 't1')

    def test_get_by_id(self):
        t = self.tds.get_by_id('t2')
        self.assertIsNotNone(t)
        self.assertEqual(t['guid'], 'g2')

    def test_get_by_title_uses_helper(self):
        # FakeTPM implements get_test_by_title which should be used
        t = self.tds.get_by_title('Title Two')
        self.assertIsNotNone(t)
        self.assertEqual(t['id'], 't2')

    def test_save_tests_calls_tpm(self):
        new_tests = [{'id': 'x', 'guid': 'gx', 'title': 'X'}]
        self.tds.save_tests(new_tests)
        self.assertIsNotNone(self.fake.saved)
        self.assertEqual(self.fake.saved[0]['id'], 'x')


if __name__ == '__main__':
    unittest.main()
