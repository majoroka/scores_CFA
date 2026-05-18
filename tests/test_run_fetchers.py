import unittest

from run_fetchers import detect_degraded_from_sync_metadata


class RunFetchersTests(unittest.TestCase):
    def test_detect_degraded_from_sync_metadata_uses_fallbacks(self):
        metadata = {
            'fallbackReuseCount': 1,
            'sourceHealth': {'status': 'degraded'},
            'fixtures': [],
        }
        self.assertTrue(detect_degraded_from_sync_metadata(metadata))

    def test_detect_degraded_from_sync_metadata_accepts_clean_metadata(self):
        metadata = {
            'fallbackReuseCount': 0,
            'sourceHealth': {'status': 'partial'},
            'fixtures': [{'fallbackUsed': False}],
        }
        self.assertFalse(detect_degraded_from_sync_metadata(metadata))


if __name__ == '__main__':
    unittest.main()
