import html
import hashlib
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from competition_configs import CompetitionConfig
from fetch_state import (
    get_competition_state,
    get_fixture_state,
    load_fetch_state,
    save_fetch_state,
    snapshot_entry,
    update_fetch_entry,
    utc_now_iso,
)
from fpf_http import fetch_page_result, get_page_content as fetch_page_content, load_existing_rounds

CACHE_DIR = 'cache'
USE_CACHE = False
SCHEMA_VERSION = 2
SYNC_METADATA_DIR = Path(CACHE_DIR) / 'sync_metadata'
ERROR_SNAPSHOT_DIR = Path(CACHE_DIR) / 'errors'
TECHNICAL_BACKOFF_MINUTES = [
    int(item.strip())
    for item in os.environ.get('TECHNICAL_BACKOFF_MINUTES', '10,20,40').split(',')
    if item.strip()
]
MONTH_MAP = {
    'jan': 1,
    'fev': 2,
    'mar': 3,
    'abr': 4,
    'mai': 5,
    'jun': 6,
    'jul': 7,
    'ago': 8,
    'set': 9,
    'out': 10,
    'nov': 11,
    'dez': 12,
}
ZEROZERO_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/136.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'pt-PT,pt;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}
SECONDARY_PREFIX_TOKENS = {
    'acf', 'ad', 'adc', 'adt', 'associacao', 'ca', 'cdr', 'cd', 'cf', 'cr',
    'dc', 'fc', 'gd', 'sc', 'slb', 'ud', 'udr',
}


class SyncCriticalError(RuntimeError):
    def __init__(self, message: str, error_type: str = 'sync_error'):
        super().__init__(message)
        self.error_type = error_type


def _read_file_text(path: str):
    if not os.path.exists(path):
        return ''
    with open(path, 'r', encoding='utf-8') as handle:
        return handle.read()


