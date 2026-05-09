import unittest
from datetime import datetime
from unittest.mock import patch

from competition_configs import CompetitionConfig
from plan_fetchers import analyze_competition, build_plan


class FetchPlannerTests(unittest.TestCase):
    def setUp(self):
        self.config = CompetitionConfig(
            competition_url="https://example.test",
            output_file="data/example.json",
            main_cache_key="example_main",
            fixture_cache_prefix="example_fixture",
            key="infantis-a",
            title="Competição Exemplo",
            subtitle="Fase Exemplo",
            page_path="example.html",
        )
        self.now = datetime(2026, 5, 10, 11, 0, 0)

    def test_selects_today_pending_matches(self):
        payload = {
            "rounds": [
                {
                    "index": 1,
                    "matches": [
                        {"date": "10 mai", "time": "09:00", "homeScore": None, "awayScore": None},
                    ],
                }
            ]
        }
        with patch("plan_fetchers.load_payload", return_value=payload):
            result = analyze_competition(self.config, self.now)
        self.assertTrue(result["should_fetch"])
        self.assertEqual(result["state"], "today_pending")

    def test_skips_today_matches_outside_prematch_window(self):
        payload = {
            "rounds": [
                {
                    "index": 1,
                    "matches": [
                        {"date": "10 mai", "time": "18:00", "homeScore": None, "awayScore": None},
                    ],
                }
            ]
        }
        with patch("plan_fetchers.load_payload", return_value=payload):
            result = analyze_competition(self.config, self.now)
        self.assertFalse(result["should_fetch"])
        self.assertEqual(result["state"], "prematch_wait")

    def test_selects_historical_backfill(self):
        payload = {
            "rounds": [
                {
                    "index": 1,
                    "matches": [
                        {"date": "2 mai", "time": "16:00", "homeScore": None, "awayScore": None},
                    ],
                }
            ]
        }
        with patch("plan_fetchers.load_payload", return_value=payload):
            result = analyze_competition(self.config, self.now)
        self.assertTrue(result["should_fetch"])
        self.assertEqual(result["state"], "historical_backfill")

    def test_ignores_historical_backfill_outside_window(self):
        payload = {
            "rounds": [
                {
                    "index": 1,
                    "matches": [
                        {"date": "10 abr", "time": "16:00", "homeScore": None, "awayScore": None},
                    ],
                }
            ]
        }
        with patch("plan_fetchers.load_payload", return_value=payload):
            result = analyze_competition(self.config, self.now)
        self.assertFalse(result["should_fetch"])
        self.assertEqual(result["state"], "idle")

    def test_build_plan_is_idle_when_nothing_selected(self):
        analysis = {
            "competition_key": "infantis-a",
            "fetcher": "fetch_infantis_a.py",
            "should_fetch": False,
            "state": "idle",
            "today_pending_count": 0,
            "upcoming_today_count": 0,
            "historical_pending_count": 0,
            "reasons": ["idle"],
        }
        with patch("plan_fetchers.analyze_competition", return_value=analysis):
            plan = build_plan(self.now)
        self.assertEqual(plan["mode"], "idle")
        self.assertEqual(plan["selected_fetchers"], [])


if __name__ == "__main__":
    unittest.main()
