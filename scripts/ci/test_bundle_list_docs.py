"""The bundle list tables match the 1.14 package metadata."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "docs" / "scripts" / "generate_bundle_list.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_bundle_list", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bundle_list_matches_package_metadata() -> None:
    generator = _load_generator()
    drifted = generator.write_bundle_list(check=True)
    assert drifted == [], "run: uv run python docs/scripts/generate_bundle_list.py"
