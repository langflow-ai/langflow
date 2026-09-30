from __future__ import annotations

import ast
import asyncio
import hashlib
import io
import json
import stat
import threading
import tracemalloc
import zipfile
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deployment_artifacts import (
    LFPKG_MEDIA_TYPE,
    EmptyProjectArtifactError,
    ProjectArtifactError,
    ProjectArtifactLimitError,
    ProjectArtifactLimits,
    ProjectArtifactNotFoundError,
    build_project_artifact,
)

MODULE = "langflow.services.deployment_artifacts.builder"
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _flow(*, flow_id: UUID | None = None, owner_id: UUID, project_id: UUID, name: str = "Flow") -> Flow:
    return Flow(
        id=flow_id or uuid4(),
        name=name,
        user_id=owner_id,
        folder_id=project_id,
        data={"nodes": [], "edges": []},
    )


def _session_with_flows(flows: list[Flow], *, repeats: int = 1) -> AsyncMock:
    ordered = sorted(flows, key=lambda flow: str(flow.id))
    pages = [ordered[index : index + 4] for index in range(0, len(ordered), 4)]
    results: list[MagicMock] = []
    for _ in range(repeats):
        revision_result = MagicMock()
        revision_result.all.return_value = [(flow.id, flow.user_id, flow.updated_at) for flow in ordered]
        results.append(revision_result)
        for page in pages:
            result = MagicMock()
            result.all.return_value = page
            results.append(result)
        final_revision_result = MagicMock()
        final_revision_result.all.return_value = [(flow.id, flow.user_id, flow.updated_at) for flow in ordered]
        results.append(final_revision_result)
    session = AsyncMock()
    session.exec.side_effect = results
    return session


async def _build_authorized(
    *,
    session: AsyncMock,
    user: SimpleNamespace,
    project: Folder,
    limits: ProjectArtifactLimits | None = None,
    flow_ids: list[UUID] | None = None,
):
    with (
        patch(f"{MODULE}.authorized_or_owner_scoped", new_callable=AsyncMock, return_value=project) as load_project,
        patch(f"{MODULE}.ensure_project_permission", new_callable=AsyncMock) as ensure_project,
        patch(f"{MODULE}.ensure_flows_permission", new_callable=AsyncMock) as ensure_flows,
    ):
        kwargs = {"limits": limits} if limits is not None else {}
        if flow_ids is not None:
            kwargs["flow_ids"] = flow_ids
        artifact = await build_project_artifact(session, user, project.id, **kwargs)
    return artifact, load_project, ensure_project, ensure_flows


