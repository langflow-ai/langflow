"""Regression tests for the nightly LFX version rewrite."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import orjson
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import update_lfx_version as mod


@pytest.fixture
def nightly_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Create the LFX metadata files changed by the nightly tag job."""
    pyproject_path = tmp_path / "src" / "lfx" / "pyproject.toml"
    pyproject_path.parent.mkdir(parents=True)
    pyproject_path.write_text(
        '[project]\nname = "lfx"\nversion = "1.11.0"\ndependencies = ["langflow-sdk>=0.3.0"]\n',
        encoding="utf-8",
    )

    index_path = pyproject_path.parent / "src" / "lfx" / "_assets" / "component_index.json"
    index_path.parent.mkdir(parents=True)
    index = {
        "entries": [["input_output", {"ChatInput": {"template": {}}}]],
        "metadata": {"num_components": 1, "num_modules": 1},
        "version": "1.11.0",
    }
    payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
    index["sha256"] = hashlib.sha256(payload).hexdigest()
    index_path.write_bytes(orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2))

    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)

    def update_temp_pyproject(relative_path: str, version: str) -> None:
        path = tmp_path / relative_path
        content = path.read_text(encoding="utf-8")
        content = re.sub(r'(?m)^version = "[^"]+"$', f'version = "{version}"', content, count=1)
        path.write_text(content, encoding="utf-8")

    monkeypatch.setattr(mod, "update_pyproject_version", update_temp_pyproject)
    return pyproject_path, index_path


def test_nightly_rewrite_keeps_component_index_in_lockstep(nightly_tree: tuple[Path, Path]) -> None:
    pyproject_path, index_path = nightly_tree

    mod.update_lfx_for_nightly("v1.11.0.dev45", "v0.3.0.dev45")

    assert 'version = "1.11.0.dev45"' in pyproject_path.read_text(encoding="utf-8")
    assert '"langflow-sdk==0.3.0.dev45"' in pyproject_path.read_text(encoding="utf-8")

    index = orjson.loads(index_path.read_bytes())
    assert index["version"] == "1.11.0.dev45"
    assert index["entries"] == [["input_output", {"ChatInput": {"template": {}}}]]
    assert index["metadata"] == {"num_components": 1, "num_modules": 1}
    assert index_path.read_bytes().endswith(b"\n")
    expected_hash = index.pop("sha256")
    payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
    assert hashlib.sha256(payload).hexdigest() == expected_hash
