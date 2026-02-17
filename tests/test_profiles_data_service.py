import unittest

from services.profiles_data_service import get_profiles_data_service


class ProfilesDataServiceSmokeTest(unittest.TestCase):
    def test_service_surface(self):
        svc = get_profiles_data_service()
        # Basic surface exists
        self.assertTrue(hasattr(svc, 'list_profiles'))
        self.assertTrue(hasattr(svc, 'get_by_id'))
        self.assertTrue(hasattr(svc, 'add_profile'))
        # Calling list_profiles when no manager present should be safe
        res = svc.list_profiles()
        self.assertIsInstance(res, list)


if __name__ == '__main__':
    unittest.main()
