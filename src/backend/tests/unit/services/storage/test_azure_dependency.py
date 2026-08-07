"""Packaging tests for the Azure Blob Storage dependency."""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def test_azure_extra_uses_azure_storage_blob_directly() -> None:
    pyproject_path = Path(__file__).resolve().parents[4] / "base" / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    expected_blob = "azure-storage-blob>=12.19.0,<13.0.0"
    expected_identity = "azure-identity>=1.15.0,<2.0.0"
    assert expected_blob in project["dependencies"]
    assert expected_identity in project["dependencies"]
    assert project["optional-dependencies"]["azure"] == [expected_blob, expected_identity]