def _write_sync_metadata(config: CompetitionConfig, metadata: dict):
    SYNC_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    target = SYNC_METADATA_DIR / f'{config.key}.json'
    with open(target, 'w', encoding='utf-8') as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def _load_previous_sync_metadata(config: CompetitionConfig):
    target = SYNC_METADATA_DIR / f'{config.key}.json'
    if not target.exists():
        return {}
    try:
        with open(target, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_error_snapshot(config: CompetitionConfig, snapshot_name: str, content: str):
    if not content:
        return None
    target_dir = ERROR_SNAPSHOT_DIR / config.key
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = target_dir / f'{snapshot_name}_{timestamp}.html'
    with open(target, 'w', encoding='utf-8') as handle:
        handle.write(content)
    return str(target)


def _result_to_metadata(result):
    if result is None:
        return {
            'ok': False,
            'errorType': 'network_error',
            'statusCode': None,
            'blocked': False,
            'attempts': 0,
            'durationSeconds': 0.0,
            'responseSize': 0,
            'cacheUsed': False,
            'url': None,
            'errorMessage': None,
        }
    return {
        'ok': result.ok,
        'errorType': result.error_type,
        'statusCode': result.status_code,
        'blocked': result.blocked,
        'attempts': result.attempts,
        'durationSeconds': result.duration_seconds,
        'responseSize': result.response_size,
        'cacheUsed': result.cache_used,
        'url': result.url,
        'errorMessage': result.error_message,
    }


def _content_hash(content: Optional[str]):
    if not content:
        return None
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _normalize_team_name(value: str):
    return _normalize_spaces(_normalize(value or ''))


def _build_match_key(match: dict):
    return (
        _normalize_team_name(match.get('home', '')),
        _normalize_team_name(match.get('away', '')),
    )


def _compare_matches(previous_match: dict, current_match: dict):
    changes = []
    if previous_match.get('homeScore') != current_match.get('homeScore') or previous_match.get('awayScore') != current_match.get('awayScore'):
        changes.append('score_changed')
    if (previous_match.get('date') or '') != (current_match.get('date') or ''):
        changes.append('date_changed')
    if (previous_match.get('time') or '') != (current_match.get('time') or ''):
        changes.append('time_changed')
    if (previous_match.get('stadium') or '') != (current_match.get('stadium') or ''):
        changes.append('stadium_changed')
    return changes


def analyze_round_changes(existing_round: Optional[dict], new_round: dict):
    if not existing_round:
        return {
            'changed': True,
            'changedFields': ['round_added'],
            'matchChanges': [
                {
                    'type': 'match_added',
                    'matchKey': _build_match_key(match),
                    'home': match.get('home'),
                    'away': match.get('away'),
                }
                for match in new_round.get('matches', [])
            ],
        }

    changed_fields = []
    match_changes = []
    previous_matches = {
        _build_match_key(match): match
        for match in existing_round.get('matches', [])
    }
    current_matches = {
        _build_match_key(match): match
        for match in new_round.get('matches', [])
    }

    for match_key, current_match in current_matches.items():
        previous_match = previous_matches.get(match_key)
        if previous_match is None:
            match_changes.append({
                'type': 'match_added',
                'matchKey': match_key,
                'home': current_match.get('home'),
                'away': current_match.get('away'),
            })
            if 'match_added' not in changed_fields:
                changed_fields.append('match_added')
            continue

        match_field_changes = _compare_matches(previous_match, current_match)
        if match_field_changes:
            match_changes.append({
                'type': 'match_updated',
                'matchKey': match_key,
                'home': current_match.get('home'),
                'away': current_match.get('away'),
                'changedFields': match_field_changes,
                'before': {
                    'date': previous_match.get('date'),
                    'time': previous_match.get('time'),
                    'stadium': previous_match.get('stadium'),
                    'homeScore': previous_match.get('homeScore'),
                    'awayScore': previous_match.get('awayScore'),
                },
                'after': {
                    'date': current_match.get('date'),
                    'time': current_match.get('time'),
                    'stadium': current_match.get('stadium'),
                    'homeScore': current_match.get('homeScore'),
                    'awayScore': current_match.get('awayScore'),
                },
            })
            for field_name in match_field_changes:
                if field_name not in changed_fields:
                    changed_fields.append(field_name)

    for match_key, previous_match in previous_matches.items():
        if match_key in current_matches:
            continue
        match_changes.append({
            'type': 'match_removed',
            'matchKey': match_key,
            'home': previous_match.get('home'),
            'away': previous_match.get('away'),
        })
        if 'match_removed' not in changed_fields:
            changed_fields.append('match_removed')

    previous_classification = existing_round.get('classification', [])
    current_classification = new_round.get('classification', [])
    if previous_classification != current_classification:
        changed_fields.append('classification_changed')

    return {
        'changed': bool(changed_fields),
        'changedFields': changed_fields,
        'matchChanges': match_changes,
    }


def enrich_rounds_for_schema(rounds, fixture_states_by_id: dict, fixture_meta_by_id: dict):
    enriched_rounds = []
    for round_data in rounds:
        fixture_id = str(round_data.get('fixtureId'))
        fixture_state = fixture_states_by_id.get(fixture_id, {})
        fixture_meta = fixture_meta_by_id.get(fixture_id, {})
        change_fields_by_key = {}
        match_added_keys = set()
        for match_change in fixture_meta.get('matchChanges', []):
            match_key = tuple(match_change.get('matchKey', ()))
            if not match_key:
                continue
            if match_change.get('type') == 'match_updated':
                change_fields_by_key[match_key] = list(match_change.get('changedFields', []))
            elif match_change.get('type') == 'match_added':
                match_added_keys.add(match_key)

        enriched_matches = []
        for match in round_data.get('matches', []):
            match_key = _build_match_key(match)
            change_flags = list(match.get('changeFlags', []))
            for field_name in change_fields_by_key.get(match_key, []):
                if field_name not in change_flags:
                    change_flags.append(field_name)
            if match_key in match_added_keys and 'match_added' not in change_flags:
                change_flags.append('match_added')

            score_source = match.get('scoreSource')
            if score_source is None and isinstance(match.get('homeScore'), int) and isinstance(match.get('awayScore'), int):
                score_source = 'fpf'

            enriched_match = dict(match)
            enriched_match['scoreSource'] = score_source
            enriched_match['calendarSource'] = match.get('calendarSource') or 'fpf'
            enriched_match['lastChangedAt'] = match.get('lastChangedAt') or fixture_state.get('lastChangedAt')
            enriched_match['changeFlags'] = change_flags
            enriched_matches.append(enriched_match)

        enriched_round = dict(round_data)
        enriched_round['lastAttemptAt'] = fixture_state.get('lastAttemptAt')
        enriched_round['lastSuccessAt'] = fixture_state.get('lastSuccessAt')
        enriched_round['lastChangedAt'] = fixture_state.get('lastChangedAt')
        enriched_round['sourceStatus'] = fixture_meta.get('fetchStatus', 'unknown')
        enriched_round['sourceIssue'] = fixture_meta.get('errorType')
        enriched_round['matches'] = enriched_matches
        enriched_rounds.append(enriched_round)

    return enriched_rounds


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize('NFD', value)
    normalized = normalized.encode('ascii', 'ignore').decode('ascii')
    return normalized.lower().strip()


def _clean_text(value: str) -> str:
    value = re.sub(r'<br\s*/?>', ' ', value, flags=re.IGNORECASE)
    value = re.sub(r'<.*?>', '', value)
    return html.unescape(value).strip()


def _normalize_spaces(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip()


def _normalize_month_token(value: str):
    if not value:
        return None
    normalized = (
        unicodedata.normalize('NFD', value)
        .encode('ascii', 'ignore')
        .decode('ascii')
        .lower()
    )
    normalized = re.sub(r'[^a-z]', '', normalized)
    if not normalized:
        return None
    return normalized[:3]


def parse_match_date(value: str, today: Optional[datetime] = None):
    trimmed = (value or '').strip()
    if not trimmed:
        return None

    sanitized = re.sub(r'\b\d{1,2}\s*[-–]\s*\d{1,2}\b', ' ', trimmed)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    if not sanitized:
        return None

    day = None
    month_token = None
    direct_matches = list(re.finditer(r'(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,})', sanitized))
    if direct_matches:
        latest_match = direct_matches[-1]
        day = int(latest_match.group(1))
        month_token = latest_match.group(2)
    else:
        tokens = sanitized.split()
        for index, token in enumerate(tokens):
            month_key = _normalize_month_token(token)
            if not month_key or month_key not in MONTH_MAP:
                continue

            extracted_day = None
            for previous_index in range(index - 1, -1, -1):
                match = re.search(r'(\d{1,2})', tokens[previous_index])
                if match:
                    extracted_day = int(match.group(1))
                    break
            if extracted_day is None and index + 1 < len(tokens):
                match = re.search(r'(\d{1,2})', tokens[index + 1])
                if match:
                    extracted_day = int(match.group(1))
            if extracted_day is not None:
                day = extracted_day
                month_token = token
                break

    if day is None or not month_token:
        return None

    month_key = _normalize_month_token(month_token)
    if month_key not in MONTH_MAP:
        return None

    reference_today = today or datetime.now()
    month = MONTH_MAP[month_key]
    year = reference_today.year
    diff = month - reference_today.month
    if diff <= -6:
        year += 1
    elif diff >= 6:
        year -= 1

    try:
        return datetime(year, month, day, 12, 0, 0)
    except ValueError:
        return None


def get_round_reference_date(round_data: dict, today: Optional[datetime] = None):
    matches = round_data.get('matches', [])
    if not isinstance(matches, list):
        return None

    latest_completed = None
    latest_any = None
    for match in matches:
        parsed = parse_match_date(match.get('date', ''), today=today)
        if not parsed:
            continue
        has_score = isinstance(match.get('homeScore'), int) and isinstance(match.get('awayScore'), int)
        if has_score and (latest_completed is None or parsed > latest_completed):
            latest_completed = parsed
        if latest_any is None or parsed > latest_any:
            latest_any = parsed
    return latest_completed or latest_any


def compute_default_round_index(rounds, today: Optional[datetime] = None):
    if not rounds:
        return 0

    reference_today = today or datetime.now()
    reference_today = reference_today.replace(hour=12, minute=0, second=0, microsecond=0)

    previous_or_current = None
    previous_or_current_date = None
    first_future = None
    first_future_date = None

    for index, round_data in enumerate(rounds):
        reference = get_round_reference_date(round_data, today=reference_today)
        if not reference:
            continue
        if reference <= reference_today:
            if previous_or_current_date is None or reference > previous_or_current_date:
                previous_or_current = index
                previous_or_current_date = reference
        elif first_future_date is None or reference < first_future_date:
            first_future = index
            first_future_date = reference

    if previous_or_current is not None:
        return previous_or_current
    if first_future is not None:
        return first_future
    return 0


def collect_quality_metrics(rounds, today: Optional[datetime] = None):
    reference_today = (today or datetime.now()).replace(hour=12, minute=0, second=0, microsecond=0)
    unique_teams = set()
    round_count = len(rounds)
    match_count = 0
    classification_count = 0
    completed_match_count = 0
    future_match_count = 0
    past_match_count = 0
    past_matches_without_score = 0
    rounds_with_matches = 0
    rounds_with_classification = 0
    rounds_with_completed_matches = 0
    rounds_without_data = 0

    for round_data in rounds:
        matches = round_data.get('matches', [])
        classification = round_data.get('classification', [])
        if matches:
            rounds_with_matches += 1
        if classification:
            rounds_with_classification += 1
        if not matches and not classification:
            rounds_without_data += 1

        round_has_completed_matches = False
        for match in matches:
            match_count += 1
            home_team = (match.get('home') or '').strip()
            away_team = (match.get('away') or '').strip()
            if home_team:
                unique_teams.add(home_team)
            if away_team:
                unique_teams.add(away_team)

            has_score = isinstance(match.get('homeScore'), int) and isinstance(match.get('awayScore'), int)
            if has_score:
                completed_match_count += 1
                round_has_completed_matches = True

            parsed_date = parse_match_date(match.get('date', ''), today=reference_today)
            if parsed_date:
                if parsed_date <= reference_today:
                    past_match_count += 1
                    if not has_score:
                        past_matches_without_score += 1
                else:
                    future_match_count += 1

        if round_has_completed_matches:
            rounds_with_completed_matches += 1

        for entry in classification:
            team_name = (entry.get('team') or '').strip()
            if team_name:
                unique_teams.add(team_name)
            classification_count += 1

    return {
        'roundCount': round_count,
        'matchCount': match_count,
        'classificationCount': classification_count,
        'teamCount': len(unique_teams),
        'completedMatchCount': completed_match_count,
        'matchesWithoutScore': max(match_count - completed_match_count, 0),
        'pastMatchCount': past_match_count,
        'pastMatchesWithoutScore': past_matches_without_score,
        'futureMatchCount': future_match_count,
        'roundsWithMatches': rounds_with_matches,
        'roundsWithClassification': rounds_with_classification,
        'roundsWithCompletedMatches': rounds_with_completed_matches,
        'roundsWithoutData': rounds_without_data,
    }


def infer_payload_status(fallback_reuse_count: int, quality_metrics: dict):
    if fallback_reuse_count > 0:
        return 'degraded'
    if quality_metrics.get('pastMatchesWithoutScore', 0) > 0:
        return 'partial'
    return 'ok'


def build_payload(
    rounds,
    fallback_reuse_count: int = 0,
    last_updated_at: Optional[str] = None,
    sync_issues: Optional[list[str]] = None,
    quality_metrics: Optional[dict] = None,
    fetch_state_entry: Optional[dict] = None,
):
    default_round_index = compute_default_round_index(rounds)
    default_round_number = None
    if 0 <= default_round_index < len(rounds):
        default_round_number = rounds[default_round_index].get('index')

    timestamp = last_updated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    metrics = quality_metrics or collect_quality_metrics(rounds)
    health_status = infer_payload_status(fallback_reuse_count, metrics)
    fetch_state_entry = fetch_state_entry or {}

    return {
        'schemaVersion': SCHEMA_VERSION,
        'generatedAt': timestamp,
        'lastAttemptAt': fetch_state_entry.get('lastAttemptAt'),
        'lastSuccessAt': fetch_state_entry.get('lastSuccessAt'),
        'lastChangedAt': fetch_state_entry.get('lastChangedAt'),
        'lastPublishedAt': timestamp,
        'defaultRoundIndex': default_round_index,
        'defaultRoundNumber': default_round_number,
        'lastUpdatedAt': timestamp,
        'sourceHealth': {
            'status': health_status,
            'fallbackReuseCount': fallback_reuse_count,
            'issues': list(sync_issues or []),
        },
        'dataQuality': metrics,
        'rounds': rounds,
    }


def _iter_series_blocks(html_content: str):
    pattern = re.compile(r'<div class="game-results[^>]*id="htmlSerieId_(\d+)"[^>]*>')
    for match in re.finditer(pattern, html_content):
        start = match.start()
        block_slice = html_content[start:]
        next_match = re.search(r'<div class="game-results', block_slice[1:])
        block = block_slice[: next_match.start() + 1] if next_match else block_slice
        yield start, block


def extract_fixture_ids(html_content: str, config: CompetitionConfig):
    if config.target_serie_id:
        pattern = re.compile(r'<div[^>]*id="htmlSerieId_' + re.escape(str(config.target_serie_id)) + r'"[^>]*>')
        match = pattern.search(html_content)
        if match:
            start = match.start()
            block_slice = html_content[start:]
            next_match = re.search(r'<div[^>]*id="htmlSerieId_\d+"', block_slice[1:])
            block = block_slice[: next_match.start() + 1] if next_match else block_slice
            fixture_ids = []
            for fixture_id in re.findall(r'fixtureId=(\d+)', block):
                if fixture_id not in fixture_ids:
                    fixture_ids.append(fixture_id)
            if fixture_ids:
                return fixture_ids

    normalized_target = _normalize(config.target_serie_name) if config.target_serie_name else ''
    normalized_phase = _normalize(config.target_phase_name) if config.target_phase_name else ''
    first_block = None

    for start, block in _iter_series_blocks(html_content):
        if first_block is None:
            first_block = block

        block_normalized = _normalize(html.unescape(block))
        if normalized_target and normalized_target not in block_normalized:
            continue

        if normalized_phase:
            phase_title_index = html_content.rfind('<div class="accordion-title', 0, start)
            phase_context = html_content[phase_title_index:start] if phase_title_index != -1 else ''
            if normalized_phase not in _normalize(html.unescape(phase_context)):
                continue

        fixture_ids = []
        for fixture_id in re.findall(r'fixtureId=(\d+)', block):
            if fixture_id not in fixture_ids:
                fixture_ids.append(fixture_id)
        if fixture_ids:
            return fixture_ids

    if config.allow_first_block_fallback and first_block:
        fixture_ids = []
        for fixture_id in re.findall(r'fixtureId=(\d+)', first_block):
            if fixture_id not in fixture_ids:
                fixture_ids.append(fixture_id)
        if fixture_ids:
            return fixture_ids

    return []


def parse_matches(html_fragment: str, strip_score_from_date: bool = False):
    matches = []
    pattern = re.compile(
        r'<div class="game"[\s\S]*?'
        r'<div class="home-team[^>]*>(.*?)</div>[\s\S]*?'
        r'<div class="[^>]*?text-center[^>]*>([\s\S]*?)</div>[\s\S]*?'
        r'<div class="away-team[^>]*>(.*?)</div>[\s\S]*?</div>\s*'
        r'<div class="game-list-stadium"[^>]*>[\s\S]*?<small[^>]*>(.*?)</small>',
        re.IGNORECASE,
    )

    for home_html, center_html, away_html, stadium_html in re.findall(pattern, html_fragment):
        home = _clean_text(home_html)
        away = _clean_text(away_html)
        center = _clean_text(center_html)
        stadium = _clean_text(stadium_html)

        score_match = re.search(r'(\d{1,2})\s*[-–]\s*(\d{1,2})', center)
        time_match = re.search(r'(\d{1,2}:\d{2})', center)
        time_value = time_match.group(1) if time_match else ''
        if strip_score_from_date:
            center_for_date = re.sub(r'\b\d{1,2}\s*[-–]\s*\d{1,2}\b', '', center).strip()
            date_value = center_for_date.replace(time_value, '').strip() if time_value else center_for_date
        else:
            date_value = center.replace(time_value, '').strip() if time_value else center

        matches.append({
            'home': home,
            'away': away,
            'date': date_value,
            'time': time_value,
            'stadium': stadium,
            'homeScore': int(score_match.group(1)) if score_match else None,
            'awayScore': int(score_match.group(2)) if score_match else None,
        })

    return matches


def parse_classification(html_fragment: str):
    classification = []
    section_match = re.search(
        r'<div id="classification">([\s\S]*?)</div>\s*<div id="matches">',
        html_fragment,
        re.IGNORECASE,
    )
    section_html = section_match.group(1) if section_match else html_fragment
    row_pattern = re.compile(
        r'<div class="game classification[^"]*">\s*([\s\S]*?)\s*(?=</div>\s*(?:<div class="game classification|$))',
        re.IGNORECASE,
    )
    rows = re.findall(row_pattern, section_html)
    for row_html in rows:
        cols = re.findall(r'<div class="[^>]*?col-[^"]*">([\s\S]*?)</div>', row_html)
        if len(cols) < 9:
            continue
        try:
            pos = int(_clean_text(cols[0]))
            team = _clean_text(cols[1])
            played = int(_clean_text(cols[2]))
            wins = int(_clean_text(cols[3]))
            draws = int(_clean_text(cols[4]))
            losses = int(_clean_text(cols[5]))
            goals_for = int(_clean_text(cols[6]))
            goals_against = int(_clean_text(cols[7]))
            points = int(_clean_text(cols[8]))
        except ValueError:
            continue
        classification.append({
            'position': pos,
            'team': team,
            'played': played,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'goalsFor': goals_for,
            'goalsAgainst': goals_against,
            'points': points,
        })
    return classification


def _secondary_team_key(team_name: str, aliases: Optional[dict[str, str]] = None):
    normalized = _normalize_spaces(_normalize(team_name or ''))
    if not normalized:
        return ''

    if aliases and normalized in aliases:
        return aliases[normalized]

    cleaned = re.sub(r'[^a-z0-9 ]+', ' ', normalized)
    tokens = [token for token in cleaned.split() if token and token not in SECONDARY_PREFIX_TOKENS]
    simplified = ' '.join(tokens) or cleaned.strip() or normalized
    simplified = _normalize_spaces(simplified)

    if aliases and simplified in aliases:
        return aliases[simplified]
    return simplified


def fetch_secondary_results_page(url: str):
    request = urllib.request.Request(url, headers=ZEROZERO_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode('utf-8', 'ignore')
    except (urllib.error.URLError, TimeoutError, ValueError):
        return ''


def parse_zerozero_round_results(html_content: str):
    section_match = re.search(
        r'<div id="fixture_games"[^>]*>[\s\S]*?<tbody>([\s\S]*?)</tbody>',
        html_content,
        re.IGNORECASE,
    )
    if not section_match:
        return []

    results = []
    row_pattern = re.compile(r'<tr>([\s\S]*?)</tr>', re.IGNORECASE)
    for row_html in row_pattern.findall(section_match.group(1)):
        columns = re.findall(r'<td[^>]*>([\s\S]*?)</td>', row_html, re.IGNORECASE)
        if len(columns) < 6:
            continue

        date_value = _clean_text(columns[0]).replace('\xa0', ' ').strip()
        home_team = _clean_text(columns[1])
        score_text = _clean_text(columns[3])
        away_team = _clean_text(columns[5])
        score_match = re.search(r'(\d{1,2})\s*[-–]\s*(\d{1,2})', score_text)
        if not home_team or not away_team or not score_match:
            continue

        results.append({
            'date': date_value,
            'home': home_team,
            'away': away_team,
            'homeScore': int(score_match.group(1)),
            'awayScore': int(score_match.group(2)),
        })

    return results


def fill_missing_scores_from_secondary_results(
    rounds,
    config: CompetitionConfig,
    today: Optional[datetime] = None,
    page_fetcher=None,
):
    if not config.secondary_results_url or not config.secondary_results_phase_id:
        return 0

    reference_today = (today or datetime.now()).replace(hour=12, minute=0, second=0, microsecond=0)
    aliases = {
        _normalize_spaces(_normalize(source)): _normalize_spaces(_normalize(target))
        for source, target in dict(config.secondary_results_team_aliases).items()
    }
    fetcher = page_fetcher or fetch_secondary_results_page
    filled_scores = 0

    for round_data in rounds:
        matches = round_data.get('matches', [])
        pending_matches = []
        for match in matches:
            has_score = isinstance(match.get('homeScore'), int) and isinstance(match.get('awayScore'), int)
            if has_score:
                continue
            parsed_date = parse_match_date(match.get('date', ''), today=reference_today)
            if not parsed_date or parsed_date > reference_today:
                continue
            pending_matches.append(match)

        if not pending_matches:
            continue

        url = (
            f'{config.secondary_results_url}?fase={config.secondary_results_phase_id}'
            f'&jornada_in={round_data.get("index")}'
        )
        page = fetcher(url)
        if not page:
            continue

        zerozero_results = parse_zerozero_round_results(page)
        zerozero_by_pair = {
            (
                _secondary_team_key(item['home'], aliases),
                _secondary_team_key(item['away'], aliases),
            ): item
            for item in zerozero_results
        }

        for match in pending_matches:
            key = (
                _secondary_team_key(match.get('home', ''), aliases),
                _secondary_team_key(match.get('away', ''), aliases),
            )
            secondary_match = zerozero_by_pair.get(key)
            if not secondary_match:
                continue
            match['homeScore'] = secondary_match['homeScore']
            match['awayScore'] = secondary_match['awayScore']
            match['scoreSource'] = 'secondary'
            filled_scores += 1

    return filled_scores


def build_classification_from_results(rounds, ignored_team_names):
    ignored = {_normalize(name) for name in ignored_team_names}
    team_labels = {}
    for round_data in rounds:
        for match in round_data.get('matches', []):
            for side in ('home', 'away'):
                team = (match.get(side) or '').strip()
                normalized = _normalize(team)
                if not team or normalized in ignored:
                    continue
                team_labels.setdefault(normalized, team)

    def empty_stats():
        return {
            'played': 0,
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'goalsFor': 0,
            'goalsAgainst': 0,
            'points': 0,
        }

    stats = {normalized: empty_stats() for normalized in team_labels}

    for round_data in rounds:
        for match in round_data.get('matches', []):
            home_team = (match.get('home') or '').strip()
            away_team = (match.get('away') or '').strip()
            home_normalized = _normalize(home_team)
            away_normalized = _normalize(away_team)

            if (
                not home_team
                or not away_team
                or home_normalized in ignored
                or away_normalized in ignored
            ):
                continue

            home_score = match.get('homeScore')
            away_score = match.get('awayScore')
            if not isinstance(home_score, int) or not isinstance(away_score, int):
                continue

            if home_normalized not in stats:
                stats[home_normalized] = empty_stats()
                team_labels.setdefault(home_normalized, home_team)
            if away_normalized not in stats:
                stats[away_normalized] = empty_stats()
                team_labels.setdefault(away_normalized, away_team)

            home_stats = stats[home_normalized]
            away_stats = stats[away_normalized]

            home_stats['played'] += 1
            away_stats['played'] += 1
            home_stats['goalsFor'] += home_score
            home_stats['goalsAgainst'] += away_score
            away_stats['goalsFor'] += away_score
            away_stats['goalsAgainst'] += home_score

            if home_score > away_score:
                home_stats['wins'] += 1
                home_stats['points'] += 3
                away_stats['losses'] += 1
            elif home_score < away_score:
                away_stats['wins'] += 1
                away_stats['points'] += 3
                home_stats['losses'] += 1
            else:
                home_stats['draws'] += 1
                away_stats['draws'] += 1
                home_stats['points'] += 1
                away_stats['points'] += 1

        classification = []
        for normalized, team_stats in stats.items():
            classification.append({
                'position': 0,
                'team': team_labels[normalized],
                'played': team_stats['played'],
                'wins': team_stats['wins'],
                'draws': team_stats['draws'],
                'losses': team_stats['losses'],
                'goalsFor': team_stats['goalsFor'],
                'goalsAgainst': team_stats['goalsAgainst'],
                'points': team_stats['points'],
            })

        classification.sort(
            key=lambda entry: (
                -entry['points'],
                -(entry['goalsFor'] - entry['goalsAgainst']),
                -entry['goalsFor'],
                _normalize(entry['team']),
            )
        )
        for position, entry in enumerate(classification, start=1):
            entry['position'] = position

        round_data['classification'] = classification


def get_page_content(url: str, cache_key: str):
    return fetch_page_content(
        url,
        cache_dir=CACHE_DIR,
        use_cache=USE_CACHE,
        cache_key=cache_key,
    )


def validate_sync_result(config: CompetitionConfig, rounds, fixture_ids, existing_rounds):
    if not fixture_ids:
        raise SyncCriticalError(f'{config.key}: no fixture ids found', 'no_fixture_ids')
    if not rounds:
        raise SyncCriticalError(f'{config.key}: no rounds extracted', 'no_rounds')
    if existing_rounds and len(rounds) < len(existing_rounds):
        raise SyncCriticalError(
            f'{config.key}: extracted only {len(rounds)} rounds, existing file has {len(existing_rounds)}',
            'round_count_shrank',
        )
    if len(rounds) < len(fixture_ids):
        raise SyncCriticalError(
            f'{config.key}: extracted only {len(rounds)} rounds for {len(fixture_ids)} fixture ids',
            'incomplete_rounds',
        )

    quality_metrics = collect_quality_metrics(rounds)
    if quality_metrics['roundCount'] <= 0:
        raise SyncCriticalError(f'{config.key}: no rounds after validation', 'no_rounds')
    if quality_metrics['matchCount'] <= 0:
        raise SyncCriticalError(f'{config.key}: no matches extracted', 'no_matches')
    if quality_metrics['teamCount'] <= 0:
        raise SyncCriticalError(f'{config.key}: no teams extracted', 'no_teams')
    return quality_metrics


def run_sync(
    config: CompetitionConfig,
    *,
    selected_fixture_ids: Optional[list[str]] = None,
    allow_full_discovery: bool = True,
):
    fetch_state = load_fetch_state()
    competition_state = get_competition_state(fetch_state, config.key)
    previous_sync_metadata = _load_previous_sync_metadata(config)
    attempt_started_at = utc_now_iso()
    existing_output_text = _read_file_text(config.output_file)
    existing_rounds = load_existing_rounds(config.output_file)
    normalized_selected_fixture_ids = [
        str(fixture_id).strip()
        for fixture_id in (selected_fixture_ids or [])
        if str(fixture_id).strip()
    ]
    selective_mode = (
        bool(normalized_selected_fixture_ids)
        and not allow_full_discovery
        and all(fixture_id in existing_rounds for fixture_id in normalized_selected_fixture_ids)
    )
    metadata = {
        'competitionKey': config.key,
        'attemptStartedAt': attempt_started_at,
        'success': False,
        'changed': False,
        'errorType': None,
        'errorMessage': None,
        'mainPage': None,
        'fixtures': [],
        'fallbackReuseCount': 0,
        'syncIssues': [],
        'outputFile': config.output_file,
        'successfulFixtureIds': [],
        'failedFixtureIds': [],
        'reusedFixtureIds': [],
        'technicalErrors': [],
        'calendarChangedCount': 0,
        'scoreChangedCount': 0,
        'sourceChangedCount': 0,
        'sourceChanged': False,
        'parsedChanged': False,
        'publishedChanged': False,
        'selectedFixtureIds': normalized_selected_fixture_ids,
        'fullDiscoveryUsed': not selective_mode,
        'stateBefore': snapshot_entry(competition_state),
        'stateAfter': None,
    }

    try:
        competition_state['lastAttemptAt'] = attempt_started_at
        if selective_mode:
            metadata['mainPage'] = {
                'ok': True,
                'errorType': None,
                'statusCode': None,
                'blocked': False,
                'attempts': 0,
                'durationSeconds': 0.0,
                'responseSize': 0,
                'cacheUsed': True,
                'url': config.competition_url,
                'errorMessage': None,
                'contentHash': None,
                'sourceChanged': False,
                'skipped': True,
                'skipReason': 'selected_fixture_ids',
            }
            fixture_ids = sorted(
                normalized_selected_fixture_ids,
                key=lambda fixture_id: int(existing_rounds[fixture_id].get('index', 0)),
            )
        else:
            main_result = fetch_page_result(
                config.competition_url,
                cache_dir=CACHE_DIR,
                use_cache=USE_CACHE,
                cache_key=config.main_cache_key,
            )
            metadata['mainPage'] = _result_to_metadata(main_result)
            metadata['mainPage']['contentHash'] = _content_hash(main_result.content)
            previous_main_hash = ((previous_sync_metadata or {}).get('mainPage') or {}).get('contentHash')
            metadata['mainPage']['sourceChanged'] = bool(
                metadata['mainPage']['contentHash']
                and metadata['mainPage']['contentHash'] != previous_main_hash
            )
            if not main_result.ok or not main_result.content:
                if main_result.content:
                    snapshot_path = _save_error_snapshot(config, 'main', main_result.content)
                    if snapshot_path:
                        metadata['mainPage']['errorSnapshotPath'] = snapshot_path
                error_type = main_result.error_type or 'network_error'
                update_fetch_entry(
                    competition_state,
                    attempted_at=attempt_started_at,
                    success=False,
                    error_type=error_type,
                    backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
                )
                raise SyncCriticalError(f'{config.key}: failed to fetch competition page', error_type)

            fixture_ids = extract_fixture_ids(main_result.content, config)
            if not fixture_ids:
                snapshot_path = _save_error_snapshot(config, 'main_no_fixture_ids', main_result.content)
                if snapshot_path:
                    metadata['mainPage']['errorSnapshotPath'] = snapshot_path
                update_fetch_entry(
                    competition_state,
                    attempted_at=attempt_started_at,
                    success=False,
                    error_type='no_fixture_ids',
                    backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
                )
                raise SyncCriticalError(f'{config.key}: no fixture ids found for target series', 'no_fixture_ids')

        rounds_by_fixture_id = {
            str(fixture_id): dict(round_data)
            for fixture_id, round_data in existing_rounds.items()
        } if selective_mode else {}
        fallback_reuse_count = 0
        sync_issues = []
        for index, fixture_id in enumerate(fixture_ids, start=1):
            round_index = existing_rounds.get(str(fixture_id), {}).get('index', index)
            print(f'Processando jornada {index} (fixtureId={fixture_id})')
            url = (
                'https://resultados.fpf.pt/Competition/'
                f'GetClassificationAndMatchesByFixture?fixtureId={fixture_id}'
            )
            fixture_attempt_at = utc_now_iso()
            fixture_state = get_fixture_state(fetch_state, config.key, str(fixture_id))
            fixture_state['lastAttemptAt'] = fixture_attempt_at
            fixture_result = fetch_page_result(
                url,
                cache_dir=CACHE_DIR,
                use_cache=USE_CACHE,
                cache_key=f'{config.fixture_cache_prefix}_{fixture_id}',
            )
            fixture_meta = {
                'index': index,
                'fixtureId': str(fixture_id),
                'fetch': _result_to_metadata(fixture_result),
                'fetchStatus': 'unknown',
                'fallbackUsed': False,
                'errorType': None,
                'changed': False,
                'sourceChanged': False,
                'changedFields': [],
                'matchChanges': [],
            }
            fixture_meta['fetch']['contentHash'] = _content_hash(fixture_result.content)
            previous_fixture_meta = next(
                (
                    item for item in (previous_sync_metadata or {}).get('fixtures', [])
                    if item.get('fixtureId') == str(fixture_id)
                ),
                {},
            )
            previous_fixture_hash = (previous_fixture_meta.get('fetch') or {}).get('contentHash')
            fixture_meta['sourceChanged'] = bool(
                fixture_meta['fetch']['contentHash']
                and fixture_meta['fetch']['contentHash'] != previous_fixture_hash
            )
            if fixture_meta['sourceChanged']:
                metadata['sourceChangedCount'] += 1
            existing_round = existing_rounds.get(str(fixture_id))
            if not fixture_result.ok or not fixture_result.content:
                if fixture_result.content:
                    snapshot_path = _save_error_snapshot(config, f'fixture_{fixture_id}', fixture_result.content)
                    if snapshot_path:
                        fixture_meta['fetch']['errorSnapshotPath'] = snapshot_path
                error_type = fixture_result.error_type or 'network_error'
                update_fetch_entry(
                    fixture_state,
                    attempted_at=fixture_attempt_at,
                    success=False,
                    error_type=error_type,
                    backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
                )
                fixture_meta['fetchStatus'] = 'error'
                fixture_meta['errorType'] = error_type
                metadata['failedFixtureIds'].append(str(fixture_id))
                metadata['technicalErrors'].append({
                    'fixtureId': str(fixture_id),
                    'errorType': error_type,
                    'stage': 'fetch',
                })
                if existing_round:
                    print(f'Falha ao obter dados da jornada {index}; a reutilizar dados existentes.')
                    rounds_by_fixture_id[str(fixture_id)] = existing_round
                    fallback_reuse_count += 1
                    sync_issues.append(f'fixture {fixture_id}: fallback to existing round')
                    fixture_meta['fallbackUsed'] = True
                    fixture_meta['fetchStatus'] = 'fallback_reused'
                    metadata['reusedFixtureIds'].append(str(fixture_id))
                else:
                    print(f'Falha ao obter dados da jornada {index}')
                    sync_issues.append(f'fixture {fixture_id}: missing fragment and no fallback')
                metadata['fixtures'].append(fixture_meta)
                continue

            try:
                matches = parse_matches(
                    fixture_result.content,
                    strip_score_from_date=config.strip_score_from_date,
                )
                classification = parse_classification(fixture_result.content)
            except Exception as exc:
                snapshot_path = _save_error_snapshot(config, f'fixture_{fixture_id}_parse_error', fixture_result.content)
                if snapshot_path:
                    fixture_meta['fetch']['errorSnapshotPath'] = snapshot_path
                update_fetch_entry(
                    fixture_state,
                    attempted_at=fixture_attempt_at,
                    success=False,
                    error_type='parse_error',
                    backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
                )
                fixture_meta['fetchStatus'] = 'parse_error'
                fixture_meta['errorType'] = 'parse_error'
                fixture_meta['errorMessage'] = str(exc)
                metadata['failedFixtureIds'].append(str(fixture_id))
                metadata['technicalErrors'].append({
                    'fixtureId': str(fixture_id),
                    'errorType': 'parse_error',
                    'stage': 'parse',
                })
                if existing_round:
                    rounds_by_fixture_id[str(fixture_id)] = existing_round
                    fallback_reuse_count += 1
                    sync_issues.append(f'fixture {fixture_id}: fallback to existing round after parse error')
                    fixture_meta['fallbackUsed'] = True
                    metadata['reusedFixtureIds'].append(str(fixture_id))
                else:
                    sync_issues.append(f'fixture {fixture_id}: parse error and no fallback')
                metadata['fixtures'].append(fixture_meta)
                continue

            if not matches and not classification and existing_round:
                print(f'Jornada {index} sem dados novos; a reutilizar dados existentes.')
                rounds_by_fixture_id[str(fixture_id)] = existing_round
                fallback_reuse_count += 1
                sync_issues.append(f'fixture {fixture_id}: reused existing round because fragment had no data')
                update_fetch_entry(
                    fixture_state,
                    attempted_at=fixture_attempt_at,
                    success=False,
                    error_type='no_usable_data',
                    backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
                )
                fixture_meta['fetchStatus'] = 'fallback_reused'
                fixture_meta['fallbackUsed'] = True
                fixture_meta['errorType'] = 'no_usable_data'
                metadata['failedFixtureIds'].append(str(fixture_id))
                metadata['reusedFixtureIds'].append(str(fixture_id))
                snapshot_path = _save_error_snapshot(config, f'fixture_{fixture_id}_no_usable_data', fixture_result.content)
                if snapshot_path:
                    fixture_meta['fetch']['errorSnapshotPath'] = snapshot_path
                metadata['fixtures'].append(fixture_meta)
                continue
            if not matches and not classification:
                print(f'Jornada {index} sem dados utilizáveis.')
                sync_issues.append(f'fixture {fixture_id}: fragment returned no usable data')
                update_fetch_entry(
                    fixture_state,
                    attempted_at=fixture_attempt_at,
                    success=False,
                    error_type='no_usable_data',
                    backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
                )
                fixture_meta['fetchStatus'] = 'no_usable_data'
                fixture_meta['errorType'] = 'no_usable_data'
                metadata['failedFixtureIds'].append(str(fixture_id))
                snapshot_path = _save_error_snapshot(config, f'fixture_{fixture_id}_no_usable_data', fixture_result.content)
                if snapshot_path:
                    fixture_meta['fetch']['errorSnapshotPath'] = snapshot_path
                metadata['fixtures'].append(fixture_meta)
                continue

            round_payload = {
                'index': round_index,
                'fixtureId': fixture_id,
                'matches': matches,
                'classification': classification,
            }
            change_info = analyze_round_changes(existing_round, round_payload)
            rounds_by_fixture_id[str(fixture_id)] = round_payload
            update_fetch_entry(
                fixture_state,
                attempted_at=fixture_attempt_at,
                success=True,
                changed=change_info['changed'],
                backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
            )
            fixture_meta['fetchStatus'] = 'ok'
            fixture_meta['changed'] = change_info['changed']
            fixture_meta['sourceChanged'] = fixture_meta['sourceChanged']
            fixture_meta['changedFields'] = change_info['changedFields']
            fixture_meta['matchChanges'] = change_info['matchChanges']
            metadata['successfulFixtureIds'].append(str(fixture_id))
            metadata['calendarChangedCount'] += sum(
                1
                for field_name in change_info['changedFields']
                if field_name in {'date_changed', 'time_changed', 'stadium_changed', 'match_added', 'match_removed'}
            )
            metadata['scoreChangedCount'] += sum(
                1
                for field_name in change_info['changedFields']
                if field_name == 'score_changed'
            )
            metadata['fixtures'].append(fixture_meta)
            time.sleep(1)

        rounds = sorted(
            rounds_by_fixture_id.values(),
            key=lambda round_data: int(round_data.get('index', 0)),
        )

        fill_missing_scores_from_secondary_results(rounds, config)

        if config.derive_classification:
            build_classification_from_results(rounds, config.ignored_team_names)

        fixture_meta_by_id = {
            item.get('fixtureId'): item
            for item in metadata['fixtures']
        }
        fixture_states_by_id = {
            str(fixture_id): state
            for fixture_id, state in competition_state.get('fixtures', {}).items()
        }
        rounds = enrich_rounds_for_schema(rounds, fixture_states_by_id, fixture_meta_by_id)

        quality_metrics = validate_sync_result(config, rounds, fixture_ids, existing_rounds)
        data = build_payload(
            rounds,
            fallback_reuse_count=fallback_reuse_count,
            sync_issues=sync_issues,
            quality_metrics=quality_metrics,
            fetch_state_entry=competition_state,
        )
        os.makedirs(os.path.dirname(config.output_file), exist_ok=True)
        rendered_output = json.dumps(data, ensure_ascii=False, indent=4) + '\n'
        with open(config.output_file, 'w', encoding='utf-8') as handle:
            handle.write(rendered_output)

        changed = rendered_output != existing_output_text
        update_fetch_entry(
            competition_state,
            attempted_at=attempt_started_at,
            success=True,
            changed=changed,
            backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
        )
        metadata['success'] = True
        metadata['changed'] = changed
        metadata['sourceChanged'] = bool(
            metadata['mainPage'].get('sourceChanged')
            or any(item.get('sourceChanged') for item in metadata['fixtures'])
        )
        metadata['parsedChanged'] = bool(
            any(item.get('changed') for item in metadata['fixtures'])
            or metadata['calendarChangedCount'] > 0
            or metadata['scoreChangedCount'] > 0
        )
        metadata['publishedChanged'] = changed
        metadata['fallbackReuseCount'] = fallback_reuse_count
        metadata['syncIssues'] = sync_issues
        metadata['dataQuality'] = quality_metrics
        metadata['sourceHealth'] = data.get('sourceHealth')
        print(f'Dados guardados em {config.output_file}')
        return data
    except SyncCriticalError as exc:
        metadata['errorType'] = exc.error_type
        metadata['errorMessage'] = str(exc)
        update_fetch_entry(
            competition_state,
            attempted_at=attempt_started_at,
            success=False,
            error_type=exc.error_type,
            backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
        )
        raise
    except Exception as exc:
        metadata['errorType'] = 'unexpected_error'
        metadata['errorMessage'] = str(exc)
        update_fetch_entry(
            competition_state,
            attempted_at=attempt_started_at,
            success=False,
            error_type='unexpected_error',
            backoff_minutes=TECHNICAL_BACKOFF_MINUTES,
        )
        raise
    finally:
        metadata['stateAfter'] = snapshot_entry(competition_state)
        save_fetch_state(fetch_state)
        _write_sync_metadata(config, metadata)
