"""Download translated backend strings from GP and save as locale JSON files.

Downloads from the "langflow-backend" GP bundle (GP_BACKEND_BUNDLE env var)
into src/backend/base/langflow/locales/ — separate from the frontend locales.

Usage:
    python download_backend_translations.py
    python download_backend_translations.py --output path/to/locales/
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from gp_client import BASE_URL, GP_INSTANCE, TARGET_LANGS, get_headers

DEFAULT_OUTPUT = Path(__file__).parent.parent.parent / "src/backend/base/langflow/locales"
GP_BACKEND_BUNDLE = os.getenv("GP_BACKEND_BUNDLE", "langflow-backend")
REQUEST_TIMEOUT = 30


def get_backend_strings(lang: str) -> dict:
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BACKEND_BUNDLE}/{lang}"
    response = requests.get(
        url,
        headers=get_headers(url, "GET"),
        verify=False,  # noqa: S501
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download backend translations from GP")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Directory to save translated JSON files")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for lang in TARGET_LANGS:
        print(f"Downloading '{lang}' translations...")
        try:
            result = get_backend_strings(lang)

            strings = {
                key: entry.get("value", "") if isinstance(entry, dict) else entry
                for key, entry in result.get("resourceStrings", {}).items()
            }

            if not strings:
                print(f"  No strings yet for '{lang}' (translation may still be in progress)")
                continue

            output_file = output_dir / f"{lang}.json"
            output_file.write_text(
                json.dumps(strings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  Saved {len(strings)} strings to {output_file}")

        except Exception as e:  # noqa: BLE001
            print(f"  Error downloading '{lang}': {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
