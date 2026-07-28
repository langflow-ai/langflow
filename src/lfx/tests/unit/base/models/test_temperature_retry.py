"""``LCModelComponent._get_chat_result`` retries once when a model rejects temperature.

Some models answer an explicit ``temperature`` with an HTTP 400 instead of
clamping it — Anthropic's Sonnet-5 generation, for example, replies with
``400 invalid_request_error: `temperature` is deprecated for this model.``.
Without a retry, every call through such a model fails hard for as long as the
component (or a hardcoded caller) keeps sending a non-default temperature. The
safety net strips the temperature off the underlying chat model and retries
exactly once.

The narrowness of the match matters as much as the retry: every other failure
(including unrelated 400s) must keep failing on the first attempt, with the
error the caller sees today.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnablePassthrough
from lfx.base.models.model import LCModelComponent, _is_temperature_rejection
from pydantic import Field

_ANTHROPIC_TEMPERATURE_400 = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': '`temperature` is deprecated for this model.'}}"
)


def test_matches_wrapped_400_message_without_status_code():
    """Wrapped provider errors may retain the HTTP status only in their text."""
    assert _is_temperature_rejection(ValueError(_ANTHROPIC_TEMPERATURE_400)) is True


def test_does_not_treat_4000_as_http_400():
    """A larger number containing 400 must not qualify as an HTTP 400 status."""
    error = ValueError("temperature is deprecated after 4000 requests")

    assert _is_temperature_rejection(error) is False


class _BadRequestError(Exception):
    """Stand-in for ``anthropic.BadRequestError`` (same ``status_code`` surface)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 400


class _TemperaturePickyChatModel(BaseChatModel):
    """Fake chat model that 400s whenever an explicit temperature is set."""

    temperature: float | None = None
    attempts: list[float | None] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "temperature-picky-fake"

    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:  # noqa: ARG002
        """Record the temperature this attempt was made with; reject anything explicit.

        ``messages`` / ``stop`` / ``run_manager`` are accepted positionally or by
        keyword to satisfy BaseChatModel's call contract but are irrelevant here.
        """
        self.attempts.append(self.temperature)
        if self.temperature is not None:
            raise _BadRequestError(_ANTHROPIC_TEMPERATURE_400)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])


class _AlwaysRejectingChatModel(_TemperaturePickyChatModel):
    """Rejects the temperature even after it has been stripped, tagging each attempt."""

    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:  # noqa: ARG002
        self.attempts.append(self.temperature)
        msg = f"{_ANTHROPIC_TEMPERATURE_400} attempt={len(self.attempts)}"
        raise _BadRequestError(msg)


class _Probe(LCModelComponent):
    """Minimal LCModelComponent usable without going through Component init."""

    display_name = "Probe"
    description = "test"

    def build_model(self):  # pragma: no cover - abstract stub
        raise NotImplementedError


def _make_probe(*, connected: bool = False, session_id: str = "", event_manager: Any = None) -> _Probe:
    """Build a probe. The streaming knobs mirror ``test_handle_stream``'s wiring.

    ``connected`` / ``session_id`` / ``event_manager`` select which branch of
    ``_handle_stream`` a ``stream=True`` call lands in.
    """
    probe = _Probe.__new__(_Probe)
    probe.get_project_name = MagicMock(return_value="test-project")
    probe.get_langchain_callbacks = MagicMock(return_value=[])
    probe.is_connected_to_chat_output = MagicMock(return_value=connected)
    # ``graph`` is a read-only property on Component (-> self._vertex.graph),
    # so wire the underlying _vertex instead of assigning graph directly.
    probe._vertex = SimpleNamespace(graph=SimpleNamespace(session_id=session_id, flow_id=None))
    probe.icon = "brain"
    probe._id = "probe-1"
    probe._event_manager = event_manager
    probe.send_message = AsyncMock(side_effect=lambda message, **_kw: message)
    probe._build_source = MagicMock(return_value=None)
    return probe


async def test_retries_once_without_temperature_when_model_rejects_it():
    """A temperature-rejection 400 must be recovered from, not surfaced to the user."""
    probe = _make_probe()
    model = _TemperaturePickyChatModel(temperature=0.1)

    result = await probe._get_chat_result(runnable=model, stream=False, input_value="hello")

    assert result.text == "ok"
    assert model.attempts == [0.1, None], (
        "Expected exactly two attempts: the original (temperature=0.1) and one retry with the "
        f"temperature stripped. Got {model.attempts!r}."
    )


async def test_retries_once_when_the_chat_model_is_nested_in_a_chain():
    """``_get_chat_result`` may run ``prompt | model | output_parser``, not a bare model.

    The chat model then sits inside a RunnableSequence inside the ``with_config``
    binding, so the retry has to reach through both wrappers and rebuild the
    chain — otherwise flows with a prompt or an output parser stay broken.
    """
    probe = _make_probe()
    model = _TemperaturePickyChatModel(temperature=0.1)
    chain = RunnablePassthrough() | model | StrOutputParser()

    result = await probe._get_chat_result(runnable=chain, stream=False, input_value="hello")

    assert result.text == "ok"
    assert model.attempts == [0.1, None], (
        f"Expected the nested chat model's temperature to be stripped on retry. Got {model.attempts!r}."
    )


