"""Standalone file continuity must coexist with authenticated user isolation."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent
from lfx.graph.graph.base import Graph
from lfx.run._defaults import apply_run_defaults
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.deps import get_settings_service

if TYPE_CHECKING:
    from pathlib import Path


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


@pytest.mark.parametrize("copy_mode", ["deepcopy", "checkpoint", "repeat", "different_user"])
def test_runtime_provenance_survives_only_same_identity_reuse(copy_mode: str) -> None:
    graph = Graph()
    apply_run_defaults(graph, session_id=None, user_id=None)
    if copy_mode == "deepcopy":
        reused = copy.deepcopy(graph)
    elif copy_mode == "checkpoint":
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
