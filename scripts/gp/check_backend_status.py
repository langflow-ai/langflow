"""Check translation progress for the backend GP bundle.

Queries GP for each target language and shows how many of the source keys
have been translated, without writing any files.

Usage:
    python scripts/gp/check_backend_status.py
    python scripts/gp/check_backend_status.py --watch      # re-check every 60s
    python scripts/gp/check_backend_status.py --watch 30   # re-check every 30s
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from gp_client import BASE_URL, GP_INSTANCE, TARGET_LANGS, get_headers

DEFAULT_SOURCE = Path(__file__).parent.parent.parent / "src/backend/base/langflow/locales/en.json"
GP_BACKEND_BUNDLE = os.getenv("GP_BACKEND_BUNDLE", "langflow-ui-backend-v2")
REQUEST_TIMEOUT = 60


def fetch_translated_count(lang: str, en_keys: set) -> tuple[int, int]:
    """Return (translated_count, total_count) for a language."""
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BACKEND_BUNDLE}/{lang}"
    response = requests.get(
        url,
        headers=get_headers(url, "GET"),
        verify=False,  # noqa: S501
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json().get("resourceStrings", {})
    translated = sum(1 for k in data if k in en_keys)
    return translated, len(en_keys)


def print_status(en_keys: set, comp_keys: set, other_keys: set) -> None:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    print(f"\n=== Backend translation status — {GP_BACKEND_BUNDLE} ({now}) ===")
    print(f"{'Lang':<10} {'Components':>20} {'Other':>15} {'Total':>15}")
    print("-" * 65)

    all_done = True
    for lang in TARGET_LANGS:
        try:
            url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BACKEND_BUNDLE}/{lang}"
            response = requests.get(
                url,
                headers=get_headers(url, "GET"),
                verify=False,  # noqa: S501  # Why: IBM GP's TLS cert has historically caused verification failures in CI
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json().get("resourceStrings", {})

            comp_done = sum(1 for k in data if k in comp_keys)
            other_done = sum(1 for k in data if k in other_keys)
            total_done = comp_done + other_done
            total = len(en_keys)

            comp_pct = comp_done / len(comp_keys) * 100 if comp_keys else 0
            total_pct = total_done / total * 100 if total else 0

            comp_str = f"{comp_done}/{len(comp_keys)} ({comp_pct:.1f}%)"
            other_str = f"{other_done}/{len(other_keys)}"
            total_str = f"{total_done}/{total} ({total_pct:.1f}%)"

            done_marker = "✓" if comp_done == len(comp_keys) else " "
            print(f"{done_marker} {lang:<8} {comp_str:>20} {other_str:>15} {total_str:>15}")

            if comp_done < len(comp_keys):
                all_done = False

        except Exception as e:  # noqa: BLE001
            print(f"  {lang:<8} ERROR: {e}")
            all_done = False

    print()
    if all_done:
        print("All languages fully translated. Run download_backend_translations.py to save.")
    else:
        print("Still in progress — run again later or use --watch to poll automatically.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check backend GP translation progress")
    parser.add_argument(
        "--watch",
        nargs="?",
        const=60,
        type=int,
        metavar="SECONDS",
        help="Poll repeatedly every N seconds (default 60)",
    )
    args = parser.parse_args()

    if not DEFAULT_SOURCE.exists():
        print(f"ERROR: {DEFAULT_SOURCE} not found. Run extract_backend_strings.py first.")
        raise SystemExit(1)

    en_data = json.loads(DEFAULT_SOURCE.read_text(encoding="utf-8"))
    en_keys = set(en_data.keys())
    comp_keys = {k for k in en_keys if k.startswith("components.")}
    other_keys = en_keys - comp_keys

    if args.watch is not None:
        interval = args.watch
        print(f"Watching every {interval}s — Ctrl+C to stop.")
        try:
            while True:
                print_status(en_keys, comp_keys, other_keys)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        print_status(en_keys, comp_keys, other_keys)


if __name__ == "__main__":
    main()
