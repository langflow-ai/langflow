"""Run the real worker CLI, replacing only the external model provider."""

import asyncio
import os
from pathlib import Path
from unittest.mock import patch

from tests.unit.api.v2.test_workflow_skills import WorkflowSkillModel


class ProcessModel(WorkflowSkillModel):
    def record_turn(self):
        with Path(os.environ["EVAL_WORKER_TURNS_FILE"]).open("a") as turns:
            turns.write("provider turn\n")

    async def _agenerate(self, *args, **kwargs):
        await asyncio.to_thread(self.record_turn)
        if os.environ.get("EVAL_WORKER_BLOCK") == "true":
            await asyncio.Event().wait()
        return await super()._agenerate(*args, **kwargs)


if __name__ == "__main__":
    from langflow.__main__ import app

    model = ProcessModel(skill_key=os.environ["EVAL_TEST_SKILL"], probe_scope=False)
    with (
        patch("lfx.base.models.unified_models.get_llm", lambda **_kw: model),
        patch("lfx.components.models_and_agents.agent.get_llm", lambda **_kw: model),
    ):
        app(["worker", "--idle-block-ms", "20"])
