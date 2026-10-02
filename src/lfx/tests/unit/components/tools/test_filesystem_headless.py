"""Standalone file continuity must coexist with authenticated user isolation."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent
from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.graph.graph.base import Graph
from lfx.run._defaults import apply_run_defaults
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.deps import get_settings_service


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path / "files"))
    monkeypatch.setenv("LANGFLOW_FS_TOOL_PEPPER_PATH", str(tmp_path / "pepper"))
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTO_LOGIN", False)


def component_for(graph: Graph) -> FileSystemToolComponent:
    component = FileSystemToolComponent(root_path="", read_only=False)
    graph.add_component(component)
    return component


@pytest.mark.parametrize("overwrite_user_id", [True, False], ids=["run", "serve"])
def test_files_survive_separate_runs_with_generated_identities(tmp_path: Path, *, overwrite_user_id: bool) -> None:
    first, second = Graph(), Graph()
    for graph in (first, second):
        apply_run_defaults(graph, session_id=None, user_id=None, overwrite_user_id=overwrite_user_id)
    writer, reader = component_for(first), component_for(second)

    assert first.user_id != second.user_id
    assert writer._write_file("notes.md", "persistent content")["status"] == "created"
    assert "persistent content" in reader._read_file("notes.md")["content"]
    assert (tmp_path / "files/shared/notes.md").read_text() == "persistent content"
    assert reader.build_metadata().data["mode"] == "shared"
    assert get_settings_service().auth_settings.AUTO_LOGIN is False


def test_explicit_uuid_identities_remain_isolated_and_stable() -> None:
    first_user, second_user = uuid4().hex, uuid4().hex
    components = []
    for user_id in (first_user, second_user, first_user):
        graph = Graph()
        apply_run_defaults(graph, session_id=None, user_id=user_id)
        components.append(component_for(graph))
    writer, other_user, same_user = components

    writer._write_file("notes.md", "private content")
    assert "error" in other_user._read_file("notes.md")
    assert "private content" in same_user._read_file("notes.md")["content"]
    assert writer.build_metadata().data["mode"] == "isolated"


def test_graph_pinned_user_does_not_become_shared() -> None:
    graph = Graph(user_id=uuid4().hex)
    apply_run_defaults(graph, session_id=None, user_id=None, overwrite_user_id=False)
    assert component_for(graph).build_metadata().data["mode"] == "isolated"


@pytest.mark.parametrize("kind", ["interactive_chat", "public_run", "headless_operator"])
def test_host_stamped_principals_do_not_gain_shared_storage(kind: str) -> None:
    graph = Graph()
    graph.execution_principal = ExecutionPrincipal(kind=kind, family="host_route")
    apply_run_defaults(graph, session_id=None, user_id=None)
    assert component_for(graph).build_metadata().data["mode"] == "isolated"


@pytest.mark.parametrize("boundary", ["force_isolation", "end_user", "verified_user", "changed_user"])
def test_authenticated_boundaries_override_generated_identity(boundary: str) -> None:
    graph = Graph()
    apply_run_defaults(graph, session_id=None, user_id=None)
    component = component_for(graph)
    component._write_file("notes.md", "standalone data")

    if boundary == "force_isolation":
        component._force_isolation = True
    elif boundary == "end_user":
        graph.end_user_id = uuid4().hex
    elif boundary == "verified_user":
        apply_run_defaults(graph, session_id=None, user_id=uuid4().hex)
    else:
        graph.user_id = uuid4().hex

    assert "error" in component._read_file("notes.md")
    assert component.build_metadata().data["mode"] == "isolated"


@pytest.mark.parametrize("copy_mode", ["deepcopy", "object_state", "repeat", "different_user"])
def test_runtime_provenance_survives_only_same_identity_reuse(copy_mode: str) -> None:
    graph = Graph()
    apply_run_defaults(graph, session_id=None, user_id=None)
    if copy_mode == "deepcopy":
        reused = copy.deepcopy(graph)
    elif copy_mode == "object_state":
        reused = Graph()
        reused.__setstate__(graph.__getstate__())
    elif copy_mode == "different_user":
        reused = graph.copy_for_run(user_id=uuid4().hex)
    else:
        reused = graph
    apply_run_defaults(reused, session_id=None, user_id=None, overwrite_user_id=False)
    expected_mode = "isolated" if copy_mode == "different_user" else "shared"
    assert component_for(reused).build_metadata().data["mode"] == expected_mode


def test_missing_identity_still_refuses_filesystem_access() -> None:
    component = component_for(Graph())
    assert "error" in component._write_file("notes.md", "should not be written")
    assert component.build_metadata().data["mode"] == "refused"


@pytest.mark.parametrize("identity", ["generated", "explicit", "host", "legacy", "mismatched", "verified_resume"])
def test_durable_checkpoint_preserves_filesystem_identity(identity: str) -> None:
    node = FileSystemToolComponent(root_path="project", read_only=False).to_frontend_node()
    graph = Graph.from_payload({"nodes": [node], "edges": []})
    user_id = uuid4().hex if identity == "explicit" else None
    apply_run_defaults(graph, session_id=None, user_id=user_id, overwrite_user_id=False)
    if identity == "host":
        graph.execution_principal = ExecutionPrincipal(kind="interactive_chat", family="host_route")
    graph.prepare()
    graph.set_run_id()
    writer = graph.vertices[0].custom_component
    assert writer._write_file("notes.md", "before pause")["status"] == "created"
    payload = graph.build_checkpoint().model_dump(mode="json")
    if identity == "legacy":
        payload.pop("headless_filesystem_user_id")
    elif identity == "mismatched":
        payload["headless_filesystem_user_id"] = uuid4().hex
    checkpoint = GraphCheckpoint.model_validate_json(json.dumps(payload))
    restored = Graph.resume_from_checkpoint(checkpoint)
    apply_run_defaults(
        restored,
        session_id=checkpoint.session_id,
        user_id=checkpoint.user_id if identity == "verified_resume" else None,
        overwrite_user_id=False,
    )
    reader = restored.vertices[0].custom_component
    assert reader.build_metadata().data["mode"] == ("shared" if identity == "generated" else "isolated")
    result = reader._read_file("notes.md")
    if identity in {"generated", "explicit", "host"}:
        assert "before pause" in result["content"]
    else:
        assert "error" in result


def test_updated_flow_export_preserves_files_when_loaded_for_separate_runs() -> None:
    node = FileSystemToolComponent(root_path="project", read_only=False).to_frontend_node()
    components = []
    for _ in range(2):
        graph = Graph.from_payload({"nodes": [copy.deepcopy(node)], "edges": []})
        apply_run_defaults(graph, session_id=None, user_id=None, overwrite_user_id=False)
        components.append(graph.vertices[0].custom_component)

    writer, reader = components
    assert writer._write_file("notes.md", "saved export content")["status"] == "created"
    assert "saved export content" in reader._read_file("notes.md")["content"]
    assert reader.build_metadata().data["mode"] == "shared"


def test_owner_selected_file_migration_keeps_other_users_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = component_for(Graph(user_id=uuid4().hex))
    other_user = component_for(Graph(user_id=uuid4().hex))
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTO_LOGIN", True)
    owner._write_file("notes.md", "existing shared file")
    shared_file = tmp_path / "files/shared/notes.md"

    monkeypatch.setattr(get_settings_service().auth_settings, "AUTO_LOGIN", False)
    assert "error" in owner._read_file("notes.md")
    destination = Path(owner.build_metadata().data["effective_root"])
    shutil.copy2(shared_file, destination / "notes.md")

    assert "existing shared file" in owner._read_file("notes.md")["content"]
    assert "error" in other_user._read_file("notes.md")
    assert shared_file.read_text() == "existing shared file"
