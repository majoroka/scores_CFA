import json
from datetime import datetime, timezone
from pathlib import Path

from competition_configs import ALL_COMPETITIONS
from competition_sync import collect_quality_metrics, infer_payload_status


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
OUTPUT_PATH = DATA_DIR / 'status.json'


def load_payload(path: Path):
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def build_competition_status(config, payload):
    rounds = payload.get('rounds', []) if isinstance(payload, dict) else []
    quality = payload.get('dataQuality') if isinstance(payload, dict) else None
    if not isinstance(quality, dict):
        quality = collect_quality_metrics(rounds)

    source_health = payload.get('sourceHealth', {}) if isinstance(payload, dict) else {}
    fallback_reuse_count = source_health.get('fallbackReuseCount', 0)
    if not isinstance(fallback_reuse_count, int):
        fallback_reuse_count = 0

    status = infer_payload_status(fallback_reuse_count, quality)

    return {
        'status': status,
        'lastUpdatedAt': payload.get('lastUpdatedAt'),
        'fallbackReuseCount': fallback_reuse_count,
        'matchesWithoutScore': quality.get('matchesWithoutScore', 0),
        'pastMatchesWithoutScore': quality.get('pastMatchesWithoutScore', 0),
        'matchCount': quality.get('matchCount', 0),
        'completedMatchCount': quality.get('completedMatchCount', 0),
        'roundCount': quality.get('roundCount', 0),
        'teamCount': quality.get('teamCount', 0),
        'roundsWithCompletedMatches': quality.get('roundsWithCompletedMatches', 0),
        'issues': list(source_health.get('issues', [])) if isinstance(source_health.get('issues', []), list) else [],
        'title': config.title,
        'subtitle': config.subtitle,
        'pagePath': config.page_path,
        'outputFile': config.output_file,
    }


def build_status_payload():
    competitions = {}
    for config in ALL_COMPETITIONS:
        payload = load_payload(ROOT / config.output_file)
        if not isinstance(payload, dict):
            competitions[config.key] = {
                'status': 'missing',
                'lastUpdatedAt': None,
                'fallbackReuseCount': 0,
                'matchesWithoutScore': 0,
                'pastMatchesWithoutScore': 0,
                'matchCount': 0,
                'completedMatchCount': 0,
                'roundCount': 0,
                'teamCount': 0,
                'roundsWithCompletedMatches': 0,
                'issues': ['payload missing'],
                'title': config.title,
                'subtitle': config.subtitle,
                'pagePath': config.page_path,
                'outputFile': config.output_file,
            }
            continue
        competitions[config.key] = build_competition_status(config, payload)

    counts = {'ok': 0, 'partial': 0, 'degraded': 0, 'missing': 0}
    for entry in competitions.values():
        status = entry.get('status')
        if status in counts:
            counts[status] += 1

    return {
        'generatedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'competitionCount': len(competitions),
        'statusCounts': counts,
        'competitions': competitions,
    }


def write_status(payload):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def main():
    payload = build_status_payload()
    write_status(payload)
    print(f'Status generated for {payload["competitionCount"]} competitions in {OUTPUT_PATH.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
