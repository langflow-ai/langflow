"""Packaging tests for the asynchronous S3 storage dependency."""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def test_async_s3_extras_use_aiobotocore_directly() -> None:
    pyproject_path = Path(__file__).resolve().parents[4] / "base" / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    expected = "aiobotocore>=3.7.0,<4.0.0"
    assert expected in project["dependencies"]
    assert project["optional-dependencies"]["aiobotocore"] == [expected]
    assert project["optional-dependencies"]["aioboto3"] == [expected]
