"""Regression tests for the nightly full -> core dependency rewrite."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import update_uv_dependency as mod


def test_pins_root_core_and_optional_extras(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        "[project]\n"
        'dependencies = ["langflow-core~=1.11.0", "lfx-bundles>=1.1,<2.0"]\n'
        "[project.optional-dependencies]\n"
        'audio = ["langflow-core[audio]~=1.11.0"]\n'
        'postgresql = ["langflow-core[postgresql]>=1.11.0,<1.12.dev0"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)

    mod.update_uv_dep("1.11.0.dev26")

    result = path.read_text(encoding="utf-8")
    assert '"langflow-core==1.11.0.dev26"' in result
    assert '"langflow-core[audio]==1.11.0.dev26"' in result
    assert '"langflow-core[postgresql]==1.11.0.dev26"' in result
    assert '"lfx-bundles>=1.1,<2.0"' in result


def test_raises_without_core_dependency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\ndependencies = ["langflow-base~=0.11.0"]\n', encoding="utf-8")
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)

    with pytest.raises(ValueError, match="UV dependency not found"):
        mod.update_uv_dep("1.11.0.dev26")
