"""Upload English source strings to GP.

Usage:
    python upload_strings.py --source path/to/en.json
"""

import argparse
import json
from pathlib import Path

from gp_client import GP_BUNDLE, create_bundle, list_bundles, upload_strings


def main():
    parser = argparse.ArgumentParser(description="Upload strings to GP")
    parser.add_argument("--source", required=True, help="Path to English source JSON file")
    args = parser.parse_args()

    # Load source strings
    strings = json.loads(Path(args.source).read_text(encoding="utf-8"))
    print(f"Loaded {len(strings)} strings from {args.source}")

    # Create bundle if it doesn't exist
    existing = list_bundles()
    if GP_BUNDLE not in existing.get("bundleIds", []):
        print(f"Creating bundle '{GP_BUNDLE}'...")
        create_bundle()
        print("Bundle created.")
    else:
        print(f"Bundle '{GP_BUNDLE}' already exists, skipping creation.")

    # Upload English strings
    print(f"Uploading strings to GP bundle '{GP_BUNDLE}'...")
    result = upload_strings(strings)
    print(f"Done: {result}")


if __name__ == "__main__":
    main()
