import tempfile
import unittest
from pathlib import Path

from fetch_state import (
    get_competition_state,
    get_fixture_state,
    load_fetch_state,
    save_fetch_state,
    update_fetch_entry,
)


class FetchStateTests(unittest.TestCase):
    def test_update_fetch_entry_tracks_success_and_change(self):
        entry = {
            "lastAttemptAt": None,
            "lastSuccessAt": None,
            "lastChangedAt": None,
            "lastErrorAt": None,
            "lastErrorType": None,
            "consecutiveFailures": 0,
            "technicalBackoffUntil": None,
        }

        update_fetch_entry(
            entry,
            attempted_at="2026-05-17T10:00:00Z",
            success=True,
            changed=True,
        )

        self.assertEqual(entry["lastAttemptAt"], "2026-05-17T10:00:00Z")
        self.assertEqual(entry["lastSuccessAt"], "2026-05-17T10:00:00Z")
        self.assertEqual(entry["lastChangedAt"], "2026-05-17T10:00:00Z")
        self.assertEqual(entry["consecutiveFailures"], 0)
        self.assertIsNone(entry["lastErrorType"])

    def test_update_fetch_entry_applies_technical_backoff_on_failure(self):
        entry = {
            "lastAttemptAt": None,
            "lastSuccessAt": None,
            "lastChangedAt": None,
            "lastErrorAt": None,
            "lastErrorType": None,
            "consecutiveFailures": 0,
            "technicalBackoffUntil": None,
        }

        update_fetch_entry(
            entry,
            attempted_at="2026-05-17T10:00:00Z",
            success=False,
            error_type="http_429",
            backoff_minutes=[10, 20, 40],
        )

        self.assertEqual(entry["lastAttemptAt"], "2026-05-17T10:00:00Z")
        self.assertEqual(entry["lastErrorAt"], "2026-05-17T10:00:00Z")
        self.assertEqual(entry["lastErrorType"], "http_429")
        self.assertEqual(entry["consecutiveFailures"], 1)
        self.assertIsNotNone(entry["technicalBackoffUntil"])

    def test_load_and_save_fetch_state_preserve_competitions_and_fixtures(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "fetch_state.json"
            state = load_fetch_state(path)
            competition_state = get_competition_state(state, "juvenis")
            fixture_state = get_fixture_state(state, "juvenis", "640944")
            competition_state["lastAttemptAt"] = "2026-05-17T10:00:00Z"
            fixture_state["lastErrorType"] = "timeout"

            save_fetch_state(state, path)
            loaded = load_fetch_state(path)

            self.assertEqual(
                loaded["competitions"]["juvenis"]["lastAttemptAt"],
                "2026-05-17T10:00:00Z",
            )
            self.assertEqual(
                loaded["competitions"]["juvenis"]["fixtures"]["640944"]["lastErrorType"],
                "timeout",
            )


if __name__ == "__main__":
    unittest.main()