async def test_retries_once_on_the_streaming_not_connected_to_chat_output_path():
    """``stream=True`` without a chat output still calls ainvoke — it needs the same net.

    A model with streaming enabled that is not wired to ChatOutput never streams;
    ``_handle_stream`` invokes it in one shot. Leaving that call unguarded means the
    fix only works for half the flows that use the model.
    """
    probe = _make_probe(connected=False)
    model = _TemperaturePickyChatModel(temperature=0.1)

    result = await probe._get_chat_result(runnable=model, stream=True, input_value="hello")

    assert result.text == "ok"
    assert model.attempts == [0.1, None], f"Expected one retry with the temperature stripped. Got {model.attempts!r}."


async def test_retries_once_on_the_streaming_fallback_to_ainvoke_path():
    """The ``missing session_id/event_manager`` streaming fallback also calls ainvoke.

    This is the path taken by ``lfx run`` and any run without an event manager, so
    it must recover from a temperature rejection exactly like the non-streaming path.
    """
    probe = _make_probe(connected=True, session_id="sess-123", event_manager=None)
    model = _TemperaturePickyChatModel(temperature=0.1)

    result = await probe._get_chat_result(runnable=model, stream=True, input_value="hello")

    assert result.text == "ok"
    assert model.attempts == [0.1, None], f"Expected one retry with the temperature stripped. Got {model.attempts!r}."
    probe.send_message.assert_not_awaited()


async def test_streaming_astream_path_surfaces_the_rejection_only_on_consumption():
    """Characterization of the one path the retry deliberately does NOT cover.

    On the real streaming path ``_handle_stream`` hands ``runnable.astream(inputs)``
    to ``Message`` and returns; nothing has been sent to the model yet. The 400
    therefore surfaces later, while the event manager drains the generator — by
    which point chunks may already have reached the UI, so a retry would either
    duplicate output or require buffering the whole stream. This test pins that
    boundary so the accepted gap documented in ``_handle_stream`` stays true, and
    any future attempt to close it has to change this test on purpose.
    """
    probe = _make_probe(connected=True, session_id="sess-123", event_manager=MagicMock())
    model = _TemperaturePickyChatModel(temperature=0.1)

    message = await probe._get_chat_result(runnable=model, stream=True, input_value="hello")

    assert model.attempts == [], "astream() must not have touched the model before consumption starts"

    with pytest.raises(_BadRequestError):
        async for _chunk in message.text:
            pass

    assert model.attempts == [0.1], (
        "Accepted gap: the streamed call is not retried without temperature. "
        f"Got {model.attempts!r} — if this now shows a retry, update the comment in _handle_stream."
    )


async def test_raises_the_second_failure_when_the_retry_also_fails():
    """The retry must happen, must happen once, and the SECOND error is what escapes.

    Uses a model that keeps rejecting even with the temperature stripped, so the
    retry is genuinely attempted (unlike an unstrippable runnable, which short-circuits
    — that branch is covered separately below). Each attempt tags its error with the
    attempt number, which is what proves the caller sees the second failure rather
    than a replay of the first.
    """
    probe = _make_probe()
    model = _AlwaysRejectingChatModel(temperature=0.1)

    with pytest.raises(ValueError, match="attempt=2"):
        await probe._get_chat_result(runnable=model, stream=False, input_value="hello")

    assert model.attempts == [0.1, None], (
        f"Expected exactly two attempts — the original and one stripped retry — and no loop. Got {model.attempts!r}."
    )


async def test_does_not_retry_when_no_chat_model_can_be_located():
    """With nothing strippable in the runnable there is no retry candidate: raise immediately.

    A runnable that is neither a chat model nor a wrapper around one (no
    bound/first/middle/last) cannot have its temperature removed, so re-issuing the
    identical call would just burn a second request for the same failure.
    """
    probe = _make_probe()
    runnable = SimpleNamespace(
        with_config=lambda _config: runnable,
        ainvoke=AsyncMock(side_effect=_BadRequestError(_ANTHROPIC_TEMPERATURE_400)),
        temperature=0.1,
    )

    with pytest.raises(ValueError, match="temperature"):
        await probe._get_chat_result(runnable=runnable, stream=False, input_value="hello")

    assert runnable.ainvoke.await_count == 1, (
        f"Nothing to strip means no second call; got {runnable.ainvoke.await_count} attempts."
    )


async def test_unrelated_error_is_not_retried():
    """A plain error must behave exactly as it does today: one attempt, then raise."""
    probe = _make_probe()
    runnable = SimpleNamespace(
        with_config=lambda _config: runnable,
        ainvoke=AsyncMock(side_effect=ValueError("connection reset")),
    )

    with pytest.raises(ValueError, match="connection reset"):
        await probe._get_chat_result(runnable=runnable, stream=False, input_value="hello")

    assert runnable.ainvoke.await_count == 1, (
        f"Unrelated errors must not trigger the temperature retry; got {runnable.ainvoke.await_count} attempts."
    )


async def test_unrelated_400_is_not_retried():
    """A 400 whose message is not about a deprecated temperature must not be retried."""
    probe = _make_probe()
    runnable = SimpleNamespace(
        with_config=lambda _config: runnable,
        ainvoke=AsyncMock(side_effect=_BadRequestError("Error code: 400 - invalid api key")),
        temperature=0.1,
    )

    with pytest.raises(ValueError, match="invalid api key"):
        await probe._get_chat_result(runnable=runnable, stream=False, input_value="hello")

    assert runnable.ainvoke.await_count == 1, (
        f"Only the documented temperature rejection is retried; got {runnable.ainvoke.await_count} attempts."
    )
