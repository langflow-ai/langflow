"""Unit tests for ValkeyIndexChatMemory."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from lfx.base.memory.model import LCChatMemoryComponent
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput, StrInput
from lfx_valkey.components.valkey.valkey_chat import ValkeyIndexChatMemory

# Create a mock for langchain_community.chat_message_histories.redis
_mock_redis_module = ModuleType("langchain_community.chat_message_histories.redis")
_MockRedisChatMessageHistory = MagicMock()
_mock_redis_module.RedisChatMessageHistory = _MockRedisChatMessageHistory


@pytest.fixture(autouse=True)
def _mock_langchain_community():
    """Mock langchain_community so tests work without it installed."""
    modules = {
        "langchain_community": ModuleType("langchain_community"),
        "langchain_community.chat_message_histories": ModuleType("langchain_community.chat_message_histories"),
        "langchain_community.chat_message_histories.redis": _mock_redis_module,
    }
    with patch.dict(sys.modules, modules):
        yield
    _MockRedisChatMessageHistory.reset_mock()


class TestValkeyIndexChatMemoryMetadata:
    def test_display_name(self):
        assert ValkeyIndexChatMemory.display_name == "Valkey Chat Memory"

    def test_icon(self):
        assert ValkeyIndexChatMemory.icon == "Valkey"

    def test_name(self):
        assert ValkeyIndexChatMemory.name == "ValkeyChatMemory"

    def test_description(self):
        assert ValkeyIndexChatMemory.description == "Retrieves and stores chat messages from Valkey."


class TestValkeyIndexChatMemoryInheritance:
    def test_inherits_from_lc_chat_memory_component(self):
        assert issubclass(ValkeyIndexChatMemory, LCChatMemoryComponent)


class TestValkeyIndexChatMemoryInputs:
    def _get_input(self, name: str):
        for inp in ValkeyIndexChatMemory.inputs:
            if inp.name == name:
                return inp
        msg = f"Input '{name}' not found"
        raise AssertionError(msg)

    def test_host_input(self):
        inp = self._get_input("host")
        assert isinstance(inp, StrInput)
        assert inp.value == "localhost"
        assert inp.required is True

    def test_port_input(self):
        inp = self._get_input("port")
        assert isinstance(inp, IntInput)
        assert inp.value == 6379
        assert inp.required is True

    def test_database_input(self):
        inp = self._get_input("database")
        assert isinstance(inp, StrInput)
        assert inp.value == "0"
        assert inp.required is True

    def test_username_input(self):
        inp = self._get_input("username")
        assert isinstance(inp, MessageTextInput)
        assert inp.advanced is True

    def test_password_input(self):
        inp = self._get_input("password")
        assert isinstance(inp, SecretStrInput)
        assert inp.advanced is True

    def test_key_prefix_input(self):
        inp = self._get_input("key_prefix")
        assert isinstance(inp, StrInput)
        assert inp.advanced is True

    def test_session_id_input(self):
        inp = self._get_input("session_id")
        assert isinstance(inp, MessageTextInput)
        assert inp.advanced is True

    def test_all_expected_input_names(self):
        input_names = [inp.name for inp in ValkeyIndexChatMemory.inputs]
        expected = ["host", "port", "database", "username", "password", "key_prefix", "session_id"]
        for name in expected:
            assert name in input_names


class TestValkeyIndexChatMemoryURLConstruction:
    def test_url_uses_redis_scheme(self):
        """RedisChatMessageHistory requires redis:// scheme (wire-compatible with Valkey)."""
        component = ValkeyIndexChatMemory()
        component.host = "localhost"
        component.port = 6379
        component.database = "0"
        component.username = ""
        component.password = ""
        component.key_prefix = ""
        component.session_id = "test-session"
        component.build_message_history()
        url = _MockRedisChatMessageHistory.call_args[1]["url"]
        assert url.startswith("redis://")

    def test_url_contains_host_and_port(self):
        component = ValkeyIndexChatMemory()
        component.host = "myhost"
        component.port = 7777
        component.database = "2"
        component.username = ""
        component.password = ""
        component.key_prefix = ""
        component.session_id = "test-session"
        component.build_message_history()
        url = _MockRedisChatMessageHistory.call_args[1]["url"]
        assert "myhost:7777" in url
        assert url.endswith("/2")

    def test_password_url_encoding(self):
        component = ValkeyIndexChatMemory()
        component.host = "localhost"
        component.port = 6379
        component.database = "0"
        component.username = "user"
        component.password = "test@pass:word/chars"  # noqa: S105  # pragma: allowlist secret
        component.key_prefix = ""
        component.session_id = "test-session"
        component.build_message_history()
        url = _MockRedisChatMessageHistory.call_args[1]["url"]
        assert "test%40pass%3Aword%2Fchars" in url

    def test_username_url_encoding(self):
        component = ValkeyIndexChatMemory()
        component.host = "localhost"
        component.port = 6379
        component.database = "0"
        component.username = "user@example.com"
        component.password = "password"  # noqa: S105  # pragma: allowlist secret
        component.key_prefix = ""
        component.session_id = "test-session"
        component.build_message_history()
        url = _MockRedisChatMessageHistory.call_args[1]["url"]
        assert url == "redis://user%40example.com:password@localhost:6379/0"  # pragma: allowlist secret


class TestValkeyIndexChatMemoryKeyPrefix:
    def test_key_prefix_passed_when_set(self):
        component = ValkeyIndexChatMemory()
        component.host = "localhost"
        component.port = 6379
        component.database = "0"
        component.username = ""
        component.password = ""
        component.key_prefix = "myprefix"
        component.session_id = "test-session"
        component.build_message_history()
        assert _MockRedisChatMessageHistory.call_args[1]["key_prefix"] == "myprefix"

    def test_key_prefix_not_passed_when_empty(self):
        component = ValkeyIndexChatMemory()
        component.host = "localhost"
        component.port = 6379
        component.database = "0"
        component.username = ""
        component.password = ""
        component.key_prefix = ""
        component.session_id = "test-session"
        component.build_message_history()
        assert "key_prefix" not in _MockRedisChatMessageHistory.call_args[1]
