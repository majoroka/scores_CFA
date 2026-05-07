import html
import json
import os
import re
import time
import unicodedata

from competition_configs import CompetitionConfig
from fpf_http import get_page_content as fetch_page_content, load_existing_rounds

CACHE_DIR = 'cache'
USE_CACHE = False


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize('NFD', value)
    normalized = normalized.encode('ascii', 'ignore').decode('ascii')
    return normalized.lower().strip()


def _clean_text(value: str) -> str:
    value = re.sub(r'<br\s*/?>', ' ', value, flags=re.IGNORECASE)
    value = re.sub(r'<.*?>', '', value)
    return html.unescape(value).strip()


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


def run_sync(config: CompetitionConfig):
    main_page = get_page_content(config.competition_url, config.main_cache_key)
    if not main_page:
        print('Erro ao obter página principal da competição.')
        return

    fixture_ids = extract_fixture_ids(main_page, config)
    if not fixture_ids:
        print('Nenhum fixtureId encontrado para a série alvo.')
        return

    existing_rounds = load_existing_rounds(config.output_file)
    rounds = []
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
            else:
                print(f'Falha ao obter dados da jornada {index}')
            continue

        matches = parse_matches(fragment, strip_score_from_date=config.strip_score_from_date)
        classification = parse_classification(fragment)
        if not matches and not classification and existing_round:
            print(f'Jornada {index} sem dados novos; a reutilizar dados existentes.')
            rounds.append(existing_round)
            continue
        rounds.append({
            'index': index,
            'fixtureId': fixture_id,
            'matches': matches,
            'classification': classification,
        })
        time.sleep(1)

    if config.derive_classification:
        build_classification_from_results(rounds, config.ignored_team_names)

    valid_rounds = [
        round_data
        for round_data in rounds
        if round_data['matches'] or round_data['classification']
    ]
    if not valid_rounds:
        print('Nenhum dado válido foi extraído. O ficheiro existente não será alterado.')
        return

    if existing_rounds and len(rounds) < len(existing_rounds):
        print(
            f'Foram extraídas apenas {len(rounds)} jornadas, '
            f'mas o ficheiro atual tem {len(existing_rounds)}. '
            'O ficheiro existente não será alterado.'
        )
        return

    data = {'rounds': rounds}
    os.makedirs(os.path.dirname(config.output_file), exist_ok=True)
    with open(config.output_file, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4)

    print(f'Dados guardados em {config.output_file}')
