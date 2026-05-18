import unittest

from run_fetchers import (
    detect_degraded_from_sync_metadata,
    detect_publish_inconsistency,
    summarize_report,
)


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

    def test_detect_publish_inconsistency_when_parsed_changed_but_not_published(self):
        metadata = {'parsedChanged': True}
        self.assertTrue(detect_publish_inconsistency(metadata, published_changed=False))
        self.assertFalse(detect_publish_inconsistency(metadata, published_changed=True))

    def test_summarize_report_tracks_source_parsed_and_publish_counts(self):
        report = {
            'fetchers': [
                {
                    'success': True,
                    'degraded': False,
                    'changed': True,
                    'source_changed': True,
                    'parsed_changed': True,
                    'published_changed': True,
                    'publish_inconsistent': False,
                },
                {
                    'success': True,
                    'degraded': False,
                    'changed': False,
                    'source_changed': True,
                    'parsed_changed': True,
                    'published_changed': False,
                    'publish_inconsistent': True,
                },
            ]
        }
        summarize_report(report)
        self.assertEqual(report['success_count'], 2)
        self.assertEqual(report['changed_count'], 1)
        self.assertEqual(report['source_changed_count'], 2)
        self.assertEqual(report['parsed_changed_count'], 2)
        self.assertEqual(report['published_changed_count'], 1)
        self.assertEqual(report['publish_inconsistency_count'], 1)


if __name__ == '__main__':
    unittest.main()