def test_deployment_artifact_service_does_not_depend_on_api_or_fastapi() -> None:
    from langflow.services.deployment_artifacts import builder

    tree = ast.parse(Path(builder.__file__).read_text())
    imported_modules = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported_modules.update(
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert not any(module.startswith(("fastapi", "langflow.api")) for module in imported_modules)


@pytest.mark.asyncio
async def test_build_project_artifact_raises_domain_error_when_project_is_not_found() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    session = AsyncMock()
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with (
        patch(f"{MODULE}.authorized_or_owner_scoped", new_callable=AsyncMock, return_value=None),
        pytest.raises(ProjectArtifactNotFoundError, match="Project not found"),
    ):
        await build_project_artifact(session, user, project_id)

    session.exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_project_artifact_is_deterministic_and_manifest_binds_exact_flow_files() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Deterministic Project", user_id=actor_id)
    first_id = UUID("00000000-0000-0000-0000-000000000001")
    second_id = UUID("00000000-0000-0000-0000-000000000002")
    flows = [
        _flow(flow_id=second_id, owner_id=actor_id, project_id=project_id, name="Second"),
        _flow(flow_id=first_id, owner_id=actor_id, project_id=project_id, name="First"),
    ]
    session = _session_with_flows(flows, repeats=2)
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    first, *_ = await _build_authorized(session=session, user=user, project=project)
    second, *_ = await _build_authorized(session=session, user=user, project=project)

    assert first.content == second.content
    assert first.filename == f"langflow-project-{project_id}.lfpkg"
    assert first.media_type == LFPKG_MEDIA_TYPE
    assert first.project_id == project_id
    assert first.project_name == project.name
    assert first.flow_count == 2

    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        expected_names = [
            "manifest.json",
            f"flows/{first_id}.json",
            f"flows/{second_id}.json",
        ]
        assert archive.namelist() == expected_names
        for info in archive.infolist():
            assert info.date_time == FIXED_ZIP_TIMESTAMP
            assert info.compress_type == zipfile.ZIP_STORED
            assert stat.S_IMODE(info.external_attr >> 16) == 0o644

        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["schema_version"] == 1
        assert manifest["project"] == {"id": str(project_id), "name": project.name}
        assert manifest["required_variables"] == []
        assert [entry["id"] for entry in manifest["flows"]] == [str(first_id), str(second_id)]
        for entry in manifest["flows"]:
            payload = archive.read(entry["path"])
            assert entry["sha256"] == hashlib.sha256(payload).hexdigest()
            assert entry["size"] == len(payload)
            assert entry["required_variables"] == []


@pytest.mark.asyncio
async def test_build_project_artifact_omits_environment_specific_flow_fields() -> None:
    """Packaged flows must not carry identifiers of the deployment they came from."""
    actor_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    project = Folder(id=project_id, name="Portable Project", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id, name="Portable")
    flow.workspace_id = workspace_id
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    artifact, *_ = await _build_authorized(session=session, user=user, project=project)

    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        payload = archive.read(f"flows/{flow.id}.json")
        packaged = json.loads(payload)

    assert str(workspace_id) not in payload.decode()
    for field in ("workspace_id", "user_id", "folder_id", "updated_at"):
        assert field not in packaged


@pytest.mark.asyncio
async def test_build_project_artifact_packages_only_explicit_flow_ids() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Selected flows", user_id=actor_id)
    selected_id = UUID("00000000-0000-0000-0000-000000000001")
    unselected_id = UUID("00000000-0000-0000-0000-000000000002")
    selected = _flow(flow_id=selected_id, owner_id=actor_id, project_id=project_id, name="Selected")
    _ = _flow(flow_id=unselected_id, owner_id=actor_id, project_id=project_id, name="Unselected")
    session = _session_with_flows([selected])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    artifact, _, _, ensure_flows = await _build_authorized(
        session=session,
        user=user,
        project=project,
        flow_ids=[selected_id],
    )

    assert [flow.flow_id for flow in artifact.flows] == [selected_id]
    assert ensure_flows.await_args.kwargs["flow_ids"] == [selected_id]
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        assert archive.namelist() == ["manifest.json", f"flows/{selected_id}.json"]


@pytest.mark.asyncio
async def test_build_project_artifact_rejects_missing_or_duplicate_flow_selection() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Selected flows", user_id=actor_id)
    selected = _flow(owner_id=actor_id, project_id=project_id)
    missing_id = uuid4()
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with (
        patch(f"{MODULE}.authorized_or_owner_scoped", new_callable=AsyncMock, return_value=project),
        patch(f"{MODULE}.ensure_project_permission", new_callable=AsyncMock),
        pytest.raises(ProjectArtifactNotFoundError, match="selected flows were not found"),
    ):
        await build_project_artifact(
            _session_with_flows([selected]),
            user,
            project_id,
            flow_ids=[selected.id, missing_id],
        )

    with pytest.raises(ProjectArtifactError, match="duplicate flow IDs"):
        await build_project_artifact(
            AsyncMock(),
            user,
            project_id,
            flow_ids=[selected.id, selected.id],
        )


@pytest.mark.asyncio
async def test_build_project_artifact_includes_cross_author_flows_with_safe_permission_batches() -> None:
    actor_id = uuid4()
    owner_id = uuid4()
    collaborator_id = uuid4()
    project_id = uuid4()
    workspace_id = uuid4()
    project = Folder(
        id=project_id,
        name="Shared Project",
        user_id=owner_id,
        workspace_id=workspace_id,
    )
    actor_flow = _flow(
        flow_id=UUID("00000000-0000-0000-0000-000000000001"),
        owner_id=actor_id,
        project_id=project_id,
        name="Actor flow",
    )
    owner_flow = _flow(
        flow_id=UUID("00000000-0000-0000-0000-000000000002"),
        owner_id=owner_id,
        project_id=project_id,
        name="Project owner flow",
    )
    collaborator_flow = _flow(
        flow_id=UUID("00000000-0000-0000-0000-000000000003"),
        owner_id=collaborator_id,
        project_id=project_id,
        name="Collaborator flow",
    )
    session = _session_with_flows([actor_flow, owner_flow, collaborator_flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    artifact, load_project, ensure_project, ensure_flows = await _build_authorized(
        session=session,
        user=user,
        project=project,
    )

    assert [flow.flow_id for flow in artifact.flows] == [actor_flow.id, owner_flow.id, collaborator_flow.id]
    assert load_project.await_args.kwargs["owner_id"] == actor_id
    ensure_project.assert_awaited_once()
    assert ensure_project.await_args.args[1].value == "read"
    assert ensure_project.await_args.kwargs == {
        "project_id": project_id,
        "project_user_id": owner_id,
        "workspace_id": workspace_id,
    }
    assert ensure_flows.await_count == 2
    actor_batch, non_owned_batch = ensure_flows.await_args_list
    assert actor_batch.args[1].value == "read"
    assert actor_batch.kwargs == {
        "flow_ids": [actor_flow.id],
        "flow_user_id": actor_id,
        "workspace_id": workspace_id,
        "folder_id": project_id,
    }
    assert non_owned_batch.args[1].value == "read"
    assert non_owned_batch.kwargs == {
        "flow_ids": [owner_flow.id, collaborator_flow.id],
        "flow_user_id": None,
        "workspace_id": workspace_id,
        "folder_id": project_id,
    }

    assert session.exec.await_count == 3
    for flow_query_call in session.exec.await_args_list:
        compiled = str(flow_query_call.args[0].compile(compile_kwargs={"literal_binds": True}))
        assert project_id.hex in compiled
        assert owner_id.hex not in compiled
        assert collaborator_id.hex not in compiled
        assert actor_id.hex not in compiled


@pytest.mark.asyncio
async def test_build_project_artifact_requires_project_read_before_loading_flows() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Denied", user_id=actor_id)
    session = _session_with_flows([])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with (
        patch(f"{MODULE}.authorized_or_owner_scoped", new_callable=AsyncMock, return_value=project),
        patch(
            f"{MODULE}.ensure_project_permission",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=403, detail="denied"),
        ),
        patch(f"{MODULE}.ensure_flows_permission", new_callable=AsyncMock) as ensure_flows,
        pytest.raises(HTTPException, match="denied"),
    ):
        await build_project_artifact(session, user, project_id)

    session.exec.assert_not_awaited()
    ensure_flows.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_project_artifact_fails_whole_package_when_any_flow_is_unreadable() -> None:
    actor_id = uuid4()
    owner_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="No partial exports", user_id=owner_id)
    flows = [
        _flow(owner_id=owner_id, project_id=project_id, name="Allowed"),
        _flow(owner_id=owner_id, project_id=project_id, name="Denied"),
    ]
    session = _session_with_flows(flows)
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with (
        patch(f"{MODULE}.authorized_or_owner_scoped", new_callable=AsyncMock, return_value=project),
        patch(f"{MODULE}.ensure_project_permission", new_callable=AsyncMock),
        patch(
            f"{MODULE}.ensure_flows_permission",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=403, detail="denied"),
        ),
        patch(f"{MODULE}._build_archive") as build_archive,
        pytest.raises(HTTPException, match="denied"),
    ):
        await build_project_artifact(session, user, project_id)

    build_archive.assert_not_called()


