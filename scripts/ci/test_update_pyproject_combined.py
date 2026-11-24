"""Integration test for the coordinated nightly metadata rewrite."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import update_lf_base_dependency
import update_pyproject_combined
import update_pyproject_version
import update_uv_dependency


@pytest.mark.parametrize("strict_bundle", [False, True])
@pytest.mark.parametrize("operator", ["~=", "=="])
def test_full_base_chain_uses_unprefixed_exact_dev_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operator: str, *, strict_bundle: bool
) -> None:
    (tmp_path / "src/backend/base").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "langflow"\nversion = "1.12.0"\n'
        'dependencies = ["langflow-base~=1.12.0"]\n'
        "[project.optional-dependencies]\n"
        'audio = ["langflow-base[audio]~=1.12.0"]\n'
        'postgresql = ["langflow-base[postgresql]~=1.12.0"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src/backend/base/pyproject.toml").write_text(
        '[project]\nname = "langflow-base"\nversion = "1.12.0"\ndependencies = ["lfx~=1.12.0"]\n',
        encoding="utf-8",
    )
    if strict_bundle:
        bundle = tmp_path / "src/bundles/google"
        (bundle / "src/lfx_google").mkdir(parents=True)
        (bundle / "pyproject.toml").write_text(
            '[project]\nname = "lfx-google"\nversion = "0.3.3"\ndependencies = ["lfx>=1.12.0,<2.0.0"]\n',
            encoding="utf-8",
        )
        (bundle / "src/lfx_google/extension.json").write_text('{"version": "0.3.3"}\n', encoding="utf-8")
        root = tmp_path / "pyproject.toml"
        root.write_text(
            root.read_text().replace('"langflow-base~=1.12.0"', '"langflow-base~=1.12.0", "lfx-google>=0.3.3,<1"')
        )

    monkeypatch.setattr(update_pyproject_version, "BASE_DIR", tmp_path)
    monkeypatch.setattr(update_lf_base_dependency, "BASE_DIR", tmp_path)
    monkeypatch.setattr(update_uv_dependency, "BASE_DIR", tmp_path)
    monkeypatch.setattr(update_pyproject_combined, "BASE_DIR", tmp_path)

    if operator == "==":
        for path in [tmp_path / "pyproject.toml", tmp_path / "src/backend/base/pyproject.toml"]:
            path.write_text(path.read_text().replace("~=1.12.0", "==1.12.0"))

    update_pyproject_combined.update_projects_for_nightly("v1.12.0.dev26", "v1.12.0.dev26", "v1.12.0.dev7")

    main = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    base = (tmp_path / "src/backend/base/pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.12.0.dev26"' in main
    assert '"langflow-base==1.12.0.dev26"' in main
    assert '"langflow-base[audio]==1.12.0.dev26"' in main
    assert '"langflow-base[postgresql]==1.12.0.dev26"' in main
    assert 'version = "1.12.0.dev26"' in base
    assert '"lfx==1.12.0.dev7"' in base
    assert "v1.12" not in main + base
    if strict_bundle:
        assert '"lfx-google>=0.3.3.dev7,<1"' in main
        assert '"lfx==1.12.0.dev7"' in (bundle / "pyproject.toml").read_text()
        assert json.loads((bundle / "src/lfx_google/extension.json").read_text())["version"] == "0.3.3.dev7"
