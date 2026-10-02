"""INT-13: the documented artifact manifest matches the one the builder emits.

``docs/docs/Lfx/lfx-connections.mdx`` shows a project-artifact manifest so a
deployment operator can read `required_connections` before anything runs. That
example is prose, not generated, so this test pins it to the builder: the key
sets it asserts come from a manifest ``build_project_artifact`` actually
produces, not from a literal copied out of the page. A field added, renamed or
dropped in ``builder.py`` or ``ProjectArtifactRequiredConnection`` breaks this
test instead of silently making the page wrong.
"""

from __future__ import annotations

import dataclasses
import io
import json
import re
import zipfile
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.database.models.folder.model import Folder
from langflow.services.deployment_artifacts import ProjectArtifactRequiredConnection

from .test_project_artifact import _build_authorized, _flow, _session_with_flows

_DOCS_PAGE = Path(__file__).resolve().parents[6] / "docs" / "docs" / "Lfx" / "lfx-connections.mdx"

_CONNECTION_SCHEMA_VERSION = 4

_CONNECTION_TEMPLATE = {
    "drive": {
        "name": "drive",
        "type": "connection_ref",
        "provider": "google",
        "value": "google/work",
        "required_scopes": ["https://www.googleapis.com/auth/drive.readonly"],
    }
}


def _documented_manifest() -> dict:
    page = _DOCS_PAGE.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", page, flags=re.DOTALL)
    manifests = [json.loads(block) for block in blocks if '"schema_version"' in block]
    assert len(manifests) == 1, "lfx-connections.mdx must show exactly one artifact manifest example"
    return manifests[0]


async def _built_manifest() -> dict:
    """Build a real connection-referencing artifact and return its manifest."""
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Marketing", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    flow.data = {"nodes": [{"data": {"node": {"template": _CONNECTION_TEMPLATE}}}], "edges": []}
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    artifact, *_ = await _build_authorized(session=session, user=user, project=project)

    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        return json.loads(archive.read("manifest.json"))


@pytest.mark.asyncio
@pytest.mark.skipif(not _DOCS_PAGE.is_file(), reason=f"docs page not present at {_DOCS_PAGE}")
async def test_documented_manifest_matches_the_builder_shape() -> None:
    documented = _documented_manifest()
    built = await _built_manifest()
    connection_fields = {field.name for field in dataclasses.fields(ProjectArtifactRequiredConnection)}

    # The rule the page states, asserted against the builder rather than restated.
    assert built["schema_version"] == _CONNECTION_SCHEMA_VERSION
    assert documented["schema_version"] == built["schema_version"]

    # Every key an operator would model from the page is a key the builder emits,
    # and the page omits none of them.
    assert set(documented) == set(built)
    assert set(documented["project"]) == set(built["project"])
    assert len(built["flows"]) == 1
    built_flow_keys = set(built["flows"][0])
    assert documented["flows"], "the example must show at least one flow entry"
    for documented_flow in documented["flows"]:
        assert set(documented_flow) == built_flow_keys

    for entry in documented["required_connections"]:
        assert set(entry) == connection_fields
    for entry in built["required_connections"]:
        assert set(entry) == connection_fields
    for documented_flow in documented["flows"]:
        for entry in documented_flow["required_connections"]:
            assert set(entry) == connection_fields
