import unittest

from run_fetchers import (
    detect_degraded_from_sync_metadata,
    detect_publish_inconsistency,
    load_plan_selections,
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

    def test_load_plan_selections_reads_fixture_ids_and_discovery_flag(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp_dir:
            plan_path = Path(temp_dir) / "fetch_plan.json"
            plan_path.write_text(json.dumps({
                "competitions": [
                    {
                        "fetcher": "fetch_fpf.py",
                        "fixture_ids_to_refresh": ["645299", "645300"],
                        "allow_full_discovery": False,
                    }
                ]
            }), encoding="utf-8")
            with patch("run_fetchers.PLAN_PATH", plan_path):
                selections = load_plan_selections()
        self.assertEqual(
            selections["fetch_fpf.py"],
            {
                "fixture_ids_to_refresh": ["645299", "645300"],
                "allow_full_discovery": False,
            },
        )


if __name__ == '__main__':
    unittest.main()
