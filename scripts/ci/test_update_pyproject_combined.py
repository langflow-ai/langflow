"""Integration test for the coordinated nightly metadata rewrite."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import update_lf_base_dependency
import update_pyproject_combined
import update_pyproject_version
import update_uv_dependency


def test_full_core_base_chain_uses_unprefixed_exact_dev_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src/backend/base").mkdir(parents=True)
    (tmp_path / "src/langflow-core").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "langflow"\nversion = "1.11.0"\n'
        'dependencies = ["langflow-core~=1.11.0"]\n'
        "[project.optional-dependencies]\n"
        'audio = ["langflow-core[audio]~=1.11.0"]\n'
        'postgresql = ["langflow-core[postgresql]~=1.11.0"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src/langflow-core/pyproject.toml").write_text(
        '[project]\nname = "langflow-core"\nversion = "1.11.0"\n'
        'dependencies = ["langflow-base[complete]~=0.11.0"]\n'
        "[project.optional-dependencies]\n"
        'audio = ["langflow-base[audio]~=0.11.0"]\n'
        'postgresql = ["langflow-base[postgresql]~=0.11.0"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src/backend/base/pyproject.toml").write_text(
        '[project]\nname = "langflow-base"\nversion = "0.11.0"\ndependencies = ["lfx~=1.11.0"]\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(update_pyproject_version, "BASE_DIR", tmp_path)
    monkeypatch.setattr(update_lf_base_dependency, "BASE_DIR", tmp_path)
    monkeypatch.setattr(update_uv_dependency, "BASE_DIR", tmp_path)

    update_pyproject_combined.update_projects_for_nightly("v1.11.0.dev26", "v1.11.0.dev26", "v1.11.0.dev7")

    main = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    core = (tmp_path / "src/langflow-core/pyproject.toml").read_text(encoding="utf-8")
    base = (tmp_path / "src/backend/base/pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.11.0.dev26"' in main
    assert '"langflow-core==1.11.0.dev26"' in main
    assert '"langflow-core[audio]==1.11.0.dev26"' in main
    assert '"langflow-core[postgresql]==1.11.0.dev26"' in main
    assert 'version = "1.11.0.dev26"' in core
    assert '"langflow-base[complete]==1.11.0.dev26"' in core
    assert '"langflow-base[audio]==1.11.0.dev26"' in core
    assert '"langflow-base[postgresql]==1.11.0.dev26"' in core
    assert 'version = "1.11.0.dev26"' in base
    assert '"lfx==1.11.0.dev7"' in base
    assert "v1.11" not in main + core + base
