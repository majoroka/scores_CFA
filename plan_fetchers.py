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
PREMATCH_WINDOW_HOURS = int(os.environ.get("PREMATCH_WINDOW_HOURS", "3"))
HISTORICAL_LOOKBACK_DAYS = int(os.environ.get("HISTORICAL_LOOKBACK_DAYS", "14"))
ACTIVE_RESULT_WINDOW_DAYS = int(os.environ.get("ACTIVE_RESULT_WINDOW_DAYS", "2"))

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


def analyze_competition(config: CompetitionConfig, now: datetime) -> dict:
    if now.tzinfo is None:
        now = now.replace(tzinfo=LOCAL_TZ)
    payload = load_payload(config)
    fetcher = FETCHER_BY_KEY[config.key]

    if not valid_payload(payload):
        return {
            "competition_key": config.key,
            "fetcher": fetcher,
            "should_fetch": True,
            "state": "missing_payload",
            "active_pending_count": 0,
            "upcoming_today_count": 0,
            "historical_pending_count": 0,
            "reasons": ["payload ausente ou inválido"],
        }

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    prematch_cutoff = now + timedelta(hours=PREMATCH_WINDOW_HOURS)
    active_window_start = today_start - timedelta(days=max(ACTIVE_RESULT_WINDOW_DAYS - 1, 0))
    historical_cutoff = today_start - timedelta(days=HISTORICAL_LOOKBACK_DAYS)

    active_pending_count = 0
    upcoming_today_count = 0
    historical_pending_count = 0

    for round_data in payload["rounds"]:
        for match in round_data.get("matches", []):
            if has_score(match):
                continue

            match_dt = build_match_datetime(match)
            if not match_dt:
                continue

            if today_start <= match_dt < tomorrow_start:
                if match_dt <= prematch_cutoff:
                    active_pending_count += 1
                else:
                    upcoming_today_count += 1
            elif active_window_start <= match_dt < today_start:
                active_pending_count += 1
            elif historical_cutoff <= match_dt < today_start:
                historical_pending_count += 1

    reasons = []
    state = "idle"
    should_fetch = False

    if active_pending_count > 0:
        should_fetch = True
        state = "active_pending"
        if ACTIVE_RESULT_WINDOW_DAYS > 1:
            reasons.append(
                f"{active_pending_count} jogo(s) dos últimos {ACTIVE_RESULT_WINDOW_DAYS} dia(s) ainda sem resultado"
            )
        else:
            reasons.append(f"{active_pending_count} jogo(s) de hoje ainda sem resultado")
    elif historical_pending_count > 0:
        should_fetch = True
        state = "historical_backfill"
        reasons.append(f"{historical_pending_count} jogo(s) históricos sem resultado na janela de recuperação")
    elif upcoming_today_count > 0:
        state = "prematch_wait"
        reasons.append(f"{upcoming_today_count} jogo(s) de hoje ainda fora da janela de monitorização")
    else:
        reasons.append("sem jogos de hoje pendentes e sem backfill histórico elegível")

    return {
        "competition_key": config.key,
        "fetcher": fetcher,
        "should_fetch": should_fetch,
        "state": state,
        "active_pending_count": active_pending_count,
        "upcoming_today_count": upcoming_today_count,
        "historical_pending_count": historical_pending_count,
        "reasons": reasons,
    }


def build_plan(now: Optional[datetime] = None) -> dict:
    reference_now = now or datetime.now(LOCAL_TZ)
    analyses = [analyze_competition(config, reference_now) for config in ALL_COMPETITIONS]
    selected = [item["fetcher"] for item in analyses if item["should_fetch"]]

    states = {item["state"] for item in analyses if item["should_fetch"]}
    if "active_pending" in states:
        mode = "active_pending"
    elif "historical_backfill" in states:
        mode = "historical_backfill"
    else:
        mode = "idle"

    return {
        "generated_at": reference_now.isoformat(),
        "mode": mode,
        "selected_fetchers": selected,
        "selected_count": len(selected),
        "competitions": analyses,
        "prematch_window_hours": PREMATCH_WINDOW_HOURS,
        "active_result_window_days": ACTIVE_RESULT_WINDOW_DAYS,
        "historical_lookback_days": HISTORICAL_LOOKBACK_DAYS,
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
        f"prematch_window_hours={plan['prematch_window_hours']} "
        f"active_result_window_days={plan['active_result_window_days']} "
        f"historical_lookback_days={plan['historical_lookback_days']}"
    )
    for item in plan["competitions"]:
        flag = "RUN" if item["should_fetch"] else "SKIP"
        print(
            f"{flag} {item['competition_key']} -> {item['fetcher']} "
            f"[{item['state']}] {'; '.join(item['reasons'])}"
        )


if __name__ == "__main__":
    main()
