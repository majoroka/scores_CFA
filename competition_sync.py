import html
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from competition_configs import CompetitionConfig
from fpf_http import get_page_content as fetch_page_content, load_existing_rounds

CACHE_DIR = 'cache'
USE_CACHE = False
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
    pass


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
):
    default_round_index = compute_default_round_index(rounds)
    default_round_number = None
    if 0 <= default_round_index < len(rounds):
        default_round_number = rounds[default_round_index].get('index')

    timestamp = last_updated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    metrics = quality_metrics or collect_quality_metrics(rounds)
    health_status = infer_payload_status(fallback_reuse_count, metrics)

    return {
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
        raise SyncCriticalError(f'{config.key}: no fixture ids found')
    if not rounds:
        raise SyncCriticalError(f'{config.key}: no rounds extracted')
    if existing_rounds and len(rounds) < len(existing_rounds):
        raise SyncCriticalError(
            f'{config.key}: extracted only {len(rounds)} rounds, existing file has {len(existing_rounds)}'
        )
    if len(rounds) < len(fixture_ids):
        raise SyncCriticalError(
            f'{config.key}: extracted only {len(rounds)} rounds for {len(fixture_ids)} fixture ids'
        )

    quality_metrics = collect_quality_metrics(rounds)
    if quality_metrics['roundCount'] <= 0:
        raise SyncCriticalError(f'{config.key}: no rounds after validation')
    if quality_metrics['matchCount'] <= 0:
        raise SyncCriticalError(f'{config.key}: no matches extracted')
    if quality_metrics['teamCount'] <= 0:
        raise SyncCriticalError(f'{config.key}: no teams extracted')
    return quality_metrics


def run_sync(config: CompetitionConfig):
    main_page = get_page_content(config.competition_url, config.main_cache_key)
    if not main_page:
        raise SyncCriticalError(f'{config.key}: failed to fetch competition page')

    fixture_ids = extract_fixture_ids(main_page, config)
    if not fixture_ids:
        raise SyncCriticalError(f'{config.key}: no fixture ids found for target series')

    existing_rounds = load_existing_rounds(config.output_file)
    rounds = []
    fallback_reuse_count = 0
    sync_issues = []
    for index, fixture_id in enumerate(fixture_ids, start=1):
        print(f'Processando jornada {index} (fixtureId={fixture_id})')
        url = (
            'https://resultados.fpf.pt/Competition/'
            f'GetClassificationAndMatchesByFixture?fixtureId={fixture_id}'
        )
        fragment = get_page_content(url, f'{config.fixture_cache_prefix}_{fixture_id}')
        existing_round = existing_rounds.get(str(fixture_id))
        if not fragment:
            if existing_round:
                print(f'Falha ao obter dados da jornada {index}; a reutilizar dados existentes.')
                rounds.append(existing_round)
                fallback_reuse_count += 1
                sync_issues.append(f'fixture {fixture_id}: fallback to existing round')
            else:
                print(f'Falha ao obter dados da jornada {index}')
                sync_issues.append(f'fixture {fixture_id}: missing fragment and no fallback')
            continue

        matches = parse_matches(fragment, strip_score_from_date=config.strip_score_from_date)
        classification = parse_classification(fragment)
        if not matches and not classification and existing_round:
            print(f'Jornada {index} sem dados novos; a reutilizar dados existentes.')
            rounds.append(existing_round)
            fallback_reuse_count += 1
            sync_issues.append(f'fixture {fixture_id}: reused existing round because fragment had no data')
            continue
        if not matches and not classification:
            print(f'Jornada {index} sem dados utilizáveis.')
            sync_issues.append(f'fixture {fixture_id}: fragment returned no usable data')
            continue
        rounds.append({
            'index': index,
            'fixtureId': fixture_id,
            'matches': matches,
            'classification': classification,
        })
        time.sleep(1)

    fill_missing_scores_from_secondary_results(rounds, config)

    if config.derive_classification:
        build_classification_from_results(rounds, config.ignored_team_names)

    quality_metrics = validate_sync_result(config, rounds, fixture_ids, existing_rounds)
    data = build_payload(
        rounds,
        fallback_reuse_count=fallback_reuse_count,
        sync_issues=sync_issues,
        quality_metrics=quality_metrics,
    )
    os.makedirs(os.path.dirname(config.output_file), exist_ok=True)
    with open(config.output_file, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4)
        handle.write('\n')

    print(f'Dados guardados em {config.output_file}')
    return data
