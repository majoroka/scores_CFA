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
            "lastAttemptAt": "2026-05-10T08:00:00Z",
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
        self.assertEqual(result["state"], "result_chase")
        self.assertTrue(result["due_now"])

    def test_selects_yesterday_pending_matches_as_active(self):
        payload = {
            "lastAttemptAt": "2026-05-10T00:00:00Z",
            "rounds": [
                {
                    "index": 1,
                    "matches": [
                        {"date": "9 mai", "time": "16:00", "homeScore": None, "awayScore": None},
                    ],
                }
            ]
        }
        with patch("plan_fetchers.load_payload", return_value=payload):
            result = analyze_competition(self.config, self.now)
        self.assertTrue(result["should_fetch"])
        self.assertEqual(result["state"], "result_chase")
        self.assertEqual(result["active_pending_count"], 1)

    def test_same_day_future_match_uses_calendar_watch_matchday(self):
        payload = {
            "lastAttemptAt": "2026-05-10T10:30:00+01:00",
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
        self.assertEqual(result["state"], "calendar_watch_matchday")
        self.assertFalse(result["due_now"])
        self.assertIsNotNone(result["next_recommended_fetch_at"])

    def test_same_day_future_match_enters_calendar_watch_when_check_is_due(self):
        payload = {
            "lastAttemptAt": "2026-05-10T00:00:00+01:00",
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
        self.assertTrue(result["should_fetch"])
        self.assertEqual(result["state"], "calendar_watch_matchday")
        self.assertTrue(result["due_now"])
        self.assertEqual(result["future_schedule_refresh_count"], 1)

    def test_future_match_within_week_enters_calendar_watch_near(self):
        payload = {
            "lastAttemptAt": "2026-05-10T00:00:00+01:00",
            "rounds": [
                {
                    "index": 1,
                    "matches": [
                        {"date": "14 mai", "time": "10:00", "homeScore": None, "awayScore": None},
                    ],
                }
            ]
        }
        with patch("plan_fetchers.load_payload", return_value=payload):
            result = analyze_competition(self.config, self.now)
        self.assertFalse(result["should_fetch"])
        self.assertEqual(result["state"], "calendar_watch_near")
        self.assertEqual(result["future_schedule_refresh_count"], 1)

    def test_future_match_beyond_week_enters_calendar_watch_far(self):
        payload = {
            "lastAttemptAt": "2026-05-10T00:00:00+01:00",
            "rounds": [
                {
                    "index": 1,
                    "matches": [
                        {"date": "20 mai", "time": "10:00", "homeScore": None, "awayScore": None},
                    ],
                }
            ]
        }
        with patch("plan_fetchers.load_payload", return_value=payload):
            result = analyze_competition(self.config, self.now)
        self.assertFalse(result["should_fetch"])
        self.assertEqual(result["state"], "calendar_watch_far")

    def test_selects_historical_backfill(self):
        payload = {
            "lastAttemptAt": "2026-05-10T00:00:00Z",
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
        self.assertEqual(result["recent_historical_pending_count"], 0)

    def test_recent_historical_backfill_waits_shorter_than_default_historical(self):
        payload = {
            "lastAttemptAt": "2026-05-10T10:30:00+01:00",
            "rounds": [
                {
                    "index": 1,
                    "matches": [
                        {"date": "8 mai", "time": "16:00", "homeScore": None, "awayScore": None},
                    ],
                }
            ]
        }
        with patch("plan_fetchers.load_payload", return_value=payload):
            result = analyze_competition(self.config, self.now)
        self.assertFalse(result["should_fetch"])
        self.assertEqual(result["state"], "result_chase")
        self.assertEqual(result["next_recommended_fetch_at"], "2026-05-10T12:30:00+01:00")

    def test_ignores_historical_backfill_outside_window(self):
        payload = {
            "lastAttemptAt": "2026-05-10T00:00:00Z",
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
            "due_now": False,
            "state": "idle",
            "functional_state": "idle",
            "technical_state": "healthy",
            "technical_backoff_level": 0,
            "active_pending_count": 0,
            "upcoming_today_count": 0,
            "future_schedule_refresh_count": 0,
            "recent_historical_pending_count": 0,
            "historical_pending_count": 0,
            "pending_today_count": 0,
            "pending_historical_count": 0,
            "next_scheduled_kickoff": None,
            "first_result_fetch_at": None,
            "last_meaningful_fetch_at": None,
            "next_recommended_fetch_at": None,
            "reasons": ["idle"],
        }
        with patch("plan_fetchers.analyze_competition", return_value=analysis):
            plan = build_plan(self.now)
        self.assertEqual(plan["mode"], "idle")
        self.assertEqual(plan["selected_fetchers"], [])

    def test_build_plan_prefers_result_chase_mode(self):
        analyses = [
            {
                "competition_key": "infantis-a",
                "fetcher": "fetch_infantis_a.py",
                "should_fetch": True,
                "due_now": True,
                "state": "historical_backfill",
                "functional_state": "historical_backfill",
                "technical_state": "healthy",
                "technical_backoff_level": 0,
                "active_pending_count": 0,
                "upcoming_today_count": 0,
                "future_schedule_refresh_count": 0,
                "recent_historical_pending_count": 0,
                "historical_pending_count": 2,
                "pending_today_count": 0,
                "pending_historical_count": 2,
                "next_scheduled_kickoff": None,
                "first_result_fetch_at": None,
                "last_meaningful_fetch_at": None,
                "next_recommended_fetch_at": "2026-05-10T06:00:00+01:00",
                "reasons": ["historical"],
            },
            {
                "competition_key": "juvenis",
                "fetcher": "fetch_juvenis.py",
                "should_fetch": True,
                "due_now": True,
                "state": "result_chase",
                "functional_state": "result_chase",
                "technical_state": "healthy",
                "technical_backoff_level": 0,
                "active_pending_count": 1,
                "upcoming_today_count": 0,
                "future_schedule_refresh_count": 0,
                "recent_historical_pending_count": 0,
                "historical_pending_count": 0,
                "pending_today_count": 1,
                "pending_historical_count": 0,
                "next_scheduled_kickoff": "2026-05-10T09:00:00+01:00",
                "first_result_fetch_at": "2026-05-10T10:50:00+01:00",
                "last_meaningful_fetch_at": "2026-05-10T10:00:00+01:00",
                "next_recommended_fetch_at": "2026-05-10T11:05:00+01:00",
                "reasons": ["active"],
            },
        ]
        competition_subset = [self.config, self.config]
        with patch("plan_fetchers.ALL_COMPETITIONS", competition_subset), patch("plan_fetchers.analyze_competition", side_effect=analyses):
            plan = build_plan(self.now)
        self.assertEqual(plan["mode"], "result_chase")


if __name__ == "__main__":
    unittest.main()
