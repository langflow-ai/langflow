"""Components keep workflow tracing callbacks when invoking LangChain directly."""

from langchain_classic.agents import AgentExecutor
from langchain_core.agents import AgentFinish
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda
from lfx.components.langchain_utilities.runnable_executor import RunnableExecComponent
from lfx.components.llm_operations.guardrails import GuardrailsComponent
from lfx.components.llm_operations.guardrails_v2 import GuardrailsV2Component
from lfx.components.llm_operations.lambda_filter import LambdaFilterComponent
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
from lfx.components.llm_operations.llm_selector import LLMSelectorComponent
from lfx.schema.message import Message


class _RecordingCallback(BaseCallbackHandler):
    def __init__(self):
        self.chain_runs = []
        self.model_runs = []

    def on_chain_start(self, _serialized, _inputs, *, run_id, **_kwargs):
        self.chain_runs.append(run_id)

    def on_chat_model_start(self, _serialized, _messages, *, run_id, **_kwargs):
        self.model_runs.append(run_id)


async def test_runnable_executor_keeps_workflow_callback(monkeypatch):
    callback = _RecordingCallback()
    monkeypatch.setattr(RunnableExecComponent, "get_langchain_callbacks", lambda _self: [callback])
    component = RunnableExecComponent()
    component.runnable = AgentExecutor(
        agent=RunnableLambda(lambda _: AgentFinish(return_values={"output": "done"}, log="done")),
        tools=[],
    )
    component.input_value = "input"
    component.input_key = "input"
    component.output_key = "output"
    component.use_stream = False

    assert await component.build_executor() == "done"
    assert callback.chain_runs


async def test_runnable_executor_stream_keeps_workflow_callback(monkeypatch):
    callback = _RecordingCallback()
    monkeypatch.setattr(RunnableExecComponent, "get_langchain_callbacks", lambda _self: [callback])
    component = RunnableExecComponent()
    component.runnable = AgentExecutor(
        agent=RunnableLambda(lambda _: AgentFinish(return_values={"output": "done"}, log="done")),
        tools=[],
    )

    assert [chunk async for chunk in component.astream_events({})] == []
    assert callback.chain_runs


async def test_llm_selector_keeps_judge_and_selected_model_callbacks(monkeypatch):
    callback = _RecordingCallback()
    monkeypatch.setattr(LLMSelectorComponent, "get_langchain_callbacks", lambda _self: [callback])
    monkeypatch.setattr(LLMSelectorComponent, "log", lambda *_args: None)
    component = LLMSelectorComponent()
    component.models = [FakeListChatModel(responses=["selected response"])]
    component.judge_llm = FakeListChatModel(responses=["0"])
    component.input_value = "input"
    component.use_openrouter_specs = False

    assert (await component.route_to_model()).text == "selected response"
    assert len(callback.model_runs) == 2


async def test_llm_selector_keeps_fallback_model_callback(monkeypatch):
    callback = _RecordingCallback()
    monkeypatch.setattr(LLMSelectorComponent, "get_langchain_callbacks", lambda _self: [callback])
    monkeypatch.setattr(LLMSelectorComponent, "log", lambda *_args: None)

    class _FailingJudge(FakeListChatModel):
        async def ainvoke(self, *_args, **_kwargs):
            message = "Judge unavailable"
            raise RuntimeError(message)

    component = LLMSelectorComponent()
    component.models = [FakeListChatModel(responses=["fallback response"])]
    component.judge_llm = _FailingJudge(responses=["0"])
    component.input_value = "input"
    component.use_openrouter_specs = False
    component.fallback_to_first = True

    assert (await component.route_to_model()).text == "fallback response"
    assert len(callback.model_runs) == 1


def test_guardrail_keeps_workflow_callback(monkeypatch):
    callback = _RecordingCallback()
    monkeypatch.setattr(GuardrailsComponent, "get_langchain_callbacks", lambda _self: [callback])
    component = GuardrailsComponent()
    model = FakeListChatModel(responses=["NO\nNo sensitive information."])

    passed, _ = component._check_guardrail(model, "Hello", "PII", "personal information")

    assert passed is True
    assert len(callback.model_runs) == 1


def test_guardrail_second_opinion_keeps_workflow_callback(monkeypatch):
    callback = _RecordingCallback()
    monkeypatch.setattr(GuardrailsV2Component, "get_langchain_callbacks", lambda _self: [callback])
    component = GuardrailsV2Component()
    component.model = FakeListChatModel(
        responses=['{"PII": {"detected": false, "confidence": 0.0, "reason": "No sensitive information."}}']
    )
    component.input_text = "Hello"
    component.enabled_guardrails = ["PII"]
    component.checking_method = "Rules + AI"
    component.llm_mode = "always"
    component._pre_run_setup()

    scores, error = component._run_llm({})

    assert error is None
    assert scores["PII"]["score"] == 0.0
    assert len(callback.model_runs) == 1


def test_smart_router_keeps_workflow_callback(monkeypatch):
    callback = _RecordingCallback()
    monkeypatch.setattr(SmartRouterComponent, "get_langchain_callbacks", lambda _self: [callback])
    component = SmartRouterComponent()
    component.model = FakeListChatModel(responses=["Greeting"])
    component.input_text = "Hello"
    component.routes = [{"route_category": "Greeting", "route_description": "A greeting"}]

    assert component._get_categorization() == "Greeting"
    assert len(callback.model_runs) == 1


async def test_lambda_filter_keeps_workflow_callback(monkeypatch):
    callback = _RecordingCallback()
    monkeypatch.setattr(LambdaFilterComponent, "get_langchain_callbacks", lambda _self: [callback])
    component = LambdaFilterComponent()
    component.model = FakeListChatModel(responses=["lambda x: x.upper()"])
    component.data = Message(text="hello")
    component.filter_instruction = "Convert text to uppercase."

    assert await component._execute_lambda() == "HELLO"
    assert len(callback.model_runs) == 1
