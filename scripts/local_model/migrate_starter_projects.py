"""Idempotent migration script: starter project LanguageModelComponents → Langflow Model.

Walks every *.json in `src/backend/base/langflow/initial_setup/starter_projects/`,
locates LanguageModelComponent nodes, and sets their `model.value` to the curated
Langflow Model default ("qwen2.5:1.5b"). The unified-model resolver picks the
"Langflow Model" provider for that model name because that group sits first in
`get_models_detailed()` (see Slice 1).

Idempotent: running twice on a migrated tree is a no-op.

Usage:
    python -m scripts.local_model.migrate_starter_projects

Run from the repo root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LANGFLOW_LOCAL_DEFAULT_MODEL = "qwen2.5:1.5b"
STARTER_PROJECTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "backend"
    / "base"
    / "langflow"
    / "initial_setup"
    / "starter_projects"
)


def rewrite_flow(flow: dict) -> bool:
    """Rewrite every LanguageModelComponent node in `flow` in place.

    Returns True iff at least one node was actually modified (idempotent helper).
    """
    nodes = flow.get("data", {}).get("nodes")
    if not isinstance(nodes, list):
        return False

    changed = False
    for node in nodes:
        if not _is_language_model_node(node):
            continue
        model_field = node.get("data", {}).get("node", {}).get("template", {}).get("model")
        if not isinstance(model_field, dict):
            continue
        if model_field.get("value") == LANGFLOW_LOCAL_DEFAULT_MODEL:
            continue
        model_field["value"] = LANGFLOW_LOCAL_DEFAULT_MODEL
        changed = True
    return changed


def _is_language_model_node(node: dict) -> bool:
    return node.get("data", {}).get("type") == "LanguageModelComponent"


def migrate_directory(directory: Path) -> list[Path]:
    """Migrate every JSON file under `directory`. Returns list of files modified."""
    modified: list[Path] = []
    for path in sorted(directory.glob("*.json")):
        try:
            flow = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Defensive: a corrupted JSON in the tree must not abort the whole run.
            continue
        if rewrite_flow(flow):
            path.write_text(json.dumps(flow, indent=2, ensure_ascii=False), encoding="utf-8")
            modified.append(path)
    return modified


def main() -> int:
    if not STARTER_PROJECTS_DIR.exists():
        sys.stderr.write(f"Starter projects directory not found: {STARTER_PROJECTS_DIR}\n")
        return 1
    modified = migrate_directory(STARTER_PROJECTS_DIR)
    sys.stdout.write(f"Modified {len(modified)} starter project(s):\n")
    for p in modified:
        sys.stdout.write(f"  {p.name}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
