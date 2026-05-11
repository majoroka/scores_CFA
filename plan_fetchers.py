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

RESULT_PUBLISH_DELAY_HOURS = int(os.environ.get("RESULT_PUBLISH_DELAY_HOURS", "2"))
RESULT_CHASE_RETRY_MINUTES = int(os.environ.get("RESULT_CHASE_RETRY_MINUTES", "15"))
RESULT_CHASE_SHORT_WAVES = int(os.environ.get("RESULT_CHASE_SHORT_WAVES", "4"))
HISTORICAL_LOOKBACK_DAYS = int(os.environ.get("HISTORICAL_LOOKBACK_DAYS", "14"))
RECENT_HISTORICAL_WINDOW_DAYS = int(os.environ.get("RECENT_HISTORICAL_WINDOW_DAYS", "2"))
RECENT_HISTORICAL_RETRY_HOURS = int(os.environ.get("RECENT_HISTORICAL_RETRY_HOURS", "2"))
HISTORICAL_RETRY_HOURS = int(os.environ.get("HISTORICAL_RETRY_HOURS", "6"))
TECHNICAL_BACKOFF_MINUTES = tuple(
    int(item.strip())
    for item in os.environ.get("TECHNICAL_BACKOFF_MINUTES", "10,20,40").split(",")
    if item.strip()
)

