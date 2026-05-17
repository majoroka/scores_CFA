import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Optional
from urllib.parse import urlparse

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

SESSION_IMPERSONATION = "chrome124"
BLOCK_COOLDOWN_SECONDS = int(os.environ.get("FPF_BLOCK_COOLDOWN_SECONDS", "45"))

_SESSION = None
_LAST_SUCCESSFUL_URL = None
_BLOCKED_UNTIL = 0.0


@dataclass
class FetchResult:
    ok: bool
    content: Optional[str]
    url: str
    status_code: Optional[int] = None
    error_type: Optional[str] = None
    blocked: bool = False
    attempts: int = 0
    duration_seconds: float = 0.0
    response_size: int = 0
    cache_used: bool = False
    error_message: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def _build_session():
    return requests.Session(
        impersonate=SESSION_IMPERSONATION,
        headers=DEFAULT_HEADERS,
    )


def _get_session():
    global _SESSION
    if _SESSION is None:
        _SESSION = _build_session()
    return _SESSION


def _reset_session():
    global _SESSION
    _SESSION = _build_session()
    return _SESSION


def _respect_block_cooldown():
    remaining = _BLOCKED_UNTIL - time.time()
    if remaining > 0:
        print(f"Cooling down for {int(remaining)}s after FPF block/rate limit")
        time.sleep(remaining)


def _mark_blocked():
    global _BLOCKED_UNTIL
    _BLOCKED_UNTIL = max(_BLOCKED_UNTIL, time.time() + BLOCK_COOLDOWN_SECONDS)


def _same_origin(left: str, right: str) -> bool:
    if not left or not right:
        return False
    left_parts = urlparse(left)
    right_parts = urlparse(right)
    return (
        left_parts.scheme == right_parts.scheme
        and left_parts.netloc == right_parts.netloc
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
    return fetch_page_result(
        url,
        cache_dir=cache_dir,
        use_cache=use_cache,
        cache_key=cache_key,
        verbose=verbose,
        max_retries=max_retries,
    ).content


def fetch_page_result(
    url: str,
    cache_dir: str,
    use_cache: bool,
    cache_key: str,
    verbose: bool = False,
    max_retries: int = 2,
):
    global _LAST_SUCCESSFUL_URL
    cache_path = os.path.join(cache_dir, f"{cache_key}.html")

    if use_cache and os.path.exists(cache_path):
        if verbose:
            print(f"Lendo do cache: {cache_key}")
        with open(cache_path, "r", encoding="utf-8") as handle:
            cached_content = handle.read()
        return FetchResult(
            ok=bool(cached_content),
            content=cached_content,
            url=url,
            attempts=0,
            duration_seconds=0.0,
            response_size=len(cached_content.encode("utf-8")),
            cache_used=True,
            error_type=None if cached_content else "empty_response",
            blocked=is_blocked_content(cached_content),
        )

    os.makedirs(cache_dir, exist_ok=True)

    last_error = None
    last_status_code = None
    last_content = None
    last_error_type = None
    total_started_at = time.time()
    for attempt in range(max_retries + 1):
        _respect_block_cooldown()
        if verbose:
            print(f"Buscando da web: {url}")
        try:
            session = _get_session()
            request_headers = dict(DEFAULT_HEADERS)
            if _LAST_SUCCESSFUL_URL and _same_origin(_LAST_SUCCESSFUL_URL, url):
                request_headers["Referer"] = _LAST_SUCCESSFUL_URL

            response = session.get(
                url,
                headers=request_headers,
                timeout=60,
            )
            last_status_code = response.status_code
            last_content = response.text
            if response.status_code == 429 and attempt < max_retries:
                last_error_type = "http_429"
                _mark_blocked()
                _reset_session()
                time.sleep(max(60, 10 * (attempt + 1)))
                continue
            if response.status_code >= 400:
                print(f"HTTP error {response.status_code} while requesting {url}")
                last_error_type = f"http_{response.status_code}"
                if response.status_code in {403, 429}:
                    _mark_blocked()
                if response.status_code == 403 and attempt < max_retries:
                    _reset_session()
                if attempt < max_retries:
                    time.sleep(max(5 * (attempt + 1), BLOCK_COOLDOWN_SECONDS))
                    continue
                return FetchResult(
                    ok=False,
                    content=last_content,
                    url=url,
                    status_code=response.status_code,
                    error_type=last_error_type,
                    blocked=response.status_code in {403, 429},
                    attempts=attempt + 1,
                    duration_seconds=round(time.time() - total_started_at, 2),
                    response_size=len((last_content or "").encode("utf-8")),
                    error_message=f"HTTP error {response.status_code}",
                )

            content = last_content
            if is_blocked_content(content):
                print(f"Blocked content while requesting {url}")
                last_error_type = "blocked_content"
                _mark_blocked()
                if attempt < max_retries:
                    _reset_session()
                if attempt < max_retries:
                    time.sleep(max(5 * (attempt + 1), BLOCK_COOLDOWN_SECONDS))
                    continue
                return FetchResult(
                    ok=False,
                    content=content,
                    url=url,
                    status_code=response.status_code,
                    error_type=last_error_type,
                    blocked=True,
                    attempts=attempt + 1,
                    duration_seconds=round(time.time() - total_started_at, 2),
                    response_size=len((content or "").encode("utf-8")),
                    error_message="Blocked content returned by origin",
                )
            if not content:
                last_error_type = "empty_response"
                if attempt < max_retries:
                    time.sleep(5 * (attempt + 1))
                    continue
                return FetchResult(
                    ok=False,
                    content=content,
                    url=url,
                    status_code=response.status_code,
                    error_type=last_error_type,
                    blocked=False,
                    attempts=attempt + 1,
                    duration_seconds=round(time.time() - total_started_at, 2),
                    response_size=0,
                    error_message="Empty response body",
                )
            _LAST_SUCCESSFUL_URL = url
            if use_cache:
                with open(cache_path, "w", encoding="utf-8") as handle:
                    handle.write(content)
            return FetchResult(
                ok=True,
                content=content,
                url=url,
                status_code=response.status_code,
                error_type=None,
                blocked=False,
                attempts=attempt + 1,
                duration_seconds=round(time.time() - total_started_at, 2),
                response_size=len(content.encode("utf-8")),
                cache_used=False,
            )
        except Exception as exc:
            last_error = exc
            if "timed out" in str(exc).lower():
                last_error_type = "timeout"
            else:
                last_error_type = "network_error"
            if attempt < max_retries:
                time.sleep(5 * (attempt + 1))
                continue

    if last_error is not None:
        print(f"Error requesting {url}: {last_error}")
    return FetchResult(
        ok=False,
        content=last_content,
        url=url,
        status_code=last_status_code,
        error_type=last_error_type or "network_error",
        blocked=bool(last_status_code in {403, 429}),
        attempts=max_retries + 1,
        duration_seconds=round(time.time() - total_started_at, 2),
        response_size=len((last_content or "").encode("utf-8")),
        error_message=str(last_error) if last_error is not None else None,
    )


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
