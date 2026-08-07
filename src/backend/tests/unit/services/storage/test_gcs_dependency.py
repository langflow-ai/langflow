"""Packaging tests for the Google Cloud Storage dependency."""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def test_gcs_extra_uses_google_cloud_storage_directly() -> None:
    pyproject_path = Path(__file__).resolve().parents[4] / "base" / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    expected = "google-cloud-storage>=2.10.0,<4.0.0"
    assert expected in project["dependencies"]
    assert project["optional-dependencies"]["gcs"] == [expected]
