import json
import os

from competition_configs import SENIORES
from competition_sync import run_sync

OUTPUT_FILE = 'data/seniores.json'


def main():
    selected_fixture_ids = []
    raw_selected_fixture_ids = os.environ.get("SELECTED_FIXTURE_IDS", "").strip()
    if raw_selected_fixture_ids:
        try:
            selected_fixture_ids = [str(value) for value in json.loads(raw_selected_fixture_ids)]
        except json.JSONDecodeError:
            selected_fixture_ids = []

    allow_full_discovery = os.environ.get("ALLOW_FULL_DISCOVERY", "1").strip().lower() not in {"0", "false", "no"}
    run_sync(
        SENIORES,
        selected_fixture_ids=selected_fixture_ids,
        allow_full_discovery=allow_full_discovery,
    )


if __name__ == '__main__':
    main()
