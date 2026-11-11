"""Bedrock sampling rejections are cleared one field at a time before retrying."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.encoders import jsonable_encoder
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate
from lfx.base.models.chat_result import get_chat_result
from lfx.base.models.model import LCModelComponent
from lfx.base.models.model_remediation import apply_overrides_to_model, find_remediation
from lfx.schema.message import Message
from pydantic import Field

if TYPE_CHECKING:
    from langchain_core.callbacks import CallbackManagerForLLMRun


def _bedrock_error(field: str) -> str:
    return (
        "An error occurred (ValidationException) when calling the Converse operation: "
        f"The model returned the following errors: `{field}` is deprecated for this model."
    )


@pytest.mark.parametrize("field", ["top_k", "top_p"])
def test_matches_bedrock_sampling_deprecation(field):
    remediation = find_remediation(_bedrock_error(field), provider=None, already_applied=set())

    assert remediation is not None
    assert remediation.overrides == {field: None}
    assert find_remediation(_bedrock_error(field), provider=None, already_applied={remediation.name}) is None


@pytest.mark.parametrize("field", ["top_k", "top_p"])
def test_does_not_match_sampling_range_errors(field):
    assert find_remediation(f"{field} must be greater than zero", provider=None, already_applied=set()) is None


@pytest.mark.parametrize("value", [0, 250])
def test_clears_additional_sampling_field_without_changing_shared_options(value):
    fields = {"top_k": value, "thinking": {"type": "adaptive"}}
    model = SimpleNamespace(additional_model_request_fields=fields)

    assert apply_overrides_to_model(model, {"top_k": None}) is True
    assert model.additional_model_request_fields == {"thinking": {"type": "adaptive"}}
    assert fields == {"top_k": value, "thinking": {"type": "adaptive"}}
    assert not hasattr(model, "top_k")
    assert apply_overrides_to_model(model, {"top_k": None}) is False


@pytest.mark.parametrize("top_p", [None, 0.9])
def test_clears_sampling_field_from_both_request_locations(top_p):
    model = SimpleNamespace(top_p=top_p, additional_model_request_fields={"top_p": 0.8, "other": True})

    assert apply_overrides_to_model(model, {"top_p": None}) is True
    assert model.top_p is None
    assert model.additional_model_request_fields == {"other": True}


@pytest.mark.parametrize("fields", [None, {}, [], {"other": True}])
def test_does_not_create_missing_sampling_fields(fields):
    model = SimpleNamespace(additional_model_request_fields=fields)

    assert apply_overrides_to_model(model, {"top_k": None}) is False
    assert model.additional_model_request_fields == fields
    assert not hasattr(model, "top_k")


def test_does_not_set_unknown_additional_fields_to_non_none_values():
    model = SimpleNamespace(additional_model_request_fields={"top_k": 250})

    assert apply_overrides_to_model(model, {"top_k": 100}) is False
    assert model.additional_model_request_fields == {"top_k": 250}


class SamplingSensitiveChatModel(BaseChatModel):
    """Mirror Bedrock validation while exercising real LangChain runnable wrappers."""

    temperature: float | None = 0.7
    top_p: float | None = 0.9
    additional_model_request_fields: dict[str, Any] = Field(default_factory=lambda: {"top_k": 250})
    seen_sampling: list[tuple[float | None, int | None, float | None]] = Field(default_factory=list)
    repeated_top_k_error: bool = False
    unrelated_error: bool = False

    @property
    def _llm_type(self) -> str:
        return "bedrock-sampling-sensitive-fake"

    def _generate(
        self,
        messages: list[BaseMessage],  # noqa: ARG002
        stop: list[str] | None = None,  # noqa: ARG002
        run_manager: CallbackManagerForLLMRun | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> ChatResult:
        self.seen_sampling.append((self.temperature, self.additional_model_request_fields.get("top_k"), self.top_p))
        if self.unrelated_error:
            msg = "rate limit exceeded"
            raise RuntimeError(msg)
        for field, value in (
            ("temperature", self.temperature),
            ("top_k", self.additional_model_request_fields.get("top_k")),
            ("top_p", self.top_p),
        ):
            if value is not None or (field == "top_k" and self.repeated_top_k_error):
                raise RuntimeError(_bedrock_error(field))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="pong"))])


class SamplingProbe(LCModelComponent):
    display_name = "Sampling Probe"
    description = "test"

    def build_model(self):
        raise NotImplementedError


def _probe() -> SamplingProbe:
    probe = SamplingProbe.__new__(SamplingProbe)
    probe.is_connected_to_chat_output = MagicMock(return_value=False)
    probe.get_project_name = MagicMock(return_value="test-project")
    probe.get_langchain_callbacks = MagicMock(return_value=[])
    probe._id = "sampling-probe"
    return probe


EXPECTED_SAMPLING = [(0.7, 250, 0.9), (None, 250, 0.9), (None, None, 0.9), (None, None, None)]


def _prompt_input() -> Message:
    template = ChatPromptTemplate.from_messages([HumanMessage(content="say pong")])
    return Message(prompt=jsonable_encoder(template.to_json()))


@pytest.mark.asyncio
@pytest.mark.parametrize("use_prompt", [False, True])
async def test_model_response_clears_all_rejected_sampling_fields(use_prompt):
    model = SamplingSensitiveChatModel()

    result = await _probe()._get_chat_result(
        runnable=model, stream=False, input_value=_prompt_input() if use_prompt else "say pong"
    )

    assert result.text == "pong"
    assert model.seen_sampling == EXPECTED_SAMPLING


@pytest.mark.parametrize("stream", [False, True])
def test_connected_model_call_clears_all_rejected_sampling_fields(stream):
    model = SamplingSensitiveChatModel()

    result = get_chat_result(runnable=model, input_value=_prompt_input(), stream=stream)

    assert ("".join(chunk.content for chunk in result) if stream else result) == "pong"
    assert model.seen_sampling == EXPECTED_SAMPLING


def test_repeated_sampling_error_stops_after_one_retry():
    model = SamplingSensitiveChatModel(temperature=None, repeated_top_k_error=True)

    with pytest.raises(RuntimeError, match="top_k"):
        get_chat_result(runnable=model, input_value="say pong")

    assert model.seen_sampling == [(None, 250, 0.9), (None, None, 0.9)]


def test_unrelated_errors_propagate_without_clearing_sampling_fields():
    model = SamplingSensitiveChatModel(unrelated_error=True)

    with pytest.raises(RuntimeError, match="rate limit"):
        get_chat_result(runnable=model, input_value="say pong")

    assert model.seen_sampling == EXPECTED_SAMPLING[:1]


@pytest.mark.asyncio
async def test_connected_agent_clears_all_rejected_sampling_fields():
    from lfx.components.models_and_agents.agent import AgentComponent

    agent = AgentComponent()
    model = SamplingSensitiveChatModel()

    async def run_once():
        result = await model.ainvoke("say pong")
        return Message(text=result.content)

    with patch.object(AgentComponent, "_selected_model_remediation_context", return_value=(None, None, model)):
        result = await agent._run_agent_with_model_remediation(run_once)

    assert result.text == "pong"
    assert model.seen_sampling == EXPECTED_SAMPLING
