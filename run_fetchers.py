import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
REPORT_PATH = CACHE_DIR / "fetch_report.json"
FETCH_TIMEOUT_SECONDS = 300
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (10, 30)


def discover_fetchers(selected_names=None):
    fetchers = sorted(
        path for path in ROOT.glob("fetch_*.py")
        if path.name != "run_fetchers.py"
    )
    if not selected_names:
        return fetchers
    selected = set(selected_names)
    return [path for path in fetchers if path.name in selected]


def extract_output_file(fetcher_path: Path):
    content = fetcher_path.read_text(encoding="utf-8")
    match = re.search(r'OUTPUT_FILE\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError(f"OUTPUT_FILE not found in {fetcher_path.name}")
    return ROOT / match.group(1)


def load_snapshot(json_path: Path):
    if not json_path.exists():
        return {
            "exists": False,
            "round_count": 0,
            "match_count": 0,
            "classification_count": 0,
            "round_indexes": [],
        }

    with open(json_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    rounds = payload.get("rounds")
    if not isinstance(rounds, list):
        raise ValueError(f"{json_path.name}: 'rounds' is not a list")

    match_count = 0
    classification_count = 0
    round_indexes = []
    for round_data in rounds:
        if not isinstance(round_data, dict):
            raise ValueError(f"{json_path.name}: invalid round entry")
        index = round_data.get("index")
        if not isinstance(index, int):
            raise ValueError(f"{json_path.name}: invalid round index")
        round_indexes.append(index)

        matches = round_data.get("matches")
        if not isinstance(matches, list):
            raise ValueError(f"{json_path.name}: 'matches' is not a list")
        match_count += len(matches)

        classification = round_data.get("classification")
        if not isinstance(classification, list):
            raise ValueError(f"{json_path.name}: 'classification' is not a list")
        classification_count += len(classification)

    if round_indexes != sorted(round_indexes):
        raise ValueError(f"{json_path.name}: round indexes are not sorted")
    if len(set(round_indexes)) != len(round_indexes):
        raise ValueError(f"{json_path.name}: duplicate round indexes")

    return {
        "exists": True,
        "round_count": len(rounds),
        "match_count": match_count,
        "classification_count": classification_count,
        "round_indexes": round_indexes,
    }


def is_valid_update(previous_snapshot, current_snapshot):
    if current_snapshot["round_count"] <= 0:
        return False, "no rounds extracted"
    if current_snapshot["match_count"] <= 0:
        return False, "no matches extracted"
    if (
        previous_snapshot["round_count"] > 0
        and current_snapshot["round_count"] < previous_snapshot["round_count"]
    ):
        return False, (
            f"round count shrank from {previous_snapshot['round_count']} "
            f"to {current_snapshot['round_count']}"
        )
    return True, None


def restore_backup(backup_path: Path, output_path: Path):
    if backup_path.exists():
        shutil.copy2(backup_path, output_path)
    elif output_path.exists():
        output_path.unlink()


def run_fetcher(fetcher_path: Path, output_path: Path):
    previous_snapshot = load_snapshot(output_path)
    backup_path = CACHE_DIR / f"{output_path.name}.bak"
    if output_path.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_path, backup_path)
    elif backup_path.exists():
        backup_path.unlink()

    attempts = []
    success = False
    final_snapshot = previous_snapshot
    changed = False

    for attempt_index in range(MAX_ATTEMPTS):
        delay_seconds = RETRY_DELAYS_SECONDS[min(attempt_index - 1, len(RETRY_DELAYS_SECONDS) - 1)] if attempt_index > 0 else 0
        if delay_seconds:
            time.sleep(delay_seconds)

        started_at = time.time()
        result = subprocess.run(
            [sys.executable, fetcher_path.name],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=FETCH_TIMEOUT_SECONDS,
        )

        attempt_report = {
            "attempt": attempt_index + 1,
            "returncode": result.returncode,
            "duration_seconds": round(time.time() - started_at, 2),
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
            "validation_error": None,
        }

        if result.returncode == 0:
            try:
                current_snapshot = load_snapshot(output_path)
                is_valid, reason = is_valid_update(previous_snapshot, current_snapshot)
                if is_valid:
                    final_snapshot = current_snapshot
                    changed = previous_snapshot != current_snapshot
                    success = True
                    attempts.append(attempt_report)
                    break
                attempt_report["validation_error"] = reason
            except Exception as exc:
                attempt_report["validation_error"] = str(exc)

        attempts.append(attempt_report)
        restore_backup(backup_path, output_path)

    if backup_path.exists():
        backup_path.unlink()

    return {
        "fetcher": fetcher_path.name,
        "output_file": str(output_path.relative_to(ROOT)),
        "success": success,
        "changed": changed,
        "previous_snapshot": previous_snapshot,
        "final_snapshot": final_snapshot,
        "attempts": attempts,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fetchers", nargs="*")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at_epoch": int(time.time()),
        "fetchers": [],
    }

    fetchers = discover_fetchers(args.fetchers)
    for fetcher_path in fetchers:
        output_path = extract_output_file(fetcher_path)
        print(f"RUN {fetcher_path.name} -> {output_path.relative_to(ROOT)}", flush=True)
        fetcher_report = run_fetcher(fetcher_path, output_path)
        report["fetchers"].append(fetcher_report)

        status = "OK" if fetcher_report["success"] else "FAIL"
        attempts_used = len(fetcher_report["attempts"])
        final_rounds = fetcher_report["final_snapshot"]["round_count"]
        changed_flag = "changed" if fetcher_report["changed"] else "unchanged"
        print(
            f"{status} {fetcher_path.name} "
            f"(attempts={attempts_used}, rounds={final_rounds}, {changed_flag})"
            ,
            flush=True,
        )

    report["success_count"] = sum(1 for item in report["fetchers"] if item["success"])
    report["failure_count"] = sum(1 for item in report["fetchers"] if not item["success"])
    report["changed_count"] = sum(1 for item in report["fetchers"] if item["changed"])

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print(
        "SUMMARY "
        f"success={report['success_count']} "
        f"failure={report['failure_count']} "
        f"changed={report['changed_count']}"
        ,
        flush=True,
    )


if __name__ == "__main__":
    main()
