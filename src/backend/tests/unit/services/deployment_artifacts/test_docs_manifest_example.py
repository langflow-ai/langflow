"""INT-13: the documented artifact manifest matches the one the builder emits.

``docs/docs/Lfx/lfx-connections.mdx`` shows a project-artifact manifest so a
deployment operator can read `required_connections` before anything runs. That
example is prose, not generated, so this test pins it to the builder: a field
renamed in ``ProjectArtifactRequiredConnection`` or a changed `schema_version`
rule breaks the test instead of silently making the page wrong.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest
from langflow.services.deployment_artifacts import ProjectArtifactRequiredConnection

_DOCS_PAGE = Path(__file__).resolve().parents[6] / "docs" / "docs" / "Lfx" / "lfx-connections.mdx"

_CONNECTION_SCHEMA_VERSION = 4


def _documented_manifest() -> dict:
    page = _DOCS_PAGE.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", page, flags=re.DOTALL)
    manifests = [json.loads(block) for block in blocks if '"schema_version"' in block]
    assert len(manifests) == 1, "lfx-connections.mdx must show exactly one artifact manifest example"
    return manifests[0]


@pytest.mark.skipif(not _DOCS_PAGE.is_file(), reason=f"docs page not present at {_DOCS_PAGE}")
def test_documented_manifest_matches_the_builder_shape() -> None:
    manifest = _documented_manifest()
    connection_fields = {field.name for field in dataclasses.fields(ProjectArtifactRequiredConnection)}

    assert manifest["schema_version"] == _CONNECTION_SCHEMA_VERSION
    assert set(manifest) == {
        "schema_version",
        "project",
        "required_variables",
        "required_connections",
        "flows",
    }
    for entry in manifest["required_connections"]:
        assert set(entry) == connection_fields
    for flow in manifest["flows"]:
        assert set(flow) == {
            "id",
            "path",
            "sha256",
            "size",
            "required_variables",
            "required_connections",
        }
        for entry in flow["required_connections"]:
            assert set(entry) == connection_fields
