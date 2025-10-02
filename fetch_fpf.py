import json
import os
import re
import time
import html
import urllib.request
import urllib.error

# --- CONFIGURAÇÃO ---
COMPETITION_URL = "https://resultados.fpf.pt/Competition/Details?competitionId=28206&seasonId=105"
OUTPUT_FILE = "data/seniores.json"
CACHE_DIR = "cache"
USE_CACHE = False  # Mude para True para usar o cache após a primeira execução

# Nota: O parsing com regex é frágil. Se a FPF alterar o HTML do site,
# este script pode quebrar.

def find_fixture_ids(html_content):
    """Encontra todos os fixtureId's a partir dos links de jornadas."""
    # Novo padrão no site: links para /Competition/GetClassificationAndMatchesByFixture?fixtureId=600930
    fixture_ids = re.findall(r"GetClassificationAndMatchesByFixture\?fixtureId=(\d+)", html_content)
    valid_ids = [fid for fid in dict.fromkeys(fixture_ids) if fid]
    return sorted(valid_ids, key=int)

def _clean_text(s: str) -> str:
    s = re.sub('<br\s*/?>', ' ', s, flags=re.IGNORECASE)
    s = re.sub('<.*?>', '', s)
    return html.unescape(s).strip()

def parse_matches_from_fragment(html_fragment: str):
    """Extrai dados dos jogos de um fragmento HTML atual (secção #matches)."""
    matches = []
    # Captura o bloco central (pode ter hora ou resultado) para detectar score
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

        # Tenta extrair o resultado (ex.: 2-1). Caso contrário, extrai hora
        score_match = re.search(r'(\d{1,2})\s*[-–]\s*(\d{1,2})', center)
        time_match = re.search(r'(\d{1,2}:\d{2})', center)
        time_str = time_match.group(1) if time_match else ''
        date_str = center.replace(time_str, '').strip() if time_str else center

        match_data = {
            'home': home,
            'away': away,
            'date': date_str,
            'time': time_str,
            'stadium': stadium,
            'homeScore': int(score_match.group(1)) if score_match else None,
            'awayScore': int(score_match.group(2)) if score_match else None
        }
        matches.append(match_data)

    return matches

def parse_classification_from_fragment(html_fragment: str):
    """Extrai a classificação do HTML atual (secção #classification)."""
    classification = []
    # Trabalhar apenas dentro da secção de classificação
    section_match = re.search(r'<div id="classification">([\s\S]*?)</div>\s*<div id="matches">', html_fragment, re.IGNORECASE)
    section_html = section_match.group(1) if section_match else html_fragment

    # Cada linha
    rows = re.findall(r'<div class="game classification[^"]*">([\s\S]*?)</div>', section_html, re.IGNORECASE)
    for row_html in rows:
        cols = re.findall(r'<div class="[^>]*?col-.*?">([\s\S]*?)</div>', row_html)
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
            'points': points,
            'played': played,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'goalsFor': goals_for,
            'goalsAgainst': goals_against,
        })
    return classification

def parse_classification_from_fragment_v2(html_fragment: str):
    """Versão robusta: usa lookahead para delimitar linhas e extrai 9 colunas (POS, TEAM, JGS, V, E, D, GM, GS, PTS)."""
    classification = []
    section_match = re.search(r'<div id="classification">([\s\S]*?)</div>\s*<div id="matches">', html_fragment, re.IGNORECASE)
    section_html = section_match.group(1) if section_match else html_fragment
    row_pattern = re.compile(r'<div class="game classification[^\"]*">\s*([\s\S]*?)\s*(?=</div><div class="game classification|</div>\s*</div>\s*<div id="matches">)', re.IGNORECASE)
    rows = re.findall(row_pattern, section_html)
    for row_html in rows:
        cols = re.findall(r'<div class="[^>]*?col-[^\"]*">([\s\S]*?)</div>', row_html)
        if len(cols) < 9:
            continue
        try:
            pos = int(_clean_text(cols[0])); team = _clean_text(cols[1])
            played = int(_clean_text(cols[2])); wins = int(_clean_text(cols[3]))
            draws = int(_clean_text(cols[4])); losses = int(_clean_text(cols[5]))
            goals_for = int(_clean_text(cols[6])); goals_against = int(_clean_text(cols[7]))
            points = int(_clean_text(cols[8]))
        except ValueError:
            continue
        classification.append({
            'position': pos,
            'team': team,
            'points': points,
            'played': played,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'goalsFor': goals_for,
            'goalsAgainst': goals_against,
        })
    return classification


# --- FUNÇÕES AUXILIARES ---

def get_page_content(url, cache_key):
    """Busca conteúdo de uma URL, com suporte a cache e backoff."""
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.html")
    
    if USE_CACHE and os.path.exists(cache_path):
        print(f"Lendo do cache: {cache_key}")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read()

    print(f"Buscando da web: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
            if USE_CACHE:
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(cache_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            return content
    except urllib.error.HTTPError as e:
        if e.code == 429: # Too Many Requests
            print("Erro 429: Muitas requisições. Aguardando 60 segundos...")
            time.sleep(60)
            return get_page_content(url, cache_key) # Tenta novamente
        else:
            print(f"Erro HTTP ao buscar {url}: {e.code} {e.reason}")
            return None
    except Exception as e:
        print(f"Erro ao buscar {url}: {e}")
        return None

def main():
    """Função principal para orquestrar o scraping."""
    if COMPETITION_URL == "URL_DA_COMPETICAO_NA_FPF":
        print("ERRO: Por favor, edite 'scripts/fetch_fpf.py' e defina a 'COMPETITION_URL'.")
        return

    # 1. Buscar a página principal e encontrar os fixtureId's
    main_page_content = get_page_content(COMPETITION_URL, "main_competition_page")
    if not main_page_content:
        print("Não foi possível obter a página principal da competição.")
        return

    fixture_ids = find_fixture_ids(main_page_content)
    if not fixture_ids:
        print("Nenhum fixtureId encontrado. Verifique o seletor em 'find_fixture_ids'.")
        return
    
    print(f"Encontrados {len(fixture_ids)} fixtureId's (jornadas).")

    all_rounds_data = []
    
    # 2. Iterar por cada jornada para buscar jogos e classificação
    for i, fixture_id in enumerate(fixture_ids):
        round_number = i + 1
        print(f"\n--- Processando Jornada {round_number} (fixtureId: {fixture_id}) ---")

        combined_url = f"https://resultados.fpf.pt/Competition/GetClassificationAndMatchesByFixture?fixtureId={fixture_id}"
        combined_html = get_page_content(combined_url, f"combined_{fixture_id}")
        if not combined_html:
            print(f"Falha ao buscar dados para a jornada {round_number}. Pulando.")
            continue

        # Separa as secções por id
        matches_section = re.search(r'<div id="matches">([\s\S]*)$', combined_html, re.IGNORECASE)
        matches_html = matches_section.group(1) if matches_section else ''

        classification_html = combined_html  # A função interna faz recorte pela secção

        matches = parse_matches_from_fragment(matches_html)
        classification = parse_classification_from_fragment_v2(classification_html)

        all_rounds_data.append({
            "index": round_number,
            "fixtureId": fixture_id,
            "matches": matches,
            "classification": classification
        })
        time.sleep(1) # Pausa para não sobrecarregar o servidor

    # 3. Salvar o resultado final
    final_data = {"rounds": all_rounds_data}
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

    print(f"\nDados salvos com sucesso em '{OUTPUT_FILE}'!")

if __name__ == "__main__":
    main()