@pytest.mark.asyncio
async def test_cancelled_package_waits_for_archive_worker_before_releasing_capacity() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Cancellation", user_id=actor_id)
    session = _session_with_flows([_flow(owner_id=actor_id, project_id=project_id)])
    user = SimpleNamespace(id=actor_id, is_superuser=False)
    worker_started = threading.Event()
    release_worker = threading.Event()

    def blocking_archive(**_kwargs):
        worker_started.set()
        release_worker.wait(timeout=5)
        return MagicMock()

    with (
        patch(f"{MODULE}.authorized_or_owner_scoped", new_callable=AsyncMock, return_value=project),
        patch(f"{MODULE}.ensure_project_permission", new_callable=AsyncMock),
        patch(f"{MODULE}.ensure_flows_permission", new_callable=AsyncMock),
        patch(f"{MODULE}._build_archive", side_effect=blocking_archive),
    ):
        task = asyncio.create_task(build_project_artifact(session, user, project_id))
        assert await asyncio.to_thread(worker_started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        try:
            assert not task.done()
        finally:
            release_worker.set()

        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_build_project_artifact_scrubs_secret_fields_without_resolving_references() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Secrets", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    flow.data = {
        "nodes": [
            {
                "data": {
                    "node": {
                        "template": {
                            "password": {"name": "password", "password": True, "value": "raw-password"},
                            "client_secret": {"name": "client_secret", "value": "raw-client-secret"},
                            "headers": {
                                "name": "headers",
                                "value": {"Authorization": "Bearer raw-token", "safe": "kept"},
                            },
                            "variable": {"name": "model", "value": "${MODEL_NAME}"},
                        }
                    }
                }
            }
        ],
        "edges": [],
    }
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    artifact, *_ = await _build_authorized(session=session, user=user, project=project)

    assert b"raw-password" not in artifact.content
    assert b"raw-client-secret" not in artifact.content
    assert b"raw-token" not in artifact.content
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        exported = json.loads(archive.read(f"flows/{flow.id}.json"))
    template = exported["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["password"]["value"] is None
    assert template["client_secret"]["value"] is None
    assert template["headers"]["value"] == {"Authorization": None, "safe": "kept"}
    assert template["variable"]["value"] == "${MODEL_NAME}"


@pytest.mark.asyncio
async def test_build_project_artifact_preserves_variable_references_and_lists_required_variables() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Variable references", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    flow.data = {
        "nodes": [
            {
                "data": {
                    "node": {
                        "template": {
                            "api_key": {
                                "name": "api_key",
                                "password": True,
                                "load_from_db": True,
                                "value": "OPENAI_API_KEY",
                            },
                            "password": {"name": "password", "password": True, "value": "raw-password"},
                            "endpoint": {"name": "endpoint", "load_from_db": True, "value": "MY_INTERNAL_API_URL"},
                            "mislabeled": {
                                "name": "token",
                                "password": True,
                                "load_from_db": True,
                                "value": "raw-mislabeled-secret\nwith-newline",
                            },
                        }
                    }
                }
            }
        ],
        "edges": [],
    }
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    artifact, *_ = await _build_authorized(session=session, user=user, project=project)

    assert b"raw-password" not in artifact.content
    assert b"raw-mislabeled-secret" not in artifact.content
    assert artifact.flows[0].required_variables == ("MY_INTERNAL_API_URL", "OPENAI_API_KEY")
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        exported = json.loads(archive.read(f"flows/{flow.id}.json"))
        manifest = json.loads(archive.read("manifest.json"))
    template = exported["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] == "OPENAI_API_KEY"
    assert template["api_key"]["load_from_db"] is True
    assert template["password"]["value"] is None
    assert template["endpoint"]["value"] == "MY_INTERNAL_API_URL"
    assert template["mislabeled"]["value"] is None
    assert manifest["required_variables"] == ["MY_INTERNAL_API_URL", "OPENAI_API_KEY"]
    assert manifest["flows"][0]["required_variables"] == ["MY_INTERNAL_API_URL", "OPENAI_API_KEY"]


@pytest.mark.asyncio
async def test_build_project_artifact_keeps_newline_heavy_code_as_bounded_string() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Runtime code", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    code = "\n" * 100_000
    flow.data = {
        "nodes": [
            {
                "data": {
                    "node": {
                        "template": {
                            "code": {"name": "code", "type": "code", "value": code},
                        }
                    }
                }
            }
        ],
        "edges": [],
    }
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    artifact, *_ = await _build_authorized(session=session, user=user, project=project)

    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        exported = json.loads(archive.read(f"flows/{flow.id}.json"))
    assert exported["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == code


@pytest.mark.asyncio
async def test_build_project_artifact_rejects_lone_unicode_surrogate_in_flow_name() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Valid project", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id, name="Invalid flow \ud800")
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactError, match="Unicode surrogate"):
        await _build_authorized(session=session, user=user, project=project)


@pytest.mark.asyncio
async def test_build_project_artifact_rejects_lone_unicode_surrogate_in_project_name() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Invalid project \ud800", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactError, match="Unicode surrogate"):
        await _build_authorized(session=session, user=user, project=project)


@pytest.mark.asyncio
async def test_build_project_artifact_rejects_lone_unicode_surrogate_in_persisted_string_value() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Valid project", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    flow.data = {"nodes": [], "edges": [], "persisted": "Invalid value \ud800"}
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactError, match="Unicode surrogate"):
        await _build_authorized(session=session, user=user, project=project)


