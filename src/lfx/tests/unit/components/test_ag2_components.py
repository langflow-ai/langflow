"""Unit tests for AG2 Langflow components."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# Install the mock autogen module before any component imports
_mock_autogen_mod = ModuleType("autogen")
_mock_autogen_mod.LLMConfig = MagicMock()
_mock_autogen_mod.AssistantAgent = MagicMock()
_mock_autogen_mod.UserProxyAgent = MagicMock()
_mock_autogen_mod.GroupChat = MagicMock()
_mock_autogen_mod.GroupChatManager = MagicMock()
sys.modules["autogen"] = _mock_autogen_mod

from lfx.components.ag2.ag2_agent import AG2AgentComponent  # noqa: E402
from lfx.components.ag2.ag2_groupchat import AG2GroupChatComponent  # noqa: E402
from lfx.components.ag2.ag2_llm_config import AG2LLMConfigComponent  # noqa: E402
from lfx.components.ag2.ag2_tool_agent import AG2ToolAgentComponent  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_autogen_mocks():
    """Reset mock call counts between tests."""
    _mock_autogen_mod.LLMConfig.reset_mock()
    _mock_autogen_mod.AssistantAgent.reset_mock()
    _mock_autogen_mod.UserProxyAgent.reset_mock()
    _mock_autogen_mod.GroupChat.reset_mock()
    _mock_autogen_mod.GroupChatManager.reset_mock()


class TestAG2LLMConfigComponent:
    """Test AG2 LLM Config component."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-credential"})  # pragma: allowlist secret
    def test_build_config(self):
        component = AG2LLMConfigComponent()
        component.model = "gpt-4o-mini"
        component.api_key = ""
        component.api_type = "openai"
        component.base_url = ""

        component.build_config()

        _mock_autogen_mod.LLMConfig.assert_called_once_with(
            {
                "model": "gpt-4o-mini",
                "api_key": "test-credential",  # pragma: allowlist secret
                "api_type": "openai",
            }
        )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-credential"})  # pragma: allowlist secret
    def test_build_config_with_explicit_key(self):
        component = AG2LLMConfigComponent()
        component.model = "gpt-4o"
        component.api_key = "explicit-credential"  # pragma: allowlist secret
        component.api_type = "openai"
        component.base_url = ""

        component.build_config()

        _mock_autogen_mod.LLMConfig.assert_called_once_with(
            {
                "model": "gpt-4o",
                "api_key": "explicit-credential",  # pragma: allowlist secret
                "api_type": "openai",
            }
        )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-credential"})  # pragma: allowlist secret
    def test_build_config_with_base_url(self):
        component = AG2LLMConfigComponent()
        component.model = "gpt-4o-mini"
        component.api_key = ""
        component.api_type = "openai"
        component.base_url = "https://custom.api.example.com/v1"

        component.build_config()

        _mock_autogen_mod.LLMConfig.assert_called_once_with(
            {
                "model": "gpt-4o-mini",
                "api_key": "test-credential",  # pragma: allowlist secret
                "api_type": "openai",
                "base_url": "https://custom.api.example.com/v1",
            }
        )

    def test_build_config_no_key_raises(self):
        component = AG2LLMConfigComponent()
        component.model = "gpt-4o-mini"
        component.api_key = ""
        component.api_type = "openai"
        component.base_url = ""

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValueError, match="API key is required"):
            component.build_config()


class TestAG2AgentComponent:
    """Test AG2 Agent component."""

    def test_build_agent(self):
        component = AG2AgentComponent()
        component.agent_name = "Researcher"
        component.system_message = "You research topics."
        component.llm_config = MagicMock()
        component.is_terminator = False

        component.build_agent()

        _mock_autogen_mod.AssistantAgent.assert_called_once_with(
            name="Researcher",
            system_message="You research topics.",
            llm_config=component.llm_config,
        )

    def test_build_agent_sets_status(self):
        component = AG2AgentComponent()
        component.agent_name = "Writer"
        component.system_message = "You write."
        component.llm_config = MagicMock()
        component.is_terminator = False

        component.build_agent()

        assert _mock_autogen_mod.AssistantAgent.called
        assert component.status == "Agent: Writer"


class TestAG2GroupChatComponent:
    """Test AG2 GroupChat component."""

    def test_no_agents_raises(self):
        component = AG2GroupChatComponent()
        component.agents = []
        component.llm_config = MagicMock()
        component.message = "Hello"
        component.max_rounds = 8
        component.speaker_selection = "auto"

        with pytest.raises(ValueError, match="At least one AG2 Agent"):
            component.run_groupchat()

    def test_empty_message_raises(self):
        component = AG2GroupChatComponent()
        component.agents = [MagicMock()]
        component.llm_config = MagicMock()
        component.message = ""
        component.max_rounds = 8
        component.speaker_selection = "auto"

        with pytest.raises(ValueError, match="Message cannot be empty"):
            component.run_groupchat()

    def test_whitespace_message_raises(self):
        component = AG2GroupChatComponent()
        component.agents = [MagicMock()]
        component.llm_config = MagicMock()
        component.message = "   "
        component.max_rounds = 8
        component.speaker_selection = "auto"

        with pytest.raises(ValueError, match="Message cannot be empty"):
            component.run_groupchat()


class TestAG2ToolAgentComponent:
    """Test AG2 Tool Agent component."""

    def test_empty_message_raises(self):
        component = AG2ToolAgentComponent()
        component.llm_config = MagicMock()
        component.message = ""
        component.system_message = "You are a helpful assistant."

        with pytest.raises(ValueError, match="Message cannot be empty"):
            component.run_tool_agent()
