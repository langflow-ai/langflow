"""Bake i18n_key into noteNodes in starter template JSON files.

For each noteNode in every starter project JSON:
  - If data.node.i18n_key is already set: leave it as-is
  - If missing: assign template_notes.{flow_key}.{index} (index among noteNodes only)

en.json is managed exclusively by extract_backend_strings.py — run that after
baking to pick up any new or changed note keys.

Usage (from repo root, no virtualenv required):
    python scripts/gp/bake_note_keys.py
    python scripts/gp/bake_note_keys.py --dry-run   # preview without writing
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
STARTER_PROJECTS_DIR = REPO_ROOT / "src/backend/base/langflow/initial_setup/starter_projects"


def _safe_flow_key(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()


def _bake_file(path: Path, dry_run: bool) -> int:
    """Bake i18n_keys into a single template JSON file. Returns number of keys added."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    name = data.get("name") or path.stem
    flow_key = _safe_flow_key(name)
    nodes = data.get("data", {}).get("nodes", [])

    keys_added = 0
    note_idx = 0

    for node in nodes:
        if node.get("type") != "noteNode":
            continue
        node_data = node["data"]["node"]

        if "i18n_key" not in node_data:
            assigned = f"template_notes.{flow_key}.{note_idx}"
            if not dry_run:
                node_data["i18n_key"] = assigned
            print(f"  + {path.name}: assigning {assigned!r}")
            keys_added += 1

        note_idx += 1

    if keys_added > 0 and not dry_run:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return keys_added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing files")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN — no files will be modified.\n")

    total_added = 0
    for project_file in sorted(STARTER_PROJECTS_DIR.glob("*.json")):
        total_added += _bake_file(project_file, dry_run=args.dry_run)

    template_count = len(list(STARTER_PROJECTS_DIR.glob("*.json")))
    print(f"\nBaked {total_added} new i18n_key(s) across {template_count} templates.")
    if total_added > 0 and not args.dry_run:
        print("Run extract_backend_strings.py to update en.json.")


if __name__ == "__main__":
    main()
