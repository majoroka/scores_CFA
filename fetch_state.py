import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional


CACHE_DIR = Path(__file__).resolve().parent / "cache"
FETCH_STATE_PATH = CACHE_DIR / "fetch_state.json"

TECHNICAL_ERROR_TYPES = {
    "http_403",
    "http_429",
    "timeout",
    "network_error",
    "blocked_content",
    "empty_response",
}


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty_entry():
    return {
        "lastAttemptAt": None,
        "lastSuccessAt": None,
        "lastChangedAt": None,
        "lastErrorAt": None,
        "lastErrorType": None,
        "consecutiveFailures": 0,
        "technicalBackoffUntil": None,
    }


def load_fetch_state(path: Path = FETCH_STATE_PATH):
    if not path.exists():
        return {"competitions": {}}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"competitions": {}}
    if not isinstance(data, dict):
        return {"competitions": {}}
    data.setdefault("competitions", {})
    return data


def save_fetch_state(state: dict, path: Path = FETCH_STATE_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def get_competition_state(state: dict, competition_key: str):
    competitions = state.setdefault("competitions", {})
    competition_state = competitions.setdefault(competition_key, _empty_entry())
    competition_state.setdefault("fixtures", {})
    return competition_state


def get_fixture_state(state: dict, competition_key: str, fixture_id: str):
    competition_state = get_competition_state(state, competition_key)
    fixtures = competition_state.setdefault("fixtures", {})
    return fixtures.setdefault(str(fixture_id), _empty_entry())


def _apply_backoff(now: datetime, backoff_minutes: List[int], consecutive_failures: int):
    if not backoff_minutes:
        return None
    index = max(0, min(consecutive_failures - 1, len(backoff_minutes) - 1))
    target = now + timedelta(minutes=backoff_minutes[index])
    return target.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def update_fetch_entry(
    entry: dict,
    *,
    attempted_at: Optional[str] = None,
    success: bool = False,
    changed: bool = False,
    error_type: Optional[str] = None,
    backoff_minutes: Optional[List[int]] = None,
):
    timestamp = attempted_at or utc_now_iso()
    entry["lastAttemptAt"] = timestamp

    if success:
        entry["lastSuccessAt"] = timestamp
        entry["lastErrorAt"] = None
        entry["lastErrorType"] = None
        entry["consecutiveFailures"] = 0
        entry["technicalBackoffUntil"] = None
        if changed:
            entry["lastChangedAt"] = timestamp
        return

    if error_type:
        entry["lastErrorAt"] = timestamp
        entry["lastErrorType"] = error_type
    entry["consecutiveFailures"] = int(entry.get("consecutiveFailures", 0)) + 1

    if error_type in TECHNICAL_ERROR_TYPES:
        backoff = backoff_minutes or []
        now_dt = datetime.now(timezone.utc)
        entry["technicalBackoffUntil"] = _apply_backoff(
            now_dt,
            backoff,
            entry["consecutiveFailures"],
        )
    else:
        entry["technicalBackoffUntil"] = None


def snapshot_entry(entry: dict):
    return deepcopy(entry)