@pytest.mark.asyncio
async def test_build_project_artifact_rejects_lone_unicode_surrogate_in_persisted_object_key() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Valid project", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    flow.data = {"nodes": [], "edges": [], "persisted": {"Invalid key \ud800": "value"}}
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactError, match="Unicode surrogate"):
        await _build_authorized(session=session, user=user, project=project)


def test_secret_scrub_uses_bounded_memory_for_wide_deep_structured_value() -> None:
    from langflow.services.deployment_artifacts import builder

    structured: object = [None] * 100_000
    for _ in range(50):
        structured = {"nested": structured}
    snapshot = builder._FlowSnapshot(
        flow_id=uuid4(),
        name="Bounded scrub",
        payload={
            "data": {
                "nodes": [
                    {
                        "data": {
                            "node": {
                                "template": {
                                    "settings": {"name": "settings", "value": structured},
                                }
                            }
                        }
                    }
                ],
                "edges": [],
            }
        },
    )

    tracemalloc.start()
    try:
        content, _ = builder._normalized_flow_bytes(snapshot)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert len(content) < 1024 * 1024
    assert peak < 16 * 1024 * 1024


@pytest.mark.parametrize(
    ("data", "expected_data"),
    [
        (None, None),
        (
            {"nodes": [None], "edges": []},
            {"nodes": [None], "edges": []},
        ),
        (
            {
                "nodes": [
                    {
                        "data": {
                            "node": {
                                "template": {
                                    "malformed": {"name": None, "password": True, "value": "retained"},
                                }
                            }
                        }
                    }
                ],
                "edges": [],
            },
            {
                "nodes": [
                    {
                        "data": {
                            "node": {
                                "template": {
                                    "malformed": {"name": None, "password": True, "value": None},
                                }
                            }
                        }
                    }
                ],
                "edges": [],
            },
        ),
    ],
)
def test_normalized_flow_bytes_accepts_model_valid_sparse_data(data: object, expected_data: object) -> None:
    from langflow.services.deployment_artifacts import builder

    snapshot = builder._FlowSnapshot(
        flow_id=uuid4(),
        name="Empty flow",
        payload={"data": data},
    )
    original_payload = deepcopy(snapshot.payload)

    content, required_variables = builder._normalized_flow_bytes(snapshot)
    assert json.loads(content) == {"data": expected_data}
    assert required_variables == ()
    assert snapshot.payload == original_payload


