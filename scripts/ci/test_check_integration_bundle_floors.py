"""Integration references must be paired with a resolvable runtime floor."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_integration_bundle_floors import BASE_DIR, check_bundle, check_bundles
from sync_bundle_lfx_pin import sync_bundles


def _bundle(tmp_path: Path, dependencies: list[str], *, integrations: bool = True, kind: str = "json") -> Path:
    package = tmp_path / "google"
    source = package / "src" / "lfx_google"
    source.mkdir(parents=True)
    pyproject = package / "pyproject.toml"
    pyproject.write_text(f'[project]\nname = "lfx-google"\ndependencies = {json.dumps(dependencies)}\n')
    manifest = (
        {"integrations": [{"provider_id": "google", "bundle": "google", "path": "capabilities.v1.json"}]}
        if integrations
        else {}
    )
    if kind == "json":
        (source / "extension.json").write_text(json.dumps(manifest))
    else:
        with pyproject.open("a") as stream:
            stream.write(
                '\n[[tool.langflow.extension.integrations]]\nprovider_id = "google"\n'
                'bundle = "google"\npath = "capabilities.v1.json"\n'
            )
    return pyproject


@pytest.mark.parametrize("kind", ["json", "toml"])
@pytest.mark.parametrize(
    "dependency",
    [
        "lfx>=1.13.0.dev0,<2.0.0",
        "lfx>=1.13.0rc1,<2",
        "lfx>=1.13.0",
        "lfx==1.13.*",
        "lfx~=1.13.0",
        "LFX[otel]>=1.14.0",
    ],
)
def test_supported_floor(tmp_path: Path, kind: str, dependency: str) -> None:
    assert check_bundle(_bundle(tmp_path, [dependency], kind=kind)) == []


@pytest.mark.parametrize(
    "dependencies",
    [
        [],
        ["lfx"],
        ["lfx>=1.12.0,<2"],
        ["lfx<2"],
        ["lfx!=1.12.*"],
        ["lfx==1.*"],
        ["lfx>=1.13.0; python_version > '3.12'"],
        ["lfx @ https://example.com/lfx.whl"],
        ["lfx-google>=1.13.0"],
        ["lfx===1.13.0"],
    ],
)
def test_unsafe_or_missing_floor_is_actionable(tmp_path: Path, dependencies: list[str]) -> None:
    errors = check_bundle(_bundle(tmp_path, dependencies))
    assert len(errors) == 1
    assert "lfx>=1.13.0.dev0" in errors[0]
    assert "sync_bundle_lfx_pin.py 1.13.0" in errors[0]


def test_legacy_bundle_is_exempt(tmp_path: Path) -> None:
    assert check_bundle(_bundle(tmp_path, ["lfx>=1.12.0"], integrations=False)) == []


def test_explicit_empty_field_still_requires_schema_support(tmp_path: Path) -> None:
    pyproject = _bundle(tmp_path, ["lfx>=1.12.0"])
    (pyproject.parent / "src" / "lfx_google" / "extension.json").write_text('{"integrations": []}')
    assert "lfx>=1.13.0.dev0" in check_bundle(pyproject)[0]


def test_sync_script_repairs_the_floor_pairing(tmp_path: Path) -> None:
    pyproject = _bundle(tmp_path, ["lfx>=1.12.0.dev0,<2.0.0"])
    assert check_bundle(pyproject)
    assert sync_bundles("1.13.0", tmp_path) == [("google", True)]
    assert check_bundle(pyproject) == []
    assert sync_bundles("1.13.0", tmp_path) == [("google", False)]


def test_malformed_manifest_fails_instead_of_bypassing_guard(tmp_path: Path) -> None:
    pyproject = _bundle(tmp_path, ["lfx>=1.13.0"])
    (pyproject.parent / "src" / "lfx_google" / "extension.json").write_text("{")
    assert "cannot validate" in check_bundle(pyproject)[0]


def test_packaged_toml_manifest_also_requires_floor(tmp_path: Path) -> None:
    pyproject = _bundle(tmp_path, ["lfx>=1.12.0"], integrations=False)
    (pyproject.parent / "src" / "lfx_google" / "pyproject.toml").write_text(
        '[[tool.langflow.extension.integrations]]\nprovider_id = "google"\n'
        'bundle = "google"\npath = "capabilities.v1.json"\n'
    )
    assert "lfx>=1.13.0.dev0" in check_bundle(pyproject)[0]


def test_project_root_json_manifest_also_requires_floor(tmp_path: Path) -> None:
    pyproject = _bundle(tmp_path, ["lfx>=1.12.0"])
    source = pyproject.parent / "src" / "lfx_google" / "extension.json"
    source.rename(pyproject.parent / "extension.json")
    assert "lfx>=1.13.0.dev0" in check_bundle(pyproject)[0]


def test_repository_integration_bundle_floors() -> None:
    assert check_bundles(BASE_DIR / "src" / "bundles") == []