FETCHER_BY_KEY = {
    "seniores": "fetch_fpf.py",
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


def midnight_after(value: datetime) -> datetime:
    local_value = value.astimezone(LOCAL_TZ)
    next_day = local_value.date() + timedelta(days=1)
    return datetime.combine(next_day, datetime.min.time(), tzinfo=LOCAL_TZ)


def classify_technical_state(payload: dict) -> tuple[str, int]:
    source_health = payload.get("sourceHealth", {}) if isinstance(payload.get("sourceHealth"), dict) else {}
    fallback_reuse_count = source_health.get("fallbackReuseCount", 0)
    if not isinstance(fallback_reuse_count, int):
        fallback_reuse_count = 0
    if fallback_reuse_count > 0:
        return "blocked", fallback_reuse_count
    return "healthy", 0


def technical_backoff_minutes(level: int) -> int:
    if not TECHNICAL_BACKOFF_MINUTES:
        return 10
    capped_level = min(max(level, 1), len(TECHNICAL_BACKOFF_MINUTES))
    return TECHNICAL_BACKOFF_MINUTES[capped_level - 1]


def compute_next_fetch_for_today_match(
    match_dt: datetime,
    last_fetch_at: Optional[datetime],
    now: datetime,
    technical_state: str,
    technical_level: int,
) -> datetime:
    first_fetch_at = match_dt + timedelta(hours=RESULT_PUBLISH_DELAY_HOURS)
    if technical_state != "healthy" and last_fetch_at is not None:
        return last_fetch_at + timedelta(minutes=technical_backoff_minutes(technical_level))
    if last_fetch_at is None or last_fetch_at < first_fetch_at:
        return first_fetch_at

    short_window_end = first_fetch_at + timedelta(minutes=RESULT_CHASE_RETRY_MINUTES * RESULT_CHASE_SHORT_WAVES)
    if last_fetch_at < short_window_end:
        return last_fetch_at + timedelta(minutes=RESULT_CHASE_RETRY_MINUTES)

    same_day_midnight = midnight_after(match_dt)
    if now < same_day_midnight:
        return last_fetch_at + timedelta(hours=1)
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
            "next_scheduled_kickoff": None,
            "first_result_fetch_at": None,
            "last_meaningful_fetch_at": None,
            "next_recommended_fetch_at": now.isoformat(),
            "reasons": ["payload ausente ou inválido"],
        }

    last_fetch_at = parse_timestamp(payload.get("lastUpdatedAt"))
    technical_state, technical_level = classify_technical_state(payload)

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    historical_cutoff = today_start - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
    recent_historical_cutoff = today_start - timedelta(days=RECENT_HISTORICAL_WINDOW_DAYS)

    upcoming_today_count = 0
    active_pending_count = 0
    recent_historical_pending_count = 0
    historical_pending_count = 0
    next_scheduled_kickoff = None
    first_result_fetch_at = None
    next_recommended_fetch_at = None

    for round_data in payload["rounds"]:
        for match in round_data.get("matches", []):
            if has_score(match):
                continue

            match_dt = build_match_datetime(match)
            if not match_dt:
                continue

            if match_dt < historical_cutoff:
                continue

            if today_start <= match_dt < tomorrow_start:
                if next_scheduled_kickoff is None or match_dt < next_scheduled_kickoff:
                    next_scheduled_kickoff = match_dt

                candidate_first_fetch = match_dt + timedelta(hours=RESULT_PUBLISH_DELAY_HOURS)
                if first_result_fetch_at is None or candidate_first_fetch < first_result_fetch_at:
                    first_result_fetch_at = candidate_first_fetch

                if now < candidate_first_fetch:
                    upcoming_today_count += 1
                    if next_recommended_fetch_at is None or candidate_first_fetch < next_recommended_fetch_at:
                        next_recommended_fetch_at = candidate_first_fetch
                else:
                    active_pending_count += 1
                    candidate_next_fetch = compute_next_fetch_for_today_match(
                        match_dt,
                        last_fetch_at,
                        now,
                        technical_state,
                        technical_level,
                    )
                    if next_recommended_fetch_at is None or candidate_next_fetch < next_recommended_fetch_at:
                        next_recommended_fetch_at = candidate_next_fetch
            elif match_dt < today_start:
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
        reasons.append(
            f"{active_pending_count} jogo(s) de hoje já dentro da janela de resultados"
        )
    elif upcoming_today_count > 0:
        state = "awaiting_window"
        reasons.append(
            f"{upcoming_today_count} jogo(s) de hoje ainda antes da primeira janela útil de fetch"
        )
    elif recent_historical_pending_count > 0:
        state = "recent_historical_backfill"
        due_now = next_recommended_fetch_at is not None and now >= next_recommended_fetch_at
        should_fetch = due_now
        reasons.append(
            f"{recent_historical_pending_count} jogo(s) históricos recentes sem resultado"
        )
    elif historical_pending_count > 0:
        state = "historical_backfill"
        due_now = next_recommended_fetch_at is not None and now >= next_recommended_fetch_at
        should_fetch = due_now
        reasons.append(
            f"{historical_pending_count} jogo(s) históricos sem resultado na janela de recuperação"
        )
    else:
        reasons.append("sem jogos pendentes elegíveis para fetch")

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
        "recent_historical_pending_count": recent_historical_pending_count,
        "historical_pending_count": historical_pending_count,
        "pending_today_count": pending_today_count,
        "pending_historical_count": historical_pending_count,
        "next_scheduled_kickoff": isoformat_or_none(next_scheduled_kickoff),
        "first_result_fetch_at": isoformat_or_none(first_result_fetch_at),
        "last_meaningful_fetch_at": isoformat_or_none(last_fetch_at),
        "next_recommended_fetch_at": isoformat_or_none(next_recommended_fetch_at),
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
        "result_publish_delay_hours": RESULT_PUBLISH_DELAY_HOURS,
        "result_chase_retry_minutes": RESULT_CHASE_RETRY_MINUTES,
        "result_chase_short_waves": RESULT_CHASE_SHORT_WAVES,
        "historical_lookback_days": HISTORICAL_LOOKBACK_DAYS,
        "recent_historical_window_days": RECENT_HISTORICAL_WINDOW_DAYS,
        "recent_historical_retry_hours": RECENT_HISTORICAL_RETRY_HOURS,
        "historical_retry_hours": HISTORICAL_RETRY_HOURS,
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
        f"result_publish_delay_hours={plan['result_publish_delay_hours']} "
        f"historical_lookback_days={plan['historical_lookback_days']} "
        f"recent_historical_window_days={plan['recent_historical_window_days']} "
        f"recent_historical_retry_hours={plan['recent_historical_retry_hours']} "
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
