"""Upload English source strings to GP.

Usage:
    python upload.py --target frontend --source path/to/en.json
    python upload.py --target backend [--source path/to/en.json]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from gp_client import (
    BASE_URL,
    GP_BUNDLE,
    GP_INSTANCE,
    TARGET_LANGS,
    create_bundle,
    get_headers,
    list_bundles,
    upload_strings,
)

DEFAULT_BACKEND_SOURCE = Path(__file__).parent.parent.parent / "src/backend/base/langflow/locales/en.json"
GP_BACKEND_BUNDLE = os.getenv("GP_BACKEND_BUNDLE", "langflow-ui-backend-v2")
BACKEND_REQUEST_TIMEOUT = 300  # 5 minutes — single PUT with full payload


def upload_backend_strings(strings: dict, lang: str = "en") -> None:
    """Upload all backend strings in a single PUT request.

    GP's PUT replaces the entire bundle content, so chunking is not safe —
    each chunk would overwrite the previous one. We send everything at once
    with an extended timeout instead.
    """
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BACKEND_BUNDLE}/{lang}"
    response = requests.put(
        url,
        headers=get_headers(url, "PUT", strings),
        json=strings,
        verify=False,  # noqa: S501
        timeout=BACKEND_REQUEST_TIMEOUT,
    )
    response.raise_for_status()


def create_backend_bundle(source_lang: str = "en") -> dict:
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BACKEND_BUNDLE}"
    body = {"sourceLanguage": source_lang, "targetLanguages": TARGET_LANGS}
    response = requests.put(
        url,
        headers=get_headers(url, "PUT", body),
        json=body,
        verify=False,  # noqa: S501
        timeout=BACKEND_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload strings to GP")
    parser.add_argument("--target", required=True, choices=["frontend", "backend"], help="Which bundle to upload to")
    parser.add_argument("--source", help="Path to English source JSON file")
    args = parser.parse_args()

    if args.target == "frontend":
        source_path = Path(args.source) if args.source else None
        if source_path is None:
            parser.error("--source is required for --target frontend")
        if not source_path.exists():
            print(f"ERROR: {source_path} not found.")
            raise SystemExit(1)

        strings = json.loads(source_path.read_text(encoding="utf-8"))
        print(f"Loaded {len(strings)} strings from {source_path}")

        existing = list_bundles()
        if GP_BUNDLE not in existing.get("bundleIds", []):
            print(f"Creating bundle '{GP_BUNDLE}'...")
            create_bundle()
            print("Bundle created.")
        else:
            print(f"Bundle '{GP_BUNDLE}' already exists, skipping creation.")

        print(f"Uploading strings to GP bundle '{GP_BUNDLE}'...")
        result = upload_strings(strings)
        print(f"Done: {result}")

    else:  # backend
        source_path = Path(args.source) if args.source else DEFAULT_BACKEND_SOURCE
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

        print(f"Uploading {len(strings)} strings to GP bundle '{GP_BACKEND_BUNDLE}' (instance: {GP_INSTANCE})...")
        upload_backend_strings(strings)
        print("Done.")


if __name__ == "__main__":
    main()
