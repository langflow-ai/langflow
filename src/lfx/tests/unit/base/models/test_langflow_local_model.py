"""Tests for ChatLangflowLocal — the wrapper over ChatOllama backing the Langflow Model provider.

Threat model covered:
  - SSRF: a user-controlled base_url could point to internal infra. Whitelist-only.
  - Injection of arbitrary model names → unbounded download surface. Whitelist-only.
  - Silent ImportError if langchain-ollama missing → confusing UX. Must raise clearly.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Defaults — happy path
# ---------------------------------------------------------------------------


class TestChatLangflowLocalDefaults:
    def test_should_use_default_model_when_not_specified(self):
        from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_DEFAULT_MODEL
        from lfx.base.models.langflow_local_model import ChatLangflowLocal

        chat = ChatLangflowLocal()

        assert chat.model == LANGFLOW_LOCAL_DEFAULT_MODEL

    def test_should_use_localhost_base_url_when_not_specified(self):
        from lfx.base.models.langflow_local_model import ChatLangflowLocal

        chat = ChatLangflowLocal()

        assert chat.base_url == "http://localhost:11434"

    def test_should_accept_curated_non_default_model(self):
        # Pick any curated model that is NOT the default — to prove non-default
        # entries also work, and the test does not silently degrade to the default
        # (which would happen if curation was bypassed).
        from lfx.base.models.langflow_local_constants import CURATED_MODEL_NAMES, LANGFLOW_LOCAL_DEFAULT_MODEL
        from lfx.base.models.langflow_local_model import ChatLangflowLocal

        non_default = next(name for name in CURATED_MODEL_NAMES if name != LANGFLOW_LOCAL_DEFAULT_MODEL)

        chat = ChatLangflowLocal(model=non_default)

        assert chat.model == non_default


# ---------------------------------------------------------------------------
# SSRF guard — base_url whitelist
# ---------------------------------------------------------------------------


class TestChatLangflowLocalBaseUrlGuard:
    def test_should_allow_localhost_base_url(self):
        from lfx.base.models.langflow_local_model import ChatLangflowLocal

        chat = ChatLangflowLocal(base_url="http://localhost:11434")

        assert chat.base_url == "http://localhost:11434"

    def test_should_allow_loopback_ipv4_base_url(self):
        from lfx.base.models.langflow_local_model import ChatLangflowLocal

        chat = ChatLangflowLocal(base_url="http://127.0.0.1:11434")

        assert chat.base_url == "http://127.0.0.1:11434"

    def test_should_allow_docker_host_base_url(self):
        from lfx.base.models.langflow_local_model import ChatLangflowLocal

        chat = ChatLangflowLocal(base_url="http://host.docker.internal:11434")

        assert chat.base_url == "http://host.docker.internal:11434"

    @pytest.mark.parametrize(
        "malicious_url",
        [
            "http://evil.com:11434",
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata SSRF classic
            "http://192.168.1.1:11434",
            "http://10.0.0.1:11434",
            "https://attacker.example.com",
            "file:///etc/passwd",
            "http://localhost:22",  # right host, wrong port — port-scan pivot
        ],
    )
    def test_should_reject_when_base_url_is_outside_whitelist(self, malicious_url):
        from lfx.base.models.langflow_local_model import (
            ChatLangflowLocal,
            UnsafeBaseUrlError,
        )

        with pytest.raises(UnsafeBaseUrlError):
            ChatLangflowLocal(base_url=malicious_url)

    def test_unsafe_base_url_error_should_not_leak_full_input(self):
        # Why: error messages can land in logs / clients. Echoing arbitrary user
        # input back unfiltered enables log injection. Message includes a fixed
        # marker plus a sanitized representation, never the raw value verbatim.
        from lfx.base.models.langflow_local_model import (
            ChatLangflowLocal,
            UnsafeBaseUrlError,
        )

        injection_payload = "http://evil.com\r\nFAKE-LOG-LINE: bypass"
        with pytest.raises(UnsafeBaseUrlError) as exc_info:
            ChatLangflowLocal(base_url=injection_payload)

        # Message must NOT contain the CRLF chunk verbatim
        assert "\r\n" not in str(exc_info.value)
        assert "FAKE-LOG-LINE" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# Anti-injection guard — model name whitelist
# ---------------------------------------------------------------------------


class TestChatLangflowLocalModelGuard:
    @pytest.mark.parametrize(
        "uncurated_model",
        [
            "llama3.1:405b",  # 200GB+ download — not curated, would brick the user
            "evil/malicious-model",
            "../../../../etc/passwd",
            "qwen2.5:1.5b; rm -rf /",  # command injection style
            "",
            "   ",
        ],
    )
    def test_should_reject_when_model_is_not_in_curated_set(self, uncurated_model):
        from lfx.base.models.langflow_local_model import (
            ChatLangflowLocal,
            UncuratedModelError,
        )

        with pytest.raises(UncuratedModelError):
            ChatLangflowLocal(model=uncurated_model)


# ---------------------------------------------------------------------------
# Dependency-missing path
# ---------------------------------------------------------------------------


class TestChatLangflowLocalImportFailure:
    def test_should_raise_clear_error_when_langchain_ollama_missing(self):
        # Simulate an environment where langchain_ollama is uninstalled. The wrapper
        # must surface a clear, actionable error — not a bare ModuleNotFoundError
        # bubbling up from somewhere deep in pydantic during instantiation.
        from lfx.base.models.langflow_local_model import (
            ChatLangflowLocal,
            LangchainOllamaMissingError,
        )

        with (
            patch.dict(sys.modules, {"langchain_ollama": None}),
            pytest.raises(LangchainOllamaMissingError) as exc_info,
        ):
            ChatLangflowLocal()

        assert "langchain-ollama" in str(exc_info.value)
        assert "install" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Inheritance / Liskov
# ---------------------------------------------------------------------------


class TestChatLangflowLocalIsSubstitutable:
    def test_should_be_a_subclass_of_chat_ollama(self):
        # LSP: anywhere ChatOllama is accepted, ChatLangflowLocal must work.
        # This unlocks reusing the entire ChatOllama integration (tool calling,
        # streaming, etc.) without re-implementing it.
        from langchain_ollama import ChatOllama
        from lfx.base.models.langflow_local_model import ChatLangflowLocal

        assert issubclass(ChatLangflowLocal, ChatOllama)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
