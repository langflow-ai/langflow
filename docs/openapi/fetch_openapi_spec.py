#!/usr/bin/env python3
"""Pull OpenAPI spec files from the langflow-ai/sdk repository.

Usage:
    python3 fetch_openapi_spec.py                          # Download all files
    python3 fetch_openapi_spec.py --file <filename>       # Download specific file
    python3 fetch_openapi_spec.py --branch <branch>       # Use different branch
"""

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = "langflow-ai/sdk"
BRANCH = "main"
SPECS_DIR = "specs"
FILES = ["langflow-workflows-openapi.json", "langflow-openapi.json"]


def fetch_file(repo: str, filepath: str, branch: str) -> str:
    """Fetch and decode file from GitHub."""
    url = f"https://api.github.com/repos/{repo}/contents/{filepath}?ref={branch}"
    with urllib.request.urlopen(url) as r:  # noqa: S310
        data = json.loads(r.read().decode())
        return base64.b64decode(data["content"]).decode("utf-8")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", action="append", dest="files")
    parser.add_argument("--branch", default=BRANCH)
    args = parser.parse_args()

    files = args.files or FILES
    local_dir = Path(__file__).parent

    for filename in files:
        if filename not in FILES:
            sys.stderr.write(f"Error: {filename} not in {FILES}\n")
            sys.exit(1)

        try:
            content = fetch_file(REPO, f"{SPECS_DIR}/{filename}", args.branch)
            (local_dir / filename).write_text(content, encoding="utf-8")
            sys.stdout.write(f"✓ {filename}\n")
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
            sys.stderr.write(f"✗ {filename}: {e}\n")
            sys.exit(1)


if __name__ == "__main__":
    main()
