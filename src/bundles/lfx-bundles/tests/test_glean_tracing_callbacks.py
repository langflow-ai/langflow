"""Glean's standalone output retains workflow callbacks on its LangChain tool."""

from types import SimpleNamespace

from langchain_core.callbacks import BaseCallbackHandler
from lfx_bundles.glean.glean_search_api import GleanSearchAPIComponent


def test_glean_search_keeps_workflow_callback(monkeypatch):
    class _RecordingCallback(BaseCallbackHandler):
        def __init__(self):
            self.tool_runs = []

        def on_tool_start(self, _serialized, _input, *, run_id, **_kwargs):
            self.tool_runs.append(run_id)

    callback = _RecordingCallback()
    monkeypatch.setattr(GleanSearchAPIComponent, "get_langchain_callbacks", lambda _self: [callback])
    monkeypatch.setattr(
        GleanSearchAPIComponent,
        "_build_wrapper",
        lambda *_args, **_kwargs: SimpleNamespace(
            run=lambda **_kwargs: [{"snippets": [{"text": "fixture result"}]}],
        ),
    )
    component = GleanSearchAPIComponent()
    component.query = "fixture query"

    result = component.fetch_content()

    assert result[0].text == "fixture result"
    assert len(callback.tool_runs) == 1