def test_normalized_flow_bytes_does_not_mutate_shared_flow_data() -> None:
    from langflow.services.deployment_artifacts import builder

    flow = _flow(owner_id=uuid4(), project_id=uuid4())
    flow.data = {
        "nodes": [
            {
                "selected": True,
                "data": {
                    "node": {
                        "template": {
                            "password": {"name": "password", "password": True, "value": "raw-password"},
                        }
                    }
                },
            }
        ],
        "edges": [],
    }
    original_data = deepcopy(flow.data)
    snapshot = builder._FlowSnapshot(
        flow_id=flow.id,
        name="Shared flow data",
        payload={"data": flow.data},
    )

    content, _ = builder._normalized_flow_bytes(snapshot)
    exported = json.loads(content)

    assert exported["data"]["nodes"][0]["data"]["node"]["template"]["password"]["value"] is None
    assert "selected" not in exported["data"]["nodes"][0]
    assert flow.data == original_data
    assert snapshot.payload["data"] is flow.data


@pytest.mark.asyncio
async def test_build_project_artifact_never_uses_mutable_names_as_archive_paths() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name='../../Project\n"name"', user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id, name="../flow\\name")
    flow.fs_path = "../../server-only/path"
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    artifact, *_ = await _build_authorized(session=session, user=user, project=project)

    assert artifact.filename == f"langflow-project-{project_id}.lfpkg"
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        assert archive.namelist() == ["manifest.json", f"flows/{flow.id}.json"]
        assert all(".." not in name and "\\" not in name for name in archive.namelist())
        exported = json.loads(archive.read(f"flows/{flow.id}.json"))
        assert "fs_path" not in exported


