import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from build_calendar import build_match_datetime
from competition_configs import ALL_COMPETITIONS, CompetitionConfig


ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
PLAN_PATH = CACHE_DIR / "fetch_plan.json"
LOCAL_TZ = ZoneInfo("Europe/Lisbon")

RESULT_PUBLISH_DELAY_MINUTES = int(os.environ.get("RESULT_PUBLISH_DELAY_MINUTES", "110"))
RESULT_CHASE_SHORT_RETRY_MINUTES = int(os.environ.get("RESULT_CHASE_SHORT_RETRY_MINUTES", "15"))
RESULT_CHASE_SHORT_WINDOW_MINUTES = int(os.environ.get("RESULT_CHASE_SHORT_WINDOW_MINUTES", "60"))
RESULT_CHASE_MEDIUM_RETRY_MINUTES = int(os.environ.get("RESULT_CHASE_MEDIUM_RETRY_MINUTES", "30"))
RESULT_CHASE_MEDIUM_WINDOW_HOURS = int(os.environ.get("RESULT_CHASE_MEDIUM_WINDOW_HOURS", "6"))
RESULT_CHASE_LONG_RETRY_HOURS = int(os.environ.get("RESULT_CHASE_LONG_RETRY_HOURS", "2"))
RESULT_CHASE_LONG_WINDOW_HOURS = int(os.environ.get("RESULT_CHASE_LONG_WINDOW_HOURS", "48"))
HISTORICAL_LOOKBACK_DAYS = int(os.environ.get("HISTORICAL_LOOKBACK_DAYS", "14"))
RECENT_HISTORICAL_WINDOW_DAYS = int(os.environ.get("RECENT_HISTORICAL_WINDOW_DAYS", "2"))
RECENT_HISTORICAL_RETRY_HOURS = int(os.environ.get("RECENT_HISTORICAL_RETRY_HOURS", "2"))
HISTORICAL_RETRY_HOURS = int(os.environ.get("HISTORICAL_RETRY_HOURS", "6"))
CALENDAR_WATCH_LOOKAHEAD_DAYS = int(os.environ.get("CALENDAR_WATCH_LOOKAHEAD_DAYS", "14"))
CALENDAR_WATCH_MATCHDAY_HOURS = int(os.environ.get("CALENDAR_WATCH_MATCHDAY_HOURS", "24"))
CALENDAR_WATCH_NEAR_DAYS = int(os.environ.get("CALENDAR_WATCH_NEAR_DAYS", "7"))
CALENDAR_WATCH_FAR_DAYS = int(os.environ.get("CALENDAR_WATCH_FAR_DAYS", "14"))
CALENDAR_WATCH_MATCHDAY_CADENCE_HOURS = int(os.environ.get("CALENDAR_WATCH_MATCHDAY_CADENCE_HOURS", "2"))
CALENDAR_WATCH_CLOSE_CADENCE_HOURS = int(os.environ.get("CALENDAR_WATCH_CLOSE_CADENCE_HOURS", "6"))
CALENDAR_WATCH_NEAR_CADENCE_HOURS = int(os.environ.get("CALENDAR_WATCH_NEAR_CADENCE_HOURS", "12"))
CALENDAR_WATCH_FAR_CADENCE_HOURS = int(os.environ.get("CALENDAR_WATCH_FAR_CADENCE_HOURS", "24"))
TECHNICAL_BACKOFF_MINUTES = tuple(
    int(item.strip())
    for item in os.environ.get("TECHNICAL_BACKOFF_MINUTES", "10,20,40").split(",")
    if item.strip()
)

FETCHER_BY_KEY = {
    "seniores": "fetch_seniores.py",
    "juniores": "fetch_juniores.py",
    "juvenis": "fetch_juvenis.py",
    "iniciados-a": "fetch_iniciados_a.py",
    "iniciados-b": "fetch_iniciados_b.py",
    "infantis-a": "fetch_infantis_a.py",
    "infantis-b": "fetch_infantis_b.py",
    "infantis-c": "fetch_infantis_c.py",
    "benjamins-a1": "fetch_benjamins_a1.py",
    "benjamins-a2": "fetch_benjamins_a2.py",
    "benjamins-b": "fetch_benjamins_b.py",
    "benjamins-bb": "fetch_benjamins_bb.py",
    "feminino-sub19": "fetch_feminino_sub19.py",
    "feminino-sub17": "fetch_feminino_sub17.py",
    "feminino-sub15": "fetch_feminino_sub15.py",
}

