"""The published Jira and GitHub parameter tables match the component classes."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "docs" / "scripts" / "generate_integration_docs.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_integration_docs", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parameter_partials_match_the_components() -> None:
    generator = _load_generator()
    drifted = generator.write_partials(check=True)
    assert drifted == [], "run: uv run python docs/scripts/generate_integration_docs.py"


def test_every_capability_is_a_heading() -> None:
    generator = _load_generator()
    for spec in generator.BUNDLES:
        rendered = generator.render_partial(spec)
        manifest = json.loads(spec.manifest.read_text(encoding="utf-8"))
        for capability in manifest["capabilities"]:
            assert f"### {capability['display_name']}" in rendered
        assert "Do not edit." in rendered