@pytest.mark.asyncio
async def test_build_project_artifact_rejects_empty_projects() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Empty", user_id=actor_id)
    session = _session_with_flows([])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(EmptyProjectArtifactError, match="no flows"):
        await _build_authorized(session=session, user=user, project=project)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flows", "limits", "message"),
    [
        (2, ProjectArtifactLimits(max_flow_count=1), "flow count"),
        (1, ProjectArtifactLimits(max_flow_bytes=32), "flow file"),
        (
            1,
            ProjectArtifactLimits(max_flow_bytes=1024 * 1024, max_expanded_bytes=32),
            "expanded size",
        ),
    ],
)
async def test_build_project_artifact_enforces_resource_limits(
    flows: int,
    limits: ProjectArtifactLimits,
    message: str,
) -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Limits", user_id=actor_id)
    rows = [_flow(owner_id=actor_id, project_id=project_id, name=f"Flow {index}") for index in range(flows)]
    session = _session_with_flows(rows)
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactLimitError, match=message):
        await _build_authorized(session=session, user=user, project=project, limits=limits)


@pytest.mark.asyncio
async def test_build_project_artifact_pages_flow_rows_and_authorizes_each_page() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Paged", user_id=actor_id)
    rows = [_flow(owner_id=actor_id, project_id=project_id, name=f"Flow {index}") for index in range(5)]
    session = _session_with_flows(rows)
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    artifact, _, _, ensure_flows = await _build_authorized(session=session, user=user, project=project)

    assert artifact.flow_count == 5
    assert session.exec.await_count == 4
    ensure_flows.assert_awaited_once()
    assert len(ensure_flows.await_args.kwargs["flow_ids"]) == 5


@pytest.mark.asyncio
async def test_build_project_artifact_fails_if_selected_flow_changes_before_page_load() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Changing", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    id_result = MagicMock()
    id_result.all.return_value = [(flow.id, flow.user_id, flow.updated_at)]
    missing_page = MagicMock()
    missing_page.all.return_value = []
    session = AsyncMock()
    session.exec.side_effect = [id_result, missing_page]
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactError, match="changed during packaging"):
        await _build_authorized(session=session, user=user, project=project)


