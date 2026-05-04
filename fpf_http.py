import json
import os
import time

from curl_cffi import requests


DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

BLOCKED_MARKERS = (
    "Automated message",
    "Your IP address has been banned by automated security systems.",
    "Performing security verification",
    "Just a moment...",
)


def is_blocked_content(content: str) -> bool:
    if not content:
        return True
    return any(marker in content for marker in BLOCKED_MARKERS)


def get_page_content(
    url: str,
    cache_dir: str,
    use_cache: bool,
    cache_key: str,
    verbose: bool = False,
    max_retries: int = 2,
):
    cache_path = os.path.join(cache_dir, f"{cache_key}.html")

    if use_cache and os.path.exists(cache_path):
        if verbose:
            print(f"Lendo do cache: {cache_key}")
        with open(cache_path, "r", encoding="utf-8") as handle:
            return handle.read()

    os.makedirs(cache_dir, exist_ok=True)

    last_error = None
    for attempt in range(max_retries + 1):
        if verbose:
            print(f"Buscando da web: {url}")
        try:
            response = requests.get(
                url,
                headers=DEFAULT_HEADERS,
                impersonate="chrome124",
                timeout=60,
            )
            if response.status_code == 429 and attempt < max_retries:
                time.sleep(60)
                continue
            if response.status_code >= 400:
                print(f"HTTP error {response.status_code} while requesting {url}")
                if attempt < max_retries:
                    time.sleep(5 * (attempt + 1))
                    continue
                return None

            content = response.text
            if is_blocked_content(content):
                print(f"Blocked content while requesting {url}")
                if attempt < max_retries:
                    time.sleep(5 * (attempt + 1))
                    continue
                return None
            if use_cache:
                with open(cache_path, "w", encoding="utf-8") as handle:
                    handle.write(content)
            return content
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(5 * (attempt + 1))
                continue

    if last_error is not None:
        print(f"Error requesting {url}: {last_error}")
    return None


def load_existing_rounds(output_file: str):
    if not os.path.exists(output_file):
        return {}

    try:
        with open(output_file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return {}

    rounds = payload.get("rounds", [])
    if not isinstance(rounds, list):
        return {}

    existing = {}
    for round_data in rounds:
        fixture_id = round_data.get("fixtureId")
        if fixture_id:
            existing[str(fixture_id)] = round_data
    return existing
