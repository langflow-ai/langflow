"""
Download translated strings from GP and save as locale JSON files.

Usage:
    python download_translations.py --output path/to/locales/
"""
import json
import os
import argparse
from gp_client import get_strings, TARGET_LANGS, GP_BUNDLE


def main():
    parser = argparse.ArgumentParser(description="Download translations from GP")
    parser.add_argument('--output', required=True, help='Directory to save translated JSON files')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    for lang in TARGET_LANGS:
        print(f"Downloading '{lang}' translations...")
        try:
            result = get_strings(lang)

            # Extract just the key:value strings from the response
            strings = {
                key: entry.get('value', '') if isinstance(entry, dict) else entry
                for key, entry in result.get('resourceStrings', {}).items()
            }

            if not strings:
                print(f"  No strings yet for '{lang}' (translation may still be in progress)")
                continue

            output_file = os.path.join(args.output, f"{lang}.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(strings, f, ensure_ascii=False, indent=2)

            print(f"  Saved {len(strings)} strings to {output_file}")

        except Exception as e:
            print(f"  Error downloading '{lang}': {e}")

    print("\nDone.")


if __name__ == '__main__':
    main()
