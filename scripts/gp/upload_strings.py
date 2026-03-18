"""
Upload English source strings to GP.

Usage:
    python upload_strings.py --source path/to/en.json
"""
import json
import argparse
from gp_client import list_bundles, create_bundle, upload_strings, GP_BUNDLE


def main():
    parser = argparse.ArgumentParser(description="Upload strings to GP")
    parser.add_argument('--source', required=True, help='Path to English source JSON file')
    args = parser.parse_args()

    # Load source strings
    with open(args.source, 'r', encoding='utf-8') as f:
        strings = json.load(f)
    print(f"Loaded {len(strings)} strings from {args.source}")

    # Create bundle if it doesn't exist
    existing = list_bundles()
    if GP_BUNDLE not in existing.get('bundleIds', []):
        print(f"Creating bundle '{GP_BUNDLE}'...")
        create_bundle()
        print("Bundle created.")
    else:
        print(f"Bundle '{GP_BUNDLE}' already exists, skipping creation.")

    # Upload English strings
    print(f"Uploading strings to GP bundle '{GP_BUNDLE}'...")
    result = upload_strings(strings)
    print(f"Done: {result}")


if __name__ == '__main__':
    main()
