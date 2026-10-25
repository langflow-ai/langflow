"""A deploy package names its stored files under the flow's own namespace.

The serving side runs every flow as one service account, so a file key namespaced to an
editor user is refused at read time there. The package rewrites those keys in transit, and
the cases that matter are the ones a wrong rewrite would hide: the stored flow changing, an
export to file being rewritten too, an unchanged flow looking edited on the next deploy, and
two files quietly merging onto one key.
"""

import io
import json
import zipfile
from copy import deepcopy
from uuid import uuid4

import pytest
from langflow.services.deployment_artifacts.builder import (
    ProjectArtifactError,
    ProjectArtifactLimits,
    _build_archive,
    _FlowSnapshot,
)

USER = str(uuid4())
OTHER_USER = str(uuid4())


def _file_node(node_id: str, value: object, *, slot: str = "file_path") -> dict:
    return {"id": node_id, "data": {"node": {"template": {"path": {"type": "file", slot: value}}}}}


def _snapshot(nodes: list, *, flow_id=None) -> _FlowSnapshot:
    return _FlowSnapshot(
        flow_id=flow_id or uuid4(),
        name="Docs",
        payload={"name": "Docs", "data": {"nodes": nodes, "edges": []}},
    )


def _build(*snapshots: _FlowSnapshot, rewrite: bool):
    return _build_archive(
        project_id=uuid4(),
        project_name="Project",
        snapshots=snapshots,
        limits=ProjectArtifactLimits(),
        rewrite_file_keys=rewrite,
    )


def _packaged_flow(artifact, flow_id) -> dict:
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        return json.loads(archive.read(f"flows/{flow_id}.json"))


def _packaged_path(artifact, flow_id) -> object:
    node = _packaged_flow(artifact, flow_id)["data"]["nodes"][0]
    return node["data"]["node"]["template"]["path"]["file_path"]


def test_should_rewrite_a_user_key_into_the_flow_namespace_when_deploying():
    snapshot = _snapshot([_file_node("File-a", f"{USER}/report.pdf")])

    artifact = _build(snapshot, rewrite=True)

    assert _packaged_path(artifact, snapshot.flow_id) == f"{snapshot.flow_id}/report.pdf"


def test_should_leave_the_stored_flow_untouched_when_the_package_is_rewritten():
    snapshot = _snapshot([_file_node("File-a", f"{USER}/report.pdf")])
    before = deepcopy(snapshot.payload)

    _build(snapshot, rewrite=True)

    assert snapshot.payload == before


def test_should_keep_the_saved_keys_when_not_deploying():
    snapshot = _snapshot([_file_node("File-a", f"{USER}/report.pdf")])

    artifact = _build(snapshot, rewrite=False)

    assert _packaged_path(artifact, snapshot.flow_id) == f"{USER}/report.pdf"


def test_should_produce_the_same_package_for_an_unchanged_flow():
    snapshot = _snapshot([_file_node("File-a", f"{USER}/report.pdf")])

    first = _build(snapshot, rewrite=True)
    second = _build(snapshot, rewrite=True)

    assert [flow.sha256 for flow in first.flows] == [flow.sha256 for flow in second.flows]


def test_should_rewrite_every_entry_of_a_list_field():
    snapshot = _snapshot([_file_node("File-a", [f"{USER}/a.pdf", f"{USER}/b.pdf"])])

    artifact = _build(snapshot, rewrite=True)

    assert _packaged_path(artifact, snapshot.flow_id) == [
        f"{snapshot.flow_id}/a.pdf",
        f"{snapshot.flow_id}/b.pdf",
    ]


def test_should_leave_a_path_that_is_not_a_storage_key_as_it_was():
    snapshot = _snapshot([_file_node("File-a", "/var/data/report.pdf")])

    artifact = _build(snapshot, rewrite=True)

    assert _packaged_path(artifact, snapshot.flow_id) == "/var/data/report.pdf"


def test_should_refuse_the_package_when_two_files_would_share_one_key():
    flow_id = uuid4()
    snapshot = _snapshot(
        [_file_node("File-a", f"{USER}/report.pdf"), _file_node("File-b", f"{OTHER_USER}/report.pdf")],
        flow_id=flow_id,
    )

    with pytest.raises(ProjectArtifactError) as raised:
        _build(snapshot, rewrite=True)

    message = str(raised.value)
    assert f"{USER}/report.pdf" in message
    assert f"{OTHER_USER}/report.pdf" in message
    assert f"{flow_id}/report.pdf" in message


def test_should_not_refuse_a_collision_when_not_deploying():
    snapshot = _snapshot([_file_node("File-a", f"{USER}/report.pdf"), _file_node("File-b", f"{OTHER_USER}/report.pdf")])

    _build(snapshot, rewrite=False)
