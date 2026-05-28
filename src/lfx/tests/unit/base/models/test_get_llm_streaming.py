"""Regression guards for the streaming contract of unified ``get_llm``.

The Agent pipeline depends on three sequential invariants:

1. ``AgentComponent._get_llm`` passes ``stream=True`` to ``get_llm`` (covered
   in ``test_agent_create_agent``).
2. ``get_llm`` forwards that flag to the chat model constructor as
   ``streaming=<value>`` — this file.
3. ``ToolCallingAgentComponent.create_agent_runnable`` enforces
   ``llm.streaming = True`` as a backward-compat shim for serialized flows
   that pre-date the wiring above (covered in
   ``src/backend/tests/unit/components/models_and_agents/test_tool_calling_agent.py``).

If layer 2 silently drops the kwarg, layers 1 and 3 cannot recover — a chat
model built without ``streaming=True`` emits a single ``on_chat_model_end``
event and Playground live-typing breaks. These tests pin the contract.
"""

from __future__ import annotations

from unittest.mock import patch


def _capture_factory():
    captured: dict = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    return FakeChatModel, captured


def _build_openai_model_selection() -> list[dict]:
    return [
        {
            "name": "gpt-4o-mini",
            "provider": "OpenAI",
            "metadata": {
                "model_class": "ChatOpenAI",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
            },
        }
    ]


def _build_anthropic_model_selection() -> list[dict]:
    return [
        {
            "name": "claude-3-5-sonnet-latest",
            "provider": "Anthropic",
            "metadata": {
                "model_class": "ChatAnthropic",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
            },
        }
    ]


def test_should_forward_streaming_true_to_chat_model_kwargs_when_stream_true():
    """Layer 2 contract: stream=True must materialize as ``streaming=True`` kwarg."""
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    fake_cls, captured = _capture_factory()

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="sk-dummy",  # pragma: allowlist secret
        ),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
    ):
        get_llm(_build_openai_model_selection(), user_id=None, stream=True)

    assert captured.get("streaming") is True, (
        f"get_llm(stream=True) must pass streaming=True to the chat model constructor. "
        f"Got streaming={captured.get('streaming')!r}. Without this the AgentComponent "
        "and LanguageModelComponent paths cannot emit on_chat_model_stream events."
    )


def test_should_forward_streaming_false_to_chat_model_kwargs_when_stream_false():
    """Layer 2 contract: stream=False must materialize as ``streaming=False`` kwarg.

    Validates the negative side of the contract — the toggle must remain functional
    for the LanguageModelComponent (which exposes streaming as a user opt-in).
    """
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    fake_cls, captured = _capture_factory()

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="sk-dummy",  # pragma: allowlist secret
        ),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
    ):
        get_llm(_build_openai_model_selection(), user_id=None, stream=False)

    assert captured.get("streaming") is False, (
        f"get_llm(stream=False) must pass streaming=False. Got streaming={captured.get('streaming')!r}. "
        "Inverting this breaks the LanguageModelComponent's opt-in toggle."
    )


def test_should_default_streaming_to_false_when_stream_kwarg_omitted():
    """Default behavior: legacy callers that omit ``stream=`` get streaming=False.

    This is the unfixed state that drives the backward-compat shim in
    ``ToolCallingAgentComponent.create_agent_runnable``. If this default ever
    flips to True, the shim becomes a no-op (harmless but misleading); if a
    future PR removes the default entirely, callers that don't pass stream
    will raise TypeError — pin the current behavior so changes are deliberate.
    """
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    fake_cls, captured = _capture_factory()

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="sk-dummy",  # pragma: allowlist secret
        ),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
    ):
        get_llm(_build_openai_model_selection(), user_id=None)

    assert captured.get("streaming") is False, (
        f"get_llm() default must produce streaming=False so the shim path is "
        f"exercised for legacy serialized flows. Got streaming={captured.get('streaming')!r}."
    )


def test_should_set_stream_usage_true_for_openai_when_streaming():
    """OpenAI providers must request usage on streamed responses.

    ``stream_usage=True`` is what makes ChatOpenAI emit token-count metadata on
    streamed chunks (otherwise usage arrives only on the final non-stream call).
    The Playground/API surface relies on these counts to display per-message
    token cost. Pinning this for the OpenAI path; Anthropic has the same
    contract — covered separately below.
    """
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    fake_cls, captured = _capture_factory()

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="sk-dummy",  # pragma: allowlist secret
        ),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
    ):
        get_llm(_build_openai_model_selection(), user_id=None, stream=True)

    assert captured.get("stream_usage") is True, (
        "OpenAI streaming responses must carry stream_usage=True so token usage is "
        "reported on each chunk and the Playground can show running cost."
    )


def test_should_set_stream_usage_true_for_anthropic_when_streaming():
    """Anthropic ChatAnthropic mirrors the OpenAI streaming-usage contract."""
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    fake_cls, captured = _capture_factory()

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="sk-ant-dummy",  # pragma: allowlist secret
        ),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
    ):
        get_llm(_build_anthropic_model_selection(), user_id=None, stream=True)

    assert captured.get("streaming") is True
    assert captured.get("stream_usage") is True, (
        "Anthropic streaming responses must carry stream_usage=True for token-cost reporting."
    )
