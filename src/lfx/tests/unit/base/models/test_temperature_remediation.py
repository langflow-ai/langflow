"""Regression tests for GH-14291 — models that reject an explicit ``temperature``.

Anthropic's Claude 5 family (``claude-sonnet-5``, ``claude-opus-5``) answers any
request carrying ``temperature`` with HTTP 400 ```temperature`` is deprecated for
this model.``, while ``claude-sonnet-4-6`` accepts it. The constraint is not
exposed by the provider's model listing, so it is matched on the ERROR TEXT and
worked around by clearing ``temperature`` and retrying once — the same
error-driven remediation contract as the OpenAI Responses-API constraint.

Impact this pins: the assistant's TranslationFlow hardcodes ``temperature: 0.1``,
so before the fix every intent classification on a Claude 5 model raised, was
swallowed by ``classify_intent``, and silently degraded to the ``question``
intent — "build me a flow" was answered in prose instead of building a flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from fastapi.encoders import jsonable_encoder
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate
from lfx.base.models.model import LCModelComponent
from lfx.base.models.model_remediation import find_remediation, reset_remediation_cache
from lfx.schema.message import Message
from pydantic import Field

if TYPE_CHECKING:
    from collections.abc import Iterator

    from langchain_core.callbacks import CallbackManagerForLLMRun

# Verbatim provider response captured from a live claude-sonnet-5 call.
ANTHROPIC_TEMPERATURE_ERROR = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': '`temperature` is deprecated for this model.'}, "
    "'request_id': 'req_011CdY7B6Rx9fGzrwztE6gYX'}"
)

UNRELATED_ERROR = (
    "Error code: 429 - {'type': 'error', 'error': {'type': 'rate_limit_error', "
    "'message': 'Number of requests has exceeded your rate limit.'}}"
)


class ProviderBadRequestError(Exception):
    """Stands in for ``anthropic.BadRequestError`` — matching is on the message, not the class."""


class TemperatureSensitiveChatModel(BaseChatModel):
    """A real chat model that mirrors Claude 5: rejects any explicitly set temperature.

    This is the one failure mode a real sandbox cannot reproduce deterministically,
    so it is modeled here rather than mocked at the call site.
    """

    temperature: float | None = None
    always_fail: bool = False
    seen_temperatures: list[float | None] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "temperature-sensitive-fake"

    def _generate(
        self,
        messages: list[BaseMessage],  # noqa: ARG002
        stop: list[str] | None = None,  # noqa: ARG002
        run_manager: CallbackManagerForLLMRun | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> ChatResult:
        self.seen_temperatures.append(self.temperature)
        if self.always_fail:
            raise ProviderBadRequestError(ANTHROPIC_TEMPERATURE_ERROR)
        if self.temperature is not None:
            raise ProviderBadRequestError(ANTHROPIC_TEMPERATURE_ERROR)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])


class RateLimitedChatModel(BaseChatModel):
    """Fails with an error no remediation covers, to prove unrelated errors still propagate."""

    temperature: float | None = None
    call_count: int = 0

    @property
    def _llm_type(self) -> str:
        return "rate-limited-fake"

    def _generate(
        self,
        messages: list[BaseMessage],  # noqa: ARG002
        stop: list[str] | None = None,  # noqa: ARG002
        run_manager: CallbackManagerForLLMRun | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> ChatResult:
        self.call_count += 1
        raise ProviderBadRequestError(UNRELATED_ERROR)


class PartialThenFailStreamingModel:
    """Yield once before failing to verify retries never duplicate partial output."""

    temperature: float | None = 0.1
    call_count: int = 0

    def stream(self, _inputs: Any) -> Iterator[AIMessageChunk]:
        self.call_count += 1
        yield AIMessageChunk(content="partial")
        raise ProviderBadRequestError(ANTHROPIC_TEMPERATURE_ERROR)


class _Probe(LCModelComponent):
    """Minimal LCModelComponent usable without going through Component init."""

    display_name = "Probe"
    description = "test"

    def build_model(self):  # pragma: no cover - not exercised; the runnable is injected
        raise NotImplementedError


def _make_probe() -> _Probe:
    probe = _Probe.__new__(_Probe)
    probe.is_connected_to_chat_output = MagicMock(return_value=False)
    probe.get_project_name = MagicMock(return_value="test-project")
    probe.get_langchain_callbacks = MagicMock(return_value=[])
    probe._id = "probe-1"
    probe._event_manager = None
    return probe


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_remediation_cache()
    yield
    reset_remediation_cache()


class TestTemperatureRemediationRegistry:
    def test_should_match_the_temperature_deprecated_error(self):
        remediation = find_remediation(ANTHROPIC_TEMPERATURE_ERROR, provider="Anthropic", already_applied=set())

        assert remediation is not None
        assert remediation.overrides == {"temperature": None}

    def test_should_match_regardless_of_provider(self):
        """The constraint is not Anthropic-specific; match on the error text alone."""
        assert find_remediation(ANTHROPIC_TEMPERATURE_ERROR, provider=None, already_applied=set()) is not None

    def test_should_not_match_unrelated_provider_errors(self):
        assert find_remediation(UNRELATED_ERROR, provider="Anthropic", already_applied=set()) is None

    def test_should_not_match_a_temperature_error_that_is_not_about_deprecation(self):
        """Guard against over-matching: an invalid *value* must still surface to the user."""
        invalid_value = "400 - temperature must be between 0 and 1"

        assert find_remediation(invalid_value, provider="Anthropic", already_applied=set()) is None


class TestApplyOverridesToModel:
    """``apply_overrides_to_model`` is imported per-test so the retry tests above stay collectable."""

    def test_should_set_a_known_attribute_and_report_success(self):
        from lfx.base.models.model_remediation import apply_overrides_to_model

        model = TemperatureSensitiveChatModel(temperature=0.1)

        assert apply_overrides_to_model(model, {"temperature": None}) is True
        assert model.temperature is None

    def test_should_report_failure_when_the_attribute_is_unknown(self):
        """Never attach a junk attribute — an unappliable override must let the error propagate."""
        from lfx.base.models.model_remediation import apply_overrides_to_model

        model = TemperatureSensitiveChatModel(temperature=0.1)

        assert apply_overrides_to_model(model, {"use_responses_api": True}) is False
        assert not hasattr(model, "use_responses_api")

    def test_should_report_failure_for_a_non_model_object(self):
        from lfx.base.models.model_remediation import apply_overrides_to_model

        assert apply_overrides_to_model(object(), {"temperature": None}) is False


class TestGetChatResultRetry:
    @pytest.mark.asyncio
    async def test_should_retry_without_temperature_when_the_model_rejects_it(self):
        probe = _make_probe()
        model = TemperatureSensitiveChatModel(temperature=0.1)

        result = await probe._get_chat_result(runnable=model, stream=False, input_value="say ok")

        assert result.text == "ok"
        assert model.seen_temperatures == [0.1, None], "expected exactly one retry, with temperature cleared"
        assert model.temperature is None

    @pytest.mark.asyncio
    async def test_should_not_retry_when_the_error_is_unrelated(self):
        probe = _make_probe()
        model = RateLimitedChatModel(temperature=0.1)

        with pytest.raises(ValueError, match="rate_limit_error"):
            await probe._get_chat_result(runnable=model, stream=False, input_value="say ok")

        assert model.call_count == 1, "unrelated errors must propagate without a retry"

    @pytest.mark.asyncio
    async def test_should_propagate_when_the_retry_also_fails(self):
        """Retry exactly once: a second failure is a real error, not a parameter constraint."""
        probe = _make_probe()
        model = TemperatureSensitiveChatModel(temperature=0.1, always_fail=True)

        with pytest.raises(ValueError, match="temperature"):
            await probe._get_chat_result(runnable=model, stream=False, input_value="say ok")

        assert model.seen_temperatures == [0.1, None]

    @pytest.mark.asyncio
    async def test_should_retry_with_a_system_message(self):
        """The system message must survive the retry — the request is rebuilt, not truncated."""
        probe = _make_probe()
        model = TemperatureSensitiveChatModel(temperature=0.1)

        result = await probe._get_chat_result(
            runnable=model, stream=False, input_value="say ok", system_message="You are terse."
        )

        assert result.text == "ok"
        assert model.seen_temperatures == [0.1, None]

    @pytest.mark.asyncio
    async def test_should_retry_when_a_prompt_component_wraps_the_model(self):
        """A Prompt wired into a Language Model turns the runnable into a chain.

        The override has to reach the chat model inside it, otherwise the most common
        Basic Prompting flow shape stays broken while the bare-input shape is fixed.
        """
        probe = _make_probe()
        model = TemperatureSensitiveChatModel(temperature=0.1)
        # ``prompt`` reaches the component jsonable_encoded, which is what load_lc_prompt expects.
        template = ChatPromptTemplate.from_messages([HumanMessage(content="say ok")])
        prompt_message = Message(prompt=jsonable_encoder(template.to_json()))

        result = await probe._get_chat_result(runnable=model, stream=False, input_value=prompt_message)

        assert result.text == "ok"
        assert model.seen_temperatures == [0.1, None]


class TestSyncGetChatResultRetry:
    """``chat_result.get_chat_result`` backs Structured Output and LLM Selector.

    Those components receive an already-built model over a connection, so a Language
    Model component configured with temperature 0.1 hands them a client that fails
    identically — the same bug reached through a different component.
    """

    def test_should_retry_without_temperature_when_the_model_rejects_it(self):
        from lfx.base.models.chat_result import get_chat_result

        model = TemperatureSensitiveChatModel(temperature=0.1)

        result = get_chat_result(runnable=model, input_value="say ok")

        assert result == "ok"
        assert model.seen_temperatures == [0.1, None]

    def test_should_retry_when_a_prompt_component_wraps_the_model(self):
        from lfx.base.models.chat_result import get_chat_result

        model = TemperatureSensitiveChatModel(temperature=0.1)
        template = ChatPromptTemplate.from_messages([HumanMessage(content="say ok")])
        prompt_message = Message(prompt=jsonable_encoder(template.to_json()))

        result = get_chat_result(runnable=model, input_value=prompt_message)

        assert result == "ok"
        assert model.seen_temperatures == [0.1, None]

    def test_should_remediate_the_model_inside_an_incoming_wrapper(self):
        from lfx.base.models.chat_result import get_chat_result

        model = TemperatureSensitiveChatModel(temperature=0.1)
        wrapped = model | StrOutputParser()

        result = get_chat_result(
            runnable=wrapped,
            remediation_target=model,
            input_value="say ok",
        )

        assert result == "ok"
        assert model.seen_temperatures == [0.1, None]

    def test_should_retry_a_lazy_stream_before_the_first_chunk(self):
        from lfx.base.models.chat_result import get_chat_result

        model = TemperatureSensitiveChatModel(temperature=0.1)

        chunks = list(get_chat_result(runnable=model, input_value="say ok", stream=True))

        assert [chunk.content for chunk in chunks] == ["ok"]
        assert model.seen_temperatures == [0.1, None]

    def test_should_not_retry_a_stream_after_emitting_a_chunk(self):
        from lfx.base.models.chat_result import get_chat_result

        model = PartialThenFailStreamingModel()
        chunks = iter(get_chat_result(runnable=model, input_value="say ok", stream=True))

        assert next(chunks).content == "partial"
        with pytest.raises(ProviderBadRequestError, match="temperature"):
            next(chunks)

        assert model.call_count == 1
        assert model.temperature == 0.1

    def test_should_not_retry_when_the_error_is_unrelated(self):
        from lfx.base.models.chat_result import get_chat_result

        model = RateLimitedChatModel(temperature=0.1)

        with pytest.raises(ProviderBadRequestError, match="rate_limit_error"):
            get_chat_result(runnable=model, input_value="say ok")

        assert model.call_count == 1

    def test_should_propagate_when_the_retry_also_fails(self):
        from lfx.base.models.chat_result import get_chat_result

        model = TemperatureSensitiveChatModel(temperature=0.1, always_fail=True)

        with pytest.raises(ProviderBadRequestError, match="temperature"):
            get_chat_result(runnable=model, input_value="say ok")

        assert model.seen_temperatures == [0.1, None]
