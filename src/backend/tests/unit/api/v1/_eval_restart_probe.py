"""Continue an evaluation from a fresh application process using only persisted state."""

import asyncio
import json
import os
from unittest.mock import patch

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langflow.main import create_app

from tests.unit.api.v1.test_eval_durability import wait_run
from tests.unit.api.v2.test_workflow_skills import WorkflowSkillModel


async def main():
    pending = json.loads(os.environ["EVAL_TEST_PENDING"])
    suite, run = os.environ["EVAL_TEST_SUITE"], os.environ["EVAL_TEST_RUN"]
    model = WorkflowSkillModel(skill_key=os.environ["EVAL_TEST_SKILL"], probe_scope=False)
    with (
        patch("lfx.base.models.unified_models.get_llm", lambda **_kw: model),
        patch("lfx.components.models_and_agents.agent.get_llm", lambda **_kw: model),
    ):
        async with (
            LifespanManager(create_app(), startup_timeout=60, shutdown_timeout=30) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://restart/") as client,
        ):
            headers = {"x-api-key": os.environ["EVAL_TEST_API_KEY"]}
            paused = await wait_run(client, headers, suite, run, {"suspended"}, completed_cases=1)
            assert paused["pending_approval"] == pending
            response = await client.post(
                f"/api/v2/workflows/{pending['job_id']}/resume",
                headers=headers,
                json={"request_id": pending["request"]["request_id"], "decision": {"action_id": "approve"}},
            )
            assert response.status_code == 200, response.text
            finished = await wait_run(client, headers, suite, run, {"completed"})
            assert finished["passed"], finished
            assert finished["result"]["cases"][0] == paused["result"]["cases"][0]
            assert finished["result"]["cases"][1]["workflow_job_id"] == pending["job_id"]
            assert "NEW RUBRIC" not in json.dumps(finished["result"]["suite"])
    print("EVALUATION_PROCESS_RESTART_OK")  # noqa: T201 -- process success sentinel


if __name__ == "__main__":
    asyncio.run(main())
