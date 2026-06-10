"""Tests for the Lothal LLM bridge (Story 0.1 — LLM Caller).

Per the backlog's testing philosophy, every test below injects a controlled,
fake SDK response and asserts *our* behaviour (routing, mapping, error
wrapping). The single test that makes a real model call —
`test_call_llm_real_subscription` — is marked `api_key_required`, which the
suite excludes by default (`-m "not api_key_required"`); run it explicitly to
verify live connectivity.
"""

import sys
import types
from importlib.util import find_spec

import pytest
from langflow.lothal.llm import (
    LLMConfigError,
    LLMConnectionError,
    LLMProvider,
    available_providers,
    call_llm,
    get_provider,
    validate_messages,
)
from langflow.lothal.llm import registry as llm_registry
from langflow.lothal.llm.providers.claude import ClaudeAgentProvider, _to_agent_input

# --- fakes -------------------------------------------------------------------


def make_fake_sdk():
    """Build a fake `claude_agent_sdk` module mirroring the symbols we use.

    `query` streams whatever is on `sdk._yields` (or raises `sdk._raise`), and
    records the prompt/options it was called with on `sdk._captured` — so a test
    can set the response *after* install, using the fake's own message classes.
    """
    sdk = types.ModuleType("claude_agent_sdk")

    class TextBlock:
        def __init__(self, text):
            self.text = text

    class AssistantMessage:
        def __init__(self, content):
            self.content = content

    class ResultMessage:
        def __init__(self, total_cost_usd=0.0):
            self.total_cost_usd = total_cost_usd

    class ClaudeAgentOptions:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    async def query(*, prompt, options):
        sdk._captured = {"prompt": prompt, "options": options}
        if sdk._raise is not None:
            raise sdk._raise
        for message in sdk._yields:
            yield message

    sdk.TextBlock = TextBlock
    sdk.AssistantMessage = AssistantMessage
    sdk.ResultMessage = ResultMessage
    sdk.ClaudeAgentOptions = ClaudeAgentOptions
    sdk.query = query
    sdk._yields = []
    sdk._raise = None
    sdk._captured = {}
    return sdk


@pytest.fixture
def fake_sdk(monkeypatch):
    """Install a fake `claude_agent_sdk` and return the module.

    Tests build their response stream from the fake's message classes and set
    `sdk._yields` / `sdk._raise` before invoking the caller.
    """
    sdk = make_fake_sdk()
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", sdk)
    return sdk


# --- message validation (typed errors on bad input) --------------------------


def test_validate_messages_rejects_empty():
    with pytest.raises(LLMConfigError):
        validate_messages([])


@pytest.mark.parametrize(
    "messages",
    [
        ["not a dict"],
        [{"role": "boss", "content": "hi"}],
        [{"role": "user", "content": ""}],
        [{"role": "user", "content": "   "}],
        [{"role": "user"}],
    ],
)
def test_validate_messages_rejects_malformed(messages):
    with pytest.raises(LLMConfigError):
        validate_messages(messages)


def test_validate_messages_accepts_valid():
    validate_messages([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}])


async def test_call_llm_empty_messages_raises_before_provider():
    with pytest.raises(LLMConfigError):
        await call_llm([])


# --- provider registry (open/closed) -----------------------------------------


def test_default_provider_is_claude():
    assert "claude" in available_providers()
    assert isinstance(get_provider(), ClaudeAgentProvider)


def test_unknown_provider_raises_config_error():
    with pytest.raises(LLMConfigError):
        get_provider("does-not-exist")


def test_model_name_read_from_env(monkeypatch):
    monkeypatch.setenv("LOTHAL_MODEL_NAME", "claude-sonnet-4-6")
    assert get_provider("claude").model == "claude-sonnet-4-6"


def test_model_name_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("LOTHAL_MODEL_NAME", raising=False)
    assert get_provider("claude").model == ClaudeAgentProvider.DEFAULT_MODEL


def test_provider_selected_from_env(monkeypatch):
    monkeypatch.setenv("LOTHAL_LLM_PROVIDER", "claude")
    assert isinstance(get_provider(), ClaudeAgentProvider)