@pytest.mark.asyncio
async def test_build_project_artifact_fails_if_flow_owner_changes_before_page_snapshot() -> None:
    actor_id = uuid4()
    new_owner_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Changing owner", user_id=actor_id)
    flow = _flow(owner_id=new_owner_id, project_id=project_id)

    initial_revisions = MagicMock()
    initial_revisions.all.return_value = [(flow.id, actor_id, flow.updated_at)]
    page = MagicMock()
    page.all.return_value = [flow]
    session = AsyncMock()
    session.exec.side_effect = [initial_revisions, page]
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactError, match="changed during packaging"):
        await _build_authorized(session=session, user=user, project=project)


@pytest.mark.asyncio
async def test_build_project_artifact_fails_if_loaded_flow_changes_before_final_revision_check() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Changing revision", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    initial_updated_at = flow.updated_at
    assert initial_updated_at is not None

    initial_revisions = MagicMock()
    initial_revisions.all.return_value = [(flow.id, flow.user_id, initial_updated_at)]
    page = MagicMock()
    page.all.return_value = [flow]
    final_revisions = MagicMock()
    final_revisions.all.return_value = [(flow.id, flow.user_id, initial_updated_at + timedelta(microseconds=1))]
    session = AsyncMock()
    session.exec.side_effect = [initial_revisions, page, final_revisions]
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactError, match="changed during packaging"):
        await _build_authorized(session=session, user=user, project=project)


@pytest.mark.asyncio
async def test_build_project_artifact_fails_if_flow_owner_changes_before_final_revision_check() -> None:
    actor_id = uuid4()
    new_owner_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Changing owner", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)

    initial_revisions = MagicMock()
    initial_revisions.all.return_value = [(flow.id, actor_id, flow.updated_at)]
    page = MagicMock()
    page.all.return_value = [flow]
    final_revisions = MagicMock()
    final_revisions.all.return_value = [(flow.id, new_owner_id, flow.updated_at)]
    session = AsyncMock()
    session.exec.side_effect = [initial_revisions, page, final_revisions]
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactError, match="changed during packaging"):
        await _build_authorized(session=session, user=user, project=project)


@pytest.mark.asyncio
async def test_build_project_artifact_detaches_and_preflights_outside_event_loop() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Worker", user_id=actor_id)
    session = _session_with_flows([_flow(owner_id=actor_id, project_id=project_id)])
    user = SimpleNamespace(id=actor_id, is_superuser=False)
    event_loop_thread = threading.get_ident()
    worker_threads: list[int] = []

    from langflow.services.deployment_artifacts import builder

    original_snapshot_rows = builder._snapshot_rows

    def observed_snapshot_rows(*args, **kwargs):
        worker_threads.append(threading.get_ident())
        return original_snapshot_rows(*args, **kwargs)

    with patch(f"{MODULE}._snapshot_rows", side_effect=observed_snapshot_rows):
        await _build_authorized(session=session, user=user, project=project)

    assert worker_threads
    assert all(thread_id != event_loop_thread for thread_id in worker_threads)


@pytest.mark.asyncio
async def test_build_project_artifact_rejects_deep_data_before_recursive_scrubbing() -> None:
    actor_id = uuid4()
    project_id = uuid4()
    project = Folder(id=project_id, name="Deep", user_id=actor_id)
    flow = _flow(owner_id=actor_id, project_id=project_id)
    nested: dict[str, object] = {}
    for _ in range(130):
        nested = {"nested": nested}
    flow.data = nested
    session = _session_with_flows([flow])
    user = SimpleNamespace(id=actor_id, is_superuser=False)

    with pytest.raises(ProjectArtifactLimitError, match="nesting limit"):
        await _build_authorized(session=session, user=user, project=project)
