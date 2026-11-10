"""The router keeps workflow callbacks on its selected model invocation."""

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from lfx_bundles.notdiamond.notdiamond import NotDiamondComponent


def test_selected_model_keeps_workflow_callback(monkeypatch):
    class _RecordingCallback(BaseCallbackHandler):
        def __init__(self):
            self.model_runs = []

        def on_chat_model_start(self, _serialized, _messages, *, run_id, **_kwargs):
            self.model_runs.append(run_id)

    callback = _RecordingCallback()
    monkeypatch.setattr(NotDiamondComponent, "get_langchain_callbacks", lambda _self: [callback])
    component = NotDiamondComponent()
    model = FakeListChatModel(responses=["selected response"])

    assert component._call_get_chat_result(model, "input", "system") == "selected response"
    assert len(callback.model_runs) == 1
