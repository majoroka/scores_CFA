import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from competition_configs import ALL_COMPETITIONS, CompetitionConfig
from competition_sync import collect_quality_metrics, infer_payload_status, parse_match_date


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
OUTPUT_PATH = DATA_DIR / 'calendar.json'
LOCAL_TZ = ZoneInfo('Europe/Lisbon')
SCORE_PATTERN = re.compile(r'\b\d{1,2}\s*[-–]\s*\d{1,2}\b')
TIME_PATTERN = re.compile(r'(\d{1,2}):(\d{2})')


def normalize_team_name(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '').strip().lower())


def clean_display_date(value: str) -> str:
    if not value:
        return ''
    cleaned = SCORE_PATTERN.sub(' ', value)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


def infer_status(match: dict, match_datetime: Optional[datetime], now: datetime) -> str:
    home_score = match.get('homeScore')
    away_score = match.get('awayScore')
    if isinstance(home_score, int) and isinstance(away_score, int):
        return 'finished'
    if not match_datetime:
        return 'unknown'
    return 'scheduled' if match_datetime >= now else 'unknown'


def build_match_datetime(match: dict) -> Optional[datetime]:
    base_date = parse_match_date(match.get('date', ''), today=datetime.now(LOCAL_TZ))
    if not base_date:
        return None

    parsed_time = TIME_PATTERN.search(match.get('time', '') or '')
    if parsed_time:
        hours = int(parsed_time.group(1))
        minutes = int(parsed_time.group(2))
    else:
        hours = 12
        minutes = 0

    naive_datetime = datetime(
        base_date.year,
        base_date.month,
        base_date.day,
        hours,
        minutes,
        0,
    )
    return naive_datetime.replace(tzinfo=LOCAL_TZ)


def load_competition_payload(config: CompetitionConfig) -> Optional[dict]:
    payload_path = ROOT / config.output_file
    if not payload_path.exists():
        return None
    with open(payload_path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def build_calendar_entries(config: CompetitionConfig, payload: dict, now: datetime) -> list[dict]:
    rounds = payload.get('rounds', [])
    if not isinstance(rounds, list):
        return []

    club_team_names = {normalize_team_name(name) for name in config.club_team_names}
    entries = []
    for round_data in rounds:
        round_number = round_data.get('index')
        fixture_id = round_data.get('fixtureId')
        matches = round_data.get('matches', [])
        if not isinstance(matches, list):
            continue

        for match in matches:
            home_normalized = normalize_team_name(match.get('home', ''))
            away_normalized = normalize_team_name(match.get('away', ''))
            if club_team_names and home_normalized not in club_team_names and away_normalized not in club_team_names:
                continue

            match_datetime = build_match_datetime(match)
            status = infer_status(match, match_datetime, now=now)
            display_date = clean_display_date(match.get('date', ''))
            display_time = (match.get('time') or '').strip()
            sort_timestamp = int(match_datetime.timestamp()) if match_datetime else None
            match_date_iso = match_datetime.isoformat() if match_datetime else None

            entries.append({
                'competitionKey': config.key,
                'competitionTitle': config.title,
                'competitionSubtitle': config.subtitle,
                'competitionPage': config.page_path,
                'competitionUrl': f"{config.page_path}#resultados-j{round_number}" if config.page_path and round_number else config.page_path,
                'roundNumber': round_number,
                'fixtureId': fixture_id,
                'matchDateISO': match_date_iso,
                'sortTimestamp': sort_timestamp,
                'status': status,
                'home': match.get('home', ''),
                'away': match.get('away', ''),
                'homeScore': match.get('homeScore'),
                'awayScore': match.get('awayScore'),
                'displayDate': display_date,
                'displayTime': display_time,
                'stadium': match.get('stadium', ''),
                'lastUpdatedAt': payload.get('lastUpdatedAt'),
                'sourceHealth': payload.get('sourceHealth', {}),
            })

    return entries


def build_calendar_payload(now: Optional[datetime] = None) -> dict:
    reference_now = now or datetime.now(LOCAL_TZ)
    entries = []
    competitions = []

    for config in ALL_COMPETITIONS:
        payload = load_competition_payload(config)
        if not payload:
            continue
        quality = payload.get('dataQuality') if isinstance(payload.get('dataQuality'), dict) else collect_quality_metrics(payload.get('rounds', []))
        raw_source_health = payload.get('sourceHealth', {}) if isinstance(payload.get('sourceHealth'), dict) else {}
        fallback_reuse_count = raw_source_health.get('fallbackReuseCount', 0) if isinstance(raw_source_health.get('fallbackReuseCount', 0), int) else 0
        competitions.append({
            'key': config.key,
            'title': config.title,
            'subtitle': config.subtitle,
            'pagePath': config.page_path,
            'outputFile': config.output_file,
            'lastUpdatedAt': payload.get('lastUpdatedAt'),
            'sourceHealth': {
                'status': infer_payload_status(fallback_reuse_count, quality),
                'fallbackReuseCount': fallback_reuse_count,
                'issues': list(raw_source_health.get('issues', [])) if isinstance(raw_source_health.get('issues', []), list) else [],
            },
            'roundCount': len(payload.get('rounds', [])) if isinstance(payload.get('rounds'), list) else 0,
        })
        entries.extend(build_calendar_entries(config, payload, now=reference_now))

    entries.sort(
        key=lambda item: (
            item['sortTimestamp'] if item['sortTimestamp'] is not None else 0,
            item['competitionTitle'],
            item['roundNumber'] or 0,
            item['home'],
            item['away'],
        )
    )

    return {
        'generatedAt': reference_now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'competitionCount': len(competitions),
        'matchCount': len(entries),
        'competitions': competitions,
        'matches': entries,
    }


def write_calendar(payload: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def main():
    payload = build_calendar_payload()
    write_calendar(payload)
    print(f'Calendar generated with {payload["matchCount"]} matches in {OUTPUT_PATH.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