async def test_call_llm_routes_to_registered_provider():
    """Adding a provider needs no change to `call_llm` (open/closed)."""
    seen = {}

    class FakeProvider(LLMProvider):
        name = "fake"

        @classmethod
        def from_env(cls):
            return cls()

        async def complete(self, messages, **kwargs):
            seen["messages"] = messages
            seen["kwargs"] = kwargs
            return "fake reply"

    snapshot = dict(llm_registry._REGISTRY)
    llm_registry.register_provider(FakeProvider)
    try:
        result = await call_llm([{"role": "user", "content": "hi"}], provider="fake", temperature=0.5)
    finally:
        llm_registry._REGISTRY.clear()
        llm_registry._REGISTRY.update(snapshot)

    assert result == "fake reply"
    assert seen["messages"] == [{"role": "user", "content": "hi"}]
    assert seen["kwargs"] == {"temperature": 0.5}


# --- message -> Agent SDK input mapping --------------------------------------


def test_to_agent_input_single_user_turn_passes_content_verbatim():
    system, prompt = _to_agent_input([{"role": "user", "content": "say hi"}])
    assert system == ""
    assert prompt == "say hi"


def test_to_agent_input_extracts_system_prompt():
    system, prompt = _to_agent_input([{"role": "system", "content": "be terse"}, {"role": "user", "content": "hi"}])
    assert system == "be terse"
    assert prompt == "hi"


def test_to_agent_input_folds_history_into_transcript():
    _, prompt = _to_agent_input(
        [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
        ]
    )
    assert prompt == "User: a\n\nAssistant: b\n\nUser: c\n\nAssistant:"


def test_to_agent_input_requires_a_conversation_turn():
    with pytest.raises(LLMConfigError):
        _to_agent_input([{"role": "system", "content": "only system"}])


# --- Claude provider against a fake SDK ---------------------------------------


async def test_claude_provider_returns_joined_text(fake_sdk):
    fake_sdk._yields = [
        object(),  # a non-AssistantMessage in the stream is ignored
        fake_sdk.AssistantMessage([fake_sdk.TextBlock("Hello "), fake_sdk.TextBlock("there")]),
        fake_sdk.ResultMessage(total_cost_usd=0.01),
    ]
    out = await call_llm(
        [{"role": "system", "content": "be terse"}, {"role": "user", "content": "hi"}],
    )
    assert out == "Hello there"
    # The configured model and system prompt reached the SDK options.
    options = fake_sdk._captured["options"]
    assert options.model == ClaudeAgentProvider.DEFAULT_MODEL
    assert options.system_prompt == "be terse"
    assert options.allowed_tools == []
    assert fake_sdk._captured["prompt"] == "hi"


async def test_per_call_model_overrides_env_default(fake_sdk, monkeypatch):
    monkeypatch.setenv("LOTHAL_MODEL_NAME", "claude-opus-4-8")
    fake_sdk._yields = [fake_sdk.AssistantMessage([fake_sdk.TextBlock("ok")])]
    out = await call_llm([{"role": "user", "content": "hi"}], model="claude-sonnet-4-6")
    assert out == "ok"
    assert fake_sdk._captured["options"].model == "claude-sonnet-4-6"


async def test_model_falls_back_to_provider_default_when_not_passed(fake_sdk, monkeypatch):
    monkeypatch.setenv("LOTHAL_MODEL_NAME", "claude-haiku-4-5")
    fake_sdk._yields = [fake_sdk.AssistantMessage([fake_sdk.TextBlock("ok")])]
    await call_llm([{"role": "user", "content": "hi"}])
    assert fake_sdk._captured["options"].model == "claude-haiku-4-5"


async def test_claude_provider_empty_response_raises_connection_error(fake_sdk):
    fake_sdk._yields = []
    with pytest.raises(LLMConnectionError):
        await call_llm([{"role": "user", "content": "hi"}])


async def test_claude_provider_wraps_sdk_failure(fake_sdk):
    fake_sdk._raise = RuntimeError("boom")
    with pytest.raises(LLMConnectionError):
        await call_llm([{"role": "user", "content": "hi"}])


async def test_claude_provider_missing_sdk_raises_config_error(monkeypatch):
    # `import claude_agent_sdk` raises ImportError when its entry is None.
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    with pytest.raises(LLMConfigError):
        await call_llm([{"role": "user", "content": "hi"}])


# --- the one real-LLM test ----------------------------------------------------


@pytest.mark.api_key_required
async def test_call_llm_real_subscription():
    """Story 0.1 acceptance: a real call returns a non-empty string.

    Excluded from the default suite (`api_key_required`); run with a live Claude
    Code subscription via `-m api_key_required`.
    """
    if find_spec("claude_agent_sdk") is None:
        pytest.skip("claude-agent-sdk not installed")
    reply = await call_llm([{"role": "user", "content": "say hi"}])
    assert isinstance(reply, str)
    assert reply.strip()
