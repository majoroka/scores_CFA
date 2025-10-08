import json
import os
import re
import time
import html
import urllib.request
import urllib.error
import unicodedata

COMPETITION_URL = "https://resultados.fpf.pt/Competition/Details?competitionId=28724&seasonId=105"
OUTPUT_FILE = "data/infantis-c.json"
CACHE_DIR = "cache"
USE_CACHE = False
TARGET_SERIE_NAME = "SÉRIE B"


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return normalized.lower().strip()


def _clean_text(value: str) -> str:
    value = re.sub('<br\\s*/?>', ' ', value, flags=re.IGNORECASE)
    value = re.sub('<.*?>', '', value)
    return html.unescape(value).strip()


def extract_fixture_ids(html_content: str, target_serie: str):
    normalized_target = _normalize(target_serie)
    pattern = re.compile(r'<div class="game-results[^>]*id="htmlSerieId_(\d+)"[^>]*>')
    for match in re.finditer(pattern, html_content):
        start = match.start()
        block_slice = html_content[start:]
        next_match = re.search(r'<div class="game-results', block_slice[1:])
        block = block_slice[: next_match.start() + 1] if next_match else block_slice
        block_normalized = _normalize(html.unescape(block))
        if normalized_target not in block_normalized:
            continue
        fixture_ids = []
        for fixture_id in re.findall(r'fixtureId=(\d+)', block):
            if fixture_id not in fixture_ids:
                fixture_ids.append(fixture_id)
        if fixture_ids:
            return fixture_ids
    return []


def parse_matches(html_fragment: str):
    matches = []
    pattern = re.compile(
        r'<div class="game"[\s\S]*?'
        r'<div class="home-team[^>]*>(.*?)</div>[\s\S]*?'
        r'<div class="[^>]*?text-center[^>]*>([\s\S]*?)</div>[\s\S]*?'
        r'<div class="away-team[^>]*>(.*?)</div>[\s\S]*?</div>\s*'
        r'<div class="game-list-stadium"[^>]*>[\s\S]*?<small[^>]*>(.*?)</small>',
        re.IGNORECASE
    )

    for home_html, center_html, away_html, stadium_html in re.findall(pattern, html_fragment):
        home = _clean_text(home_html)
        away = _clean_text(away_html)
        center = _clean_text(center_html)
        stadium = _clean_text(stadium_html)

        score_match = re.search(r'(\d{1,2})\s*[-–]\s*(\d{1,2})', center)
        time_match = re.search(r'(\d{1,2}:\d{2})', center)
        time_value = time_match.group(1) if time_match else ''
        date_value = center.replace(time_value, '').strip() if time_value else center

        matches.append({
            "home": home,
            "away": away,
            "date": date_value,
            "time": time_value,
            "stadium": stadium,
            "homeScore": int(score_match.group(1)) if score_match else None,
            "awayScore": int(score_match.group(2)) if score_match else None,
        })

    return matches


def parse_classification(html_fragment: str):
    classification = []
    section_match = re.search(
        r'<div id=\"classification\">([\s\S]*?)</div>\s*<div id=\"matches\">',
        html_fragment,
        re.IGNORECASE
    )
    section_html = section_match.group(1) if section_match else html_fragment
    row_pattern = re.compile(
        r'<div class=\"game classification[^\"]*\">\s*([\s\S]*?)\s*(?=</div><div class=\"game classification|</div>\s*</div>\s*<div id=\"matches\">)',
        re.IGNORECASE
    )
    rows = re.findall(row_pattern, section_html)
    for row_html in rows:
        cols = re.findall(r'<div class=\"[^>]*?col-[^\"]*\">([\s\S]*?)</div>', row_html)
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
            "position": pos,
            "team": team,
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goalsFor": goals_for,
            "goalsAgainst": goals_against,
            "points": points,
        })
    return classification


def get_page_content(url: str, cache_key: str):
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.html")

    if USE_CACHE and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as handle:
            return handle.read()

    os.makedirs(CACHE_DIR, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            content = response.read().decode("utf-8")
            if USE_CACHE:
                with open(cache_path, "w", encoding="utf-8") as handle:
                    handle.write(content)
            return content
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            time.sleep(60)
            return get_page_content(url, cache_key)
        print(f"HTTP error {exc.code} while requesting {url}")
    except Exception as exc:
        print(f"Error requesting {url}: {exc}")
    return None


def main():
    main_page = get_page_content(COMPETITION_URL, "infantis_c_competition_main")
    if not main_page:
        print("Erro ao obter página principal da competição.")
        return

    fixture_ids = extract_fixture_ids(main_page, TARGET_SERIE_NAME)
    if not fixture_ids:
        print("Nenhum fixtureId encontrado para a série alvo.")
        return

    rounds = []
    for index, fixture_id in enumerate(fixture_ids, start=1):
        print(f"Processando jornada {index} (fixtureId={fixture_id})")
        url = (
            "https://resultados.fpf.pt/Competition/"
            f"GetClassificationAndMatchesByFixture?fixtureId={fixture_id}"
        )
        fragment = get_page_content(url, f"infantis_c_fixture_{fixture_id}")
        if not fragment:
            print(f"Falha ao obter dados da jornada {index}")
            continue

        matches = parse_matches(fragment)
        classification = parse_classification(fragment)
        rounds.append({
            "index": index,
            "fixtureId": fixture_id,
            "matches": matches,
            "classification": classification,
        })
        time.sleep(1)

    data = {"rounds": rounds}
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
