"""Bake i18n_key into noteNodes in starter template JSON files.

For each noteNode in every starter project JSON:
  - Compute the expected key: template_notes.{flow_key}.{sha256[:8]}
    where the hash is derived from the noteNode's description field.
  - If data.node.i18n_key already equals the expected key: leave it as-is.
  - Otherwise (missing or stale after an edit): assign the expected key.

This means keys are content-addressed — they change automatically when the
description changes, stay stable when nodes are reordered, and never silently
collide when a note is deleted and a new one added at the same position.

en.json is managed exclusively by extract_backend_strings.py — run that after
baking to pick up any new or changed note keys.

Usage (from repo root, no virtualenv required):
    python scripts/gp/bake_note_keys.py
    python scripts/gp/bake_note_keys.py --dry-run   # preview without writing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
STARTER_PROJECTS_DIR = REPO_ROOT / "src/backend/base/langflow/initial_setup/starter_projects"

# NOTE: _safe_flow_key and _note_hash are intentionally kept inline (not imported from
# langflow.utils.i18n_keys) because this script is designed to run WITHOUT a virtualenv —
# the CI workflow calls it before the Python environment is set up.  bake_note_keys.py
# only writes template_notes.{key} values that are read back verbatim by i18n.py at
# runtime, so a local drift here does NOT affect component-translation correctness.


def _safe_flow_key(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()


def _note_hash(description: str) -> str:
    return hashlib.sha256(description.encode()).hexdigest()[:8]


def _bake_file(path: Path, *, dry_run: bool) -> int:
    """Bake i18n_keys into a single template JSON file. Returns number of keys added/updated."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    name = data.get("name") or path.stem
    flow_key = _safe_flow_key(name)
    nodes = data.get("data", {}).get("nodes", [])

    keys_changed = 0

    for node in nodes:
        if node.get("type") != "noteNode":
            continue
        node_data = node["data"]["node"]
        description = node_data.get("description", "")
        expected = f"template_notes.{flow_key}.{_note_hash(description)}"

        if node_data.get("i18n_key") == expected:
            continue

        action = "updating" if "i18n_key" in node_data else "assigning"
        if not dry_run:
            node_data["i18n_key"] = expected
        print(f"  + {path.name}: {action} {expected!r}")
        keys_changed += 1

    if keys_changed > 0 and not dry_run:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return keys_changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing files")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN — no files will be modified.\n")

    total_changed = 0
    for project_file in sorted(STARTER_PROJECTS_DIR.glob("*.json")):
        total_changed += _bake_file(project_file, dry_run=args.dry_run)

    template_count = len(list(STARTER_PROJECTS_DIR.glob("*.json")))
    print(f"\nBaked {total_changed} i18n_key(s) across {template_count} templates.")
    if total_changed > 0 and not args.dry_run:
        print("Run extract_backend_strings.py to update en.json.")


if __name__ == "__main__":
    main()
