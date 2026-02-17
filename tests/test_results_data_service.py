import unittest

from services.results_data_service import get_results_data_service


class ResultsDataServiceSmokeTest(unittest.TestCase):
    def test_service_surface(self):
        svc = get_results_data_service()
        self.assertTrue(hasattr(svc, 'list_results_for_profile'))
        self.assertTrue(hasattr(svc, 'get_result_by_id'))
        self.assertTrue(hasattr(svc, 'add_result'))
        # Should return empty list by default
        res = svc.list_results_for_profile('nonexistent')
        self.assertIsInstance(res, list)


if __name__ == '__main__':
    unittest.main()
