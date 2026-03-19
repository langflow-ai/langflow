"""Upload backend English source strings to GP as a separate bundle.

Uses GP_BACKEND_BUNDLE env var (default: "langflow-backend") so backend
strings are kept separate from the frontend "langflow-ui" bundle.

Usage:
    python upload_backend_strings.py
    python upload_backend_strings.py --source path/to/en.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from gp_client import BASE_URL, GP_INSTANCE, TARGET_LANGS, create_bundle, get_headers, list_bundles

DEFAULT_SOURCE = Path(__file__).parent.parent.parent / "src/backend/base/langflow/locales/en.json"
GP_BACKEND_BUNDLE = os.getenv("GP_BACKEND_BUNDLE", "langflow-backend")
REQUEST_TIMEOUT = 30


def upload_backend_strings(strings: dict, lang: str = "en") -> dict:
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BACKEND_BUNDLE}/{lang}"
    response = requests.put(
        url,
        headers=get_headers(url, "PUT", strings),
        json=strings,
        verify=False,  # noqa: S501
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def create_backend_bundle(source_lang: str = "en") -> dict:
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BACKEND_BUNDLE}"
    body = {"sourceLanguage": source_lang, "targetLanguages": TARGET_LANGS}
    response = requests.put(
        url,
        headers=get_headers(url, "PUT", body),
        json=body,
        verify=False,  # noqa: S501
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload backend strings to GP")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to backend en.json")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"ERROR: {source_path} not found. Run extract_backend_strings.py first.")
        raise SystemExit(1)

    strings = json.loads(source_path.read_text(encoding="utf-8"))
    print(f"Loaded {len(strings)} strings from {source_path}")

    existing = list_bundles()
    if GP_BACKEND_BUNDLE not in existing.get("bundleIds", []):
        print(f"Creating bundle '{GP_BACKEND_BUNDLE}'...")
        create_backend_bundle()
        print("Bundle created.")
    else:
        print(f"Bundle '{GP_BACKEND_BUNDLE}' already exists, skipping creation.")

    print(f"Uploading strings to GP bundle '{GP_BACKEND_BUNDLE}'...")
    result = upload_backend_strings(strings)
    print(f"Done: {result}")


if __name__ == "__main__":
    main()
