"""Fresh-process continuation probe, invoked by test_workflow_candidates."""

import asyncio
import json
import os
from unittest.mock import patch
from uuid import UUID

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import ToolMessage
from langflow.main import create_app
from langflow.services.deps import get_job_service

from tests.unit.api.v2.test_workflow_skills import WorkflowSkillModel, wait_status


async def main():
    job_id = os.environ["CANDIDATE_TEST_JOB"]
    digest = os.environ["CANDIDATE_TEST_DIGEST"]
    request_id = os.environ["CANDIDATE_TEST_REQUEST"]
    model = WorkflowSkillModel(skill_key=os.environ["CANDIDATE_TEST_SKILL"], probe_scope=False)
    app = create_app()
    with (
        patch("lfx.base.models.unified_models.get_llm", lambda **_kw: model),
        patch("lfx.components.models_and_agents.agent.get_llm", lambda **_kw: model),
    ):
        async with (
            LifespanManager(app, startup_timeout=60, shutdown_timeout=30) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://restart/") as client,
        ):
            headers = {"x-api-key": os.environ["CANDIDATE_TEST_API_KEY"]}
            paused = await client.get("/api/v2/workflows", headers=headers, params={"job_id": job_id})
            assert paused.status_code == 200, paused.text
            assert paused.json()["status"] == "suspended"
            assert paused.json()["candidate_digest"] == digest
            resumed = await client.post(
                f"/api/v2/workflows/{job_id}/resume",
                headers=headers,
                json={
                    "request_id": request_id,
                    "decision": {"action_id": "approve"},
                },
            )
            assert resumed.status_code == 200, resumed.text
            result = await wait_status(client, headers, job_id, {"completed"})
            assert result["candidate_digest"] == digest
            assert "Research complete" in json.dumps(result)
            assert "NEW DRAFT" not in str(model.seen[-1])
            assert "Candidate instructions: cite original evidence." in str(model.seen[-1])
            results = [m for m in model.seen[-1] if isinstance(m, ToolMessage) and m.name == model.tool_name]
            assert len(results) == 1
            assert "SOURCE RESULT" in results[0].content
            replay = await client.get(f"/api/v2/workflows/{job_id}/events", headers=headers)
            assert replay.status_code == 200
            assert "Research complete" in replay.text
            duplicate = await client.post(
                f"/api/v2/workflows/{job_id}/resume",
                headers=headers,
                json={
                    "request_id": request_id,
                    "decision": {"action_id": "approve"},
                },
            )
            assert duplicate.status_code == 409
            job = await get_job_service().get_job_by_job_id(UUID(job_id))
            assert job.job_metadata["candidate_digest"] == digest
    print("CANDIDATE_PROCESS_RESTART_OK")  # noqa: T201 -- subprocess success sentinel


if __name__ == "__main__":
    asyncio.run(main())
