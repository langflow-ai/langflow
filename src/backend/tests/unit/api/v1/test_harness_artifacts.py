"""Candidate creation uses exact reviewed versions and deploy authorization."""

from uuid import UUID

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.deployment_artifacts.harness import build_harness_artifact
from langflow.services.deps import session_scope
from lfx.projects.runtime_artifacts import read_candidate

from tests.unit.api.v1.test_harness_skill_packs import skill_harness  # noqa: F401
from tests.unit.api.v1.test_project_config_write_through import stored_flow
from tests.unit.api.v2.test_workflow_skills import workflow_harness  # noqa: F401


async def test_candidate_download_contains_only_entrypoint_and_reviewed_tool(
    client,
    logged_in_headers,
    workflow_harness,  # noqa: F811
):
    project, root, *_ = workflow_harness
    response = await client.get(f"/api/v1/projects/{project}/harness-artifact", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    candidate = read_candidate(response.content)
    assert candidate.manifest["entrypoints"] == [root]
    assert len(candidate.definitions) == 2
    assert response.headers["etag"] == f'"{candidate.digest}"'
    second = await client.get(f"/api/v1/projects/{project}/harness-artifact", headers=logged_in_headers)
    assert second.content == response.content


async def test_candidate_keeps_reviewed_tool_after_source_draft_edit(workflow_harness, active_user):  # noqa: F811
    project, root, *_ = workflow_harness
    before = await stored_flow(root)
    tool = next(n["data"]["_harness_tool"]["tool_pack"] for n in before.data["nodes"] if n["data"].get("_harness_tool"))
    async with session_scope() as session:
        row = await session.get(Flow, UUID(tool["tool"]["flow_id"]))
        row.data = {"nodes": [], "edges": []}
        session.add(row)
        await session.commit()
    async with session_scope() as session:
        candidate = await build_harness_artifact(session, active_user, UUID(project))
    assert candidate.definitions[tool["tool"]["flow_id"]]["data"]["nodes"]


async def test_candidate_requires_deploy_on_dependencies(workflow_harness, active_user, monkeypatch):  # noqa: F811
    from fastapi import HTTPException

    project, root, *_ = workflow_harness

    async def deny(_user, action, **scope):
        if action.value == "deploy" and str(scope["flow_id"]) != root:
            raise HTTPException(403)

    monkeypatch.setattr("langflow.services.database.models.folder.flow_bindings.ensure_flow_permission", deny)
    async with session_scope() as session:
        with pytest.raises(HTTPException):
            await build_harness_artifact(session, active_user, UUID(project))


async def test_candidate_rechecks_root_after_dependency_resolution(workflow_harness, active_user, monkeypatch):  # noqa: F811
    from copy import deepcopy

    from langflow.services.deployment_artifacts import ProjectArtifactError, harness

    original = harness.resolve_tool_pack_snapshot
    project, root, *_ = workflow_harness

    async def edit_after_read(session, *args, **kwargs):
        result = await original(session, *args, **kwargs)
        row = await session.get(Flow, UUID(root))
        changed = deepcopy(row.data)
        changed["nodes"][0]["data"]["changed_during_packaging"] = True
        row.data = changed
        session.add(row)
        await session.flush()
        return result

    monkeypatch.setattr(harness, "resolve_tool_pack_snapshot", edit_after_read)
    async with session_scope() as session:
        with pytest.raises(ProjectArtifactError, match="changed during packaging"):
            await build_harness_artifact(session, active_user, UUID(project))


async def test_candidate_scrubs_secrets_and_records_original_revision(workflow_harness, active_user):  # noqa: F811
    from copy import deepcopy

    from lfx.projects.bindings import flow_revision

    project, root, *_ = workflow_harness
    async with session_scope() as session:
        row = await session.get(Flow, UUID(root))
        data = deepcopy(row.data)
        data["nodes"][0]["data"]["node"]["template"]["credential"] = {
            "type": "str",
            "password": True,
            "value": "literal-private-value",
        }
        row.data = data
        session.add(row)
        await session.commit()
    async with session_scope() as session:
        candidate = await build_harness_artifact(session, active_user, UUID(project))
    assert b"literal-private-value" not in candidate.archive()
    source = next(item for item in candidate.manifest["flows"] if item["id"] == root)
    assert source["source_revision"] == flow_revision(data)
    assert flow_revision(candidate.definitions[root]["data"]) != source["source_revision"]
    assert (await stored_flow(root)).data == data


async def test_editor_candidate_executes_in_clean_lfx_process(workflow_harness, active_user, tmp_path):  # noqa: F811
    """Optional two-environment acceptance lane; external model is the only substitute."""
    import asyncio
    import os
    from pathlib import Path

    executable = os.environ.get("LFX_CANDIDATE_TEST_PYTHON")
    if not executable:
        pytest.skip("Set LFX_CANDIDATE_TEST_PYTHON to a standalone LFX test environment's Python")
    project, *_ = workflow_harness
    async with session_scope() as session:
        candidate = await build_harness_artifact(session, active_user, UUID(project))
    path = tmp_path / "research.lfpkg"
    path.write_bytes(candidate.archive())
    repo = Path(__file__).resolve().parents[6]
    process = await asyncio.create_subprocess_exec(
        executable,
        "-m",
        "pytest",
        "src/lfx/tests/unit/cli/test_harness_artifacts.py::test_exported_editor_candidate",
        "-q",
        "--disable-warnings",
        cwd=repo,
        env={**os.environ, "LFX_TEST_CANDIDATE": str(path)},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=120)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    assert process.returncode == 0, output.decode()