SELECTIVE_REFRESH_PILOT_KEYS = {"seniores"}
SELECTIVE_REFRESH_MAX_FIXTURE_IDS = 2


def load_payload(config: CompetitionConfig) -> Optional[dict]:
    output_path = ROOT / config.output_file
    if not output_path.exists():
        return None
    with open(output_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def has_score(match: dict) -> bool:
    return isinstance(match.get("homeScore"), int) and isinstance(match.get("awayScore"), int)


def valid_payload(payload: Optional[dict]) -> bool:
    return bool(
        payload and
        isinstance(payload.get("rounds"), list) and
        payload["rounds"] and
        all(isinstance(round_data.get("matches"), list) for round_data in payload["rounds"])
    )


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.astimezone(LOCAL_TZ)


def isoformat_or_none(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def classify_technical_state(payload: dict) -> tuple[str, int]:
    source_health = payload.get("sourceHealth", {}) if isinstance(payload.get("sourceHealth"), dict) else {}
    fallback_reuse_count = source_health.get("fallbackReuseCount", 0)
    if not isinstance(fallback_reuse_count, int):
        fallback_reuse_count = 0
    if fallback_reuse_count > 0:
        return "blocked", fallback_reuse_count
    return "healthy", 0


def last_fetch_reference(payload: dict) -> Optional[datetime]:
    for field_name in ("lastAttemptAt", "lastSuccessAt", "lastChangedAt", "lastUpdatedAt"):
        parsed = parse_timestamp(payload.get(field_name))
        if parsed is not None:
            return parsed
    return None


def technical_backoff_minutes(level: int) -> int:
    if not TECHNICAL_BACKOFF_MINUTES:
        return 10
    capped_level = min(max(level, 1), len(TECHNICAL_BACKOFF_MINUTES))
    return TECHNICAL_BACKOFF_MINUTES[capped_level - 1]


def compute_next_fetch_for_result_chase(
    match_dt: datetime,
    last_fetch_at: Optional[datetime],
    technical_state: str,
    technical_level: int,
) -> datetime:
    first_fetch_at = match_dt + timedelta(minutes=RESULT_PUBLISH_DELAY_MINUTES)
    if technical_state != "healthy" and last_fetch_at is not None:
        return last_fetch_at + timedelta(minutes=technical_backoff_minutes(technical_level))
    if last_fetch_at is None or last_fetch_at < first_fetch_at:
        return first_fetch_at

    short_window_end = first_fetch_at + timedelta(minutes=RESULT_CHASE_SHORT_WINDOW_MINUTES)
    if last_fetch_at < short_window_end:
        return last_fetch_at + timedelta(minutes=RESULT_CHASE_SHORT_RETRY_MINUTES)

    medium_window_end = match_dt + timedelta(hours=RESULT_CHASE_MEDIUM_WINDOW_HOURS)
    if last_fetch_at < medium_window_end:
        return last_fetch_at + timedelta(minutes=RESULT_CHASE_MEDIUM_RETRY_MINUTES)

    long_window_end = match_dt + timedelta(hours=RESULT_CHASE_LONG_WINDOW_HOURS)
    if last_fetch_at < long_window_end:
        return last_fetch_at + timedelta(hours=RESULT_CHASE_LONG_RETRY_HOURS)

    return last_fetch_at + timedelta(hours=HISTORICAL_RETRY_HOURS)


def compute_next_fetch_for_historical_match(
    match_dt: datetime,
    last_fetch_at: Optional[datetime],
    now: datetime,
    technical_state: str,
    technical_level: int,
) -> datetime:
    if technical_state != "healthy" and last_fetch_at is not None:
        return last_fetch_at + timedelta(minutes=technical_backoff_minutes(technical_level))
    if last_fetch_at is None:
        return now
    recent_historical_cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=RECENT_HISTORICAL_WINDOW_DAYS)
    if match_dt >= recent_historical_cutoff:
        return last_fetch_at + timedelta(hours=RECENT_HISTORICAL_RETRY_HOURS)
    return last_fetch_at + timedelta(hours=HISTORICAL_RETRY_HOURS)


def compute_next_fetch_for_future_match(
    match_dt: datetime,
    last_fetch_at: Optional[datetime],
    now: datetime,
    technical_state: str,
    technical_level: int,
) -> datetime:
    if technical_state != "healthy" and last_fetch_at is not None:
        return last_fetch_at + timedelta(minutes=technical_backoff_minutes(technical_level))
    if last_fetch_at is None:
        return now

    hours_until_match = max(0, (match_dt - now).total_seconds() / 3600.0)
    days_until_match = hours_until_match / 24.0

    if hours_until_match <= CALENDAR_WATCH_MATCHDAY_HOURS:
        cadence_hours = CALENDAR_WATCH_MATCHDAY_CADENCE_HOURS
    elif days_until_match <= 3:
        cadence_hours = CALENDAR_WATCH_CLOSE_CADENCE_HOURS
    elif days_until_match <= CALENDAR_WATCH_NEAR_DAYS:
        cadence_hours = CALENDAR_WATCH_NEAR_CADENCE_HOURS
    else:
        cadence_hours = CALENDAR_WATCH_FAR_CADENCE_HOURS
    return last_fetch_at + timedelta(hours=cadence_hours)


def classify_calendar_watch_state(match_dt: datetime, now: datetime) -> str:
    hours_until_match = max(0, (match_dt - now).total_seconds() / 3600.0)
    days_until_match = hours_until_match / 24.0
    if hours_until_match <= CALENDAR_WATCH_MATCHDAY_HOURS:
        return "calendar_watch_matchday"
    if days_until_match <= CALENDAR_WATCH_NEAR_DAYS:
        return "calendar_watch_near"
    return "calendar_watch_far"


def select_fixture_ids_to_refresh(config: CompetitionConfig, payload: dict, now: datetime) -> list[str]:
    if config.key not in SELECTIVE_REFRESH_PILOT_KEYS:
        return []

    historical_cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
    calendar_watch_cutoff = now + timedelta(days=CALENDAR_WATCH_LOOKAHEAD_DAYS)
    candidates = []

    for round_data in payload.get("rounds", []):
        fixture_id = str(round_data.get("fixtureId") or "").strip()
        if not fixture_id:
            continue

        best_priority = None
        best_match_dt = None
        for match in round_data.get("matches", []):
            match_dt = build_match_datetime(match)
            if not match_dt or match_dt < historical_cutoff or match_dt > calendar_watch_cutoff:
                continue

            if match_dt <= now and not has_score(match):
                if match_dt + timedelta(hours=RESULT_CHASE_LONG_WINDOW_HOURS) >= now:
                    priority = 1
                else:
                    priority = 2
            elif match_dt > now:
                if (match_dt - now).total_seconds() / 3600.0 <= CALENDAR_WATCH_MATCHDAY_HOURS:
                    priority = 3
                elif (match_dt - now).days < CALENDAR_WATCH_NEAR_DAYS:
                    priority = 4
                else:
                    priority = 5
            else:
                continue

            if best_priority is None or priority < best_priority or (priority == best_priority and match_dt < best_match_dt):
                best_priority = priority
                best_match_dt = match_dt

        if best_priority is not None and best_match_dt is not None:
            candidates.append((best_priority, best_match_dt, fixture_id))

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    selected = []
    seen = set()
    for _, _, fixture_id in candidates:
        if fixture_id in seen:
            continue
        seen.add(fixture_id)
        selected.append(fixture_id)
        if len(selected) >= SELECTIVE_REFRESH_MAX_FIXTURE_IDS:
            break
    return selected


def analyze_competition(config: CompetitionConfig, now: datetime) -> dict:
    if now.tzinfo is None:
        now = now.replace(tzinfo=LOCAL_TZ)
    else:
        now = now.astimezone(LOCAL_TZ)

    payload = load_payload(config)
    fetcher = FETCHER_BY_KEY[config.key]

    if not valid_payload(payload):
        return {
            "competition_key": config.key,
            "fetcher": fetcher,
            "should_fetch": True,
            "due_now": True,
            "state": "missing_payload",
            "functional_state": "missing_payload",
            "technical_state": "unknown",
            "technical_backoff_level": 0,
            "active_pending_count": 0,
            "upcoming_today_count": 0,
            "historical_pending_count": 0,
            "pending_today_count": 0,
            "pending_historical_count": 0,
            "future_schedule_refresh_count": 0,
            "next_scheduled_kickoff": None,
            "first_result_fetch_at": None,
            "last_meaningful_fetch_at": None,
            "next_recommended_fetch_at": now.isoformat(),
            "reasons": ["payload ausente ou inválido"],
        }

    last_fetch_at = last_fetch_reference(payload)
    technical_state, technical_level = classify_technical_state(payload)
    fixture_ids_to_refresh = select_fixture_ids_to_refresh(config, payload, now)
    allow_full_discovery = config.key not in SELECTIVE_REFRESH_PILOT_KEYS

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    historical_cutoff = today_start - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
    recent_historical_cutoff = today_start - timedelta(days=RECENT_HISTORICAL_WINDOW_DAYS)
    calendar_watch_cutoff = now + timedelta(days=CALENDAR_WATCH_LOOKAHEAD_DAYS)

    upcoming_today_count = 0
    active_pending_count = 0
    recent_historical_pending_count = 0
    historical_pending_count = 0
    future_schedule_refresh_count = 0
    next_scheduled_kickoff = None
    first_result_fetch_at = None
    next_recommended_fetch_at = None
    future_watch_state = None

    for round_data in payload["rounds"]:
        for match in round_data.get("matches", []):
            if has_score(match):
                continue

            match_dt = build_match_datetime(match)
            if not match_dt:
                continue

            if next_scheduled_kickoff is None or (match_dt >= now and match_dt < next_scheduled_kickoff):
                next_scheduled_kickoff = match_dt

            if match_dt < historical_cutoff:
                continue

            first_fetch_at = match_dt + timedelta(minutes=RESULT_PUBLISH_DELAY_MINUTES)
            if first_result_fetch_at is None or first_fetch_at < first_result_fetch_at:
                first_result_fetch_at = first_fetch_at

            if match_dt > now:
                if match_dt > calendar_watch_cutoff:
                    continue
                future_schedule_refresh_count += 1
                candidate_next_fetch = compute_next_fetch_for_future_match(
                    match_dt,
                    last_fetch_at,
                    now,
                    technical_state,
                    technical_level,
                )
                if next_recommended_fetch_at is None or candidate_next_fetch < next_recommended_fetch_at:
                    next_recommended_fetch_at = candidate_next_fetch
                candidate_state = classify_calendar_watch_state(match_dt, now)
                if future_watch_state is None:
                    future_watch_state = candidate_state
                elif future_watch_state == "calendar_watch_far" and candidate_state != "calendar_watch_far":
                    future_watch_state = candidate_state
                elif future_watch_state == "calendar_watch_near" and candidate_state == "calendar_watch_matchday":
                    future_watch_state = candidate_state
                if match_dt.date() == now.date():
                    upcoming_today_count += 1
                continue

            if now < first_fetch_at:
                upcoming_today_count += 1
                future_schedule_refresh_count += 1
                candidate_next_fetch = first_fetch_at
                if next_recommended_fetch_at is None or candidate_next_fetch < next_recommended_fetch_at:
                    next_recommended_fetch_at = candidate_next_fetch
                future_watch_state = "calendar_watch_matchday"
                continue

            result_chase_cutoff = match_dt + timedelta(hours=RESULT_CHASE_LONG_WINDOW_HOURS)
            if now <= result_chase_cutoff:
                active_pending_count += 1
                candidate_next_fetch = compute_next_fetch_for_result_chase(
                    match_dt,
                    last_fetch_at,
                    technical_state,
                    technical_level,
                )
                if next_recommended_fetch_at is None or candidate_next_fetch < next_recommended_fetch_at:
                    next_recommended_fetch_at = candidate_next_fetch
                continue

            historical_pending_count += 1
            if match_dt >= recent_historical_cutoff:
                recent_historical_pending_count += 1
            candidate_next_fetch = compute_next_fetch_for_historical_match(
                match_dt,
                last_fetch_at,
                now,
                technical_state,
                technical_level,
            )
            if next_recommended_fetch_at is None or candidate_next_fetch < next_recommended_fetch_at:
                next_recommended_fetch_at = candidate_next_fetch

    pending_today_count = active_pending_count + upcoming_today_count
    reasons = []
    state = "idle"
    should_fetch = False
    due_now = False

    if active_pending_count > 0:
        state = "result_chase"
        due_now = next_recommended_fetch_at is not None and now >= next_recommended_fetch_at
        should_fetch = due_now
        reasons.append(f"{active_pending_count} jogo(s) dentro da janela ativa de resultados")
    elif future_schedule_refresh_count > 0:
        state = future_watch_state or "calendar_watch_near"
        due_now = next_recommended_fetch_at is not None and now >= next_recommended_fetch_at
        should_fetch = due_now
        reasons.append(f"{future_schedule_refresh_count} jogo(s) futuros na vigilância de calendário")
    elif recent_historical_pending_count > 0:
        state = "recent_historical_backfill"
        due_now = next_recommended_fetch_at is not None and now >= next_recommended_fetch_at
        should_fetch = due_now
        reasons.append(f"{recent_historical_pending_count} jogo(s) históricos recentes sem resultado")
    elif historical_pending_count > 0:
        state = "historical_backfill"
        due_now = next_recommended_fetch_at is not None and now >= next_recommended_fetch_at
        should_fetch = due_now
        reasons.append(f"{historical_pending_count} jogo(s) históricos sem resultado na janela de recuperação")
    else:
        reasons.append("sem jogos pendentes elegíveis para fetch")

    if config.key in SELECTIVE_REFRESH_PILOT_KEYS:
        if fixture_ids_to_refresh:
            reasons.append(f"piloto seletivo: {len(fixture_ids_to_refresh)} fixtureId(s) elegíveis")
        else:
            reasons.append("piloto seletivo: sem fixtureIds elegíveis")
        should_fetch = should_fetch and bool(fixture_ids_to_refresh)

    return {
        "competition_key": config.key,
        "fetcher": fetcher,
        "should_fetch": should_fetch,
        "due_now": due_now,
        "state": state,
        "functional_state": state,
        "technical_state": technical_state,
        "technical_backoff_level": technical_level,
        "active_pending_count": active_pending_count,
        "upcoming_today_count": upcoming_today_count,
        "future_schedule_refresh_count": future_schedule_refresh_count,
        "recent_historical_pending_count": recent_historical_pending_count,
        "historical_pending_count": historical_pending_count,
        "pending_today_count": pending_today_count,
        "pending_historical_count": historical_pending_count,
        "next_scheduled_kickoff": isoformat_or_none(next_scheduled_kickoff),
        "first_result_fetch_at": isoformat_or_none(first_result_fetch_at),
        "last_meaningful_fetch_at": isoformat_or_none(last_fetch_at),
        "next_recommended_fetch_at": isoformat_or_none(next_recommended_fetch_at),
        "fixture_ids_to_refresh": fixture_ids_to_refresh,
        "allow_full_discovery": allow_full_discovery,
        "reasons": reasons,
    }


def build_plan(now: Optional[datetime] = None) -> dict:
    reference_now = now or datetime.now(LOCAL_TZ)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=LOCAL_TZ)
    else:
        reference_now = reference_now.astimezone(LOCAL_TZ)

    analyses = [analyze_competition(config, reference_now) for config in ALL_COMPETITIONS]
    selected = [item["fetcher"] for item in analyses if item["should_fetch"]]

    states = {item["state"] for item in analyses if item["should_fetch"]}
    if "missing_payload" in states:
        mode = "missing_payload"
    elif "result_chase" in states:
        mode = "result_chase"
    elif "calendar_watch_matchday" in states:
        mode = "calendar_watch_matchday"
    elif "calendar_watch_near" in states:
        mode = "calendar_watch_near"
    elif "calendar_watch_far" in states:
        mode = "calendar_watch_far"
    elif "recent_historical_backfill" in states:
        mode = "recent_historical_backfill"
    elif "historical_backfill" in states:
        mode = "historical_backfill"
    else:
        mode = "idle"

    next_due_candidates = [
        item["next_recommended_fetch_at"]
        for item in analyses
        if item.get("next_recommended_fetch_at")
    ]
    next_due_candidates.sort()

    return {
        "generated_at": reference_now.isoformat(),
        "mode": mode,
        "selected_fetchers": selected,
        "selected_count": len(selected),
        "competitions": analyses,
        "result_publish_delay_minutes": RESULT_PUBLISH_DELAY_MINUTES,
        "result_chase_short_retry_minutes": RESULT_CHASE_SHORT_RETRY_MINUTES,
        "result_chase_short_window_minutes": RESULT_CHASE_SHORT_WINDOW_MINUTES,
        "result_chase_medium_retry_minutes": RESULT_CHASE_MEDIUM_RETRY_MINUTES,
        "result_chase_medium_window_hours": RESULT_CHASE_MEDIUM_WINDOW_HOURS,
        "result_chase_long_retry_hours": RESULT_CHASE_LONG_RETRY_HOURS,
        "result_chase_long_window_hours": RESULT_CHASE_LONG_WINDOW_HOURS,
        "historical_lookback_days": HISTORICAL_LOOKBACK_DAYS,
        "recent_historical_window_days": RECENT_HISTORICAL_WINDOW_DAYS,
        "recent_historical_retry_hours": RECENT_HISTORICAL_RETRY_HOURS,
        "historical_retry_hours": HISTORICAL_RETRY_HOURS,
        "calendar_watch_lookahead_days": CALENDAR_WATCH_LOOKAHEAD_DAYS,
        "calendar_watch_matchday_hours": CALENDAR_WATCH_MATCHDAY_HOURS,
        "calendar_watch_near_days": CALENDAR_WATCH_NEAR_DAYS,
        "calendar_watch_far_days": CALENDAR_WATCH_FAR_DAYS,
        "calendar_watch_matchday_cadence_hours": CALENDAR_WATCH_MATCHDAY_CADENCE_HOURS,
        "calendar_watch_close_cadence_hours": CALENDAR_WATCH_CLOSE_CADENCE_HOURS,
        "calendar_watch_near_cadence_hours": CALENDAR_WATCH_NEAR_CADENCE_HOURS,
        "calendar_watch_far_cadence_hours": CALENDAR_WATCH_FAR_CADENCE_HOURS,
        "technical_backoff_minutes": list(TECHNICAL_BACKOFF_MINUTES),
        "next_global_fetch_at": next_due_candidates[0] if next_due_candidates else None,
    }


def write_plan(plan: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(PLAN_PATH, "w", encoding="utf-8") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main():
    plan = build_plan()
    write_plan(plan)
    print(
        f"Fetch plan mode={plan['mode']} selected={plan['selected_count']} "
        f"result_publish_delay_minutes={plan['result_publish_delay_minutes']} "
        f"historical_lookback_days={plan['historical_lookback_days']} "
        f"recent_historical_window_days={plan['recent_historical_window_days']} "
        f"recent_historical_retry_hours={plan['recent_historical_retry_hours']} "
        f"calendar_watch_lookahead_days={plan['calendar_watch_lookahead_days']} "
        f"historical_retry_hours={plan['historical_retry_hours']}"
    )
    for item in plan["competitions"]:
        flag = "RUN" if item["should_fetch"] else "SKIP"
        print(
            f"{flag} {item['competition_key']} -> {item['fetcher']} "
            f"[{item['state']}] next={item.get('next_recommended_fetch_at')} "
            f"{'; '.join(item['reasons'])}"
        )


if __name__ == "__main__":
    main()
