"""Policy generation keeps workflow tracing through the ToolGuard model adapter."""

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.tools import tool
from lfx_toolguard.components.models_and_agents import policies_component
from lfx_toolguard.components.models_and_agents.policies_component import PoliciesComponent


@pytest.mark.parametrize("stage", ["specs", "code"])
async def test_policy_generation_keeps_workflow_callback(monkeypatch, tmp_path, stage):
    class _RecordingCallback(BaseCallbackHandler):
        def __init__(self):
            self.model_runs = []

        def on_chat_model_start(self, _serialized, _messages, *, run_id, **_kwargs):
            self.model_runs.append(run_id)

    @tool
    def read_record(record_id: str) -> str:
        """Read a fixture record."""
        return record_id

    async def _generate(*, llm, **_kwargs):
        return await llm.generate([{"role": "user", "content": "Generate a read-only policy."}])

    # The ToolGuard generation boundary is local; component, adapter, and LangChain run for real.
    monkeypatch.setattr("toolguard.buildtime.generate_guard_specs", _generate)
    monkeypatch.setattr("toolguard.buildtime.generate_guards_code", _generate)
    monkeypatch.setattr(policies_component, "TOOLGUARD_WORK_DIR", tmp_path)
    callback = _RecordingCallback()
    monkeypatch.setattr(PoliciesComponent, "get_langchain_callbacks", lambda _self: [callback])
    component = PoliciesComponent()
    component.project = "tracing"
    component.policies = ["Allow record reads."]
    component.in_tools = [read_record]
    component.model = FakeListChatModel(responses=["Generated policy"])

    if stage == "specs":
        result = await component._generate_guard_specs()
    else:
        result = await component._generate_guard_code([])

    assert result == "Generated policy"
    assert len(callback.model_runs) == 1
