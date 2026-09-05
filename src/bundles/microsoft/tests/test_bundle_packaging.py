"""The shipped package must validate, load and be registered everywhere."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import lfx_microsoft
import pytest
from lfx.extension import load_extension, validate_extension
from lfx.extension.migration import MIGRATION_TABLE_PATH

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - the py3.10 matrix leg
    import tomli as tomllib

PACKAGE_ROOT = Path(lfx_microsoft.__file__).resolve().parent
BUNDLE_DIR = PACKAGE_ROOT.parents[1]
PYPROJECT = BUNDLE_DIR / "pyproject.toml"
CLASS_NAMES = (
    "OutlookCalendarCreateComponent",
    "OutlookCalendarListComponent",
    "OutlookSearchComponent",
    "OutlookSendComponent",
    "SharePointFetchComponent",
    "SharePointListComponent",
    "TeamsChannelPostComponent",
    "TeamsChatPostComponent",
)

requires_source_tree = pytest.mark.skipif(
    not PYPROJECT.exists(),
    reason="pyproject.toml is only present in a source checkout",
)


def test_extension_manifest_validates() -> None:
    result = validate_extension(PACKAGE_ROOT)
    assert result.ok, result.errors


def test_loader_exposes_the_components_and_the_capability_manifest() -> None:
    result = load_extension(PACKAGE_ROOT, distribution="lfx-microsoft")
    assert result.ok, result.errors
    assert {component.class_name for component in result.components} == set(CLASS_NAMES)
    assert len(result.integrations) == 1
    integration = result.integrations[0]
    assert integration.provider_id == "microsoft"
    assert integration.bundle == "microsoft"
    assert integration.capability_manifest.schema_version == 1
    assert len(integration.capability_manifest.capabilities) == 8


def test_capability_manifest_ships_inside_the_bundle_directory() -> None:
    manifest = json.loads((PACKAGE_ROOT / "extension.json").read_text(encoding="utf-8"))
    reference = manifest["integrations"][0]
    bundle_path = manifest["bundles"][0]["path"]
    assert (PACKAGE_ROOT / bundle_path / reference["path"]).is_file()


def test_migration_table_carries_a_bare_name_row_for_every_class() -> None:
    table = json.loads(MIGRATION_TABLE_PATH.read_text(encoding="utf-8"))
    rows = {
        entry["bare_class_name"]: entry for entry in table["entries"] if entry.get("bare_class_name") in CLASS_NAMES
    }
    assert set(rows) == set(CLASS_NAMES)
    for class_name, entry in rows.items():
        assert entry["target"] == f"ext:microsoft:{class_name}@official"
        assert entry["added_in"] == "1.13.0"


@requires_source_tree
def test_pyproject_declares_the_extension_entry_point_and_the_lfx_floor() -> None:
    meta = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = meta["project"]
    assert project["name"] == "lfx-microsoft"
    assert project["entry-points"]["langflow.extensions"] == {"lfx-microsoft": "lfx_microsoft"}
    assert project["dependencies"] == ["lfx>=1.13.0.dev0,<2.0.0"]


@requires_source_tree
def test_the_wheel_ships_the_manifest_and_the_capability_catalog() -> None:
    meta = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    include = meta["tool"]["hatch"]["build"]["targets"]["wheel"]["include"]
    assert "src/lfx_microsoft/extension.json" in include
    assert "src/lfx_microsoft/components/microsoft/capabilities.v1.json" in include


@requires_source_tree
def test_the_declared_version_matches_the_extension_manifest() -> None:
    meta = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    manifest = json.loads((PACKAGE_ROOT / "extension.json").read_text(encoding="utf-8"))
    assert manifest["version"] == meta["project"]["version"]
    assert manifest["id"] == "lfx-microsoft"
