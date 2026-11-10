"""Formatting a Hub prompt retains workflow callbacks."""

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.prompts import PromptTemplate
from lfx.components.langchain_utilities.langchain_hub import LangChainHubPromptComponent


async def test_prompt_hub_keeps_workflow_callback(monkeypatch):
    class _RecordingCallback(BaseCallbackHandler):
        def __init__(self):
            self.prompt_runs = []

        def on_chain_start(self, _serialized, _inputs, *, run_id, **_kwargs):
            self.prompt_runs.append(run_id)

    callback = _RecordingCallback()
    monkeypatch.setattr(LangChainHubPromptComponent, "get_langchain_callbacks", lambda _self: [callback])
    monkeypatch.setattr(
        LangChainHubPromptComponent,
        "_fetch_langchain_hub_template",
        lambda _self: PromptTemplate.from_template("Hello"),
    )

    result = await LangChainHubPromptComponent().build_prompt()

    assert result.text == "Hello"
    assert len(callback.prompt_runs) == 1
