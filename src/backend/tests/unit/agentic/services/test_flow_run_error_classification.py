"""classify_run_error — decide if a failed verification run is fixable.

The flow-verification loop must NOT burn LLM tokens retrying a flow whose
run failed for a reason the LLM cannot fix (missing user API key, DB,
file, network) or a timeout. It SHOULD retry genuine code/wiring/spec
bugs. This classifier is the pure decision at the heart of that loop.
"""

from __future__ import annotations

import pytest
from langflow.agentic.services.flow_run_error_classification import (
    RunErrorKind,
    classify_run_error,
)


class TestExternalResourceErrors:
    @pytest.mark.parametrize(
        "message",
        [
            "Incorrect API key provided: sk-abc***",
            "AuthenticationError: invalid api key",
            "401 Unauthorized",
            "403 Forbidden",
            "OPENAI_API_KEY is not set. Please configure it.",
            "Missing API key for provider Anthropic",
            "Connection refused",
            "Failed to resolve 'api.openai.com'",
            "Max retries exceeded with url: /v1/chat/completions",
            "No such file or directory: '/data/handbook.pdf'",
            "could not connect to database: connection timed out",
            "Rate limit reached for gpt-4o",
            "429 Too Many Requests",
            # A model the account can't call — the agent can't fix this by
            # rebuilding, so it must NOT trigger the 3x fix-retry loop (which
            # hangs the chat on "Crafting your component...").
            "Model not available. Please select a different model.",
            "The model `gpt-5.4` model_not_found",
            "Project does not have access to model gpt-5.4",
        ],
    )
    def test_should_classify_as_external_resource_when_error_needs_user_supplied_resource(self, message):
        assert classify_run_error(message) is RunErrorKind.EXTERNAL_RESOURCE


class TestTimeout:
    def test_should_classify_as_timeout_when_run_timed_out(self):
        assert classify_run_error("The flow run timed out after 120s.") is RunErrorKind.TIMEOUT


class TestFixableErrors:
    @pytest.mark.parametrize(
        "message",
        [
            "Attribute build_output not found in PrimeChecker",
            "No model selected",
            "Component type 'FooBar' not found in registry",
            "AttributeError: 'NoneType' object has no attribute 'text'",
            "ValidationError: 1 validation error for ChatOutput",
            "TypeError: run() missing 1 required positional argument",
            "NameError: name 'Messsage' is not defined",
            "Edge target handle 'xyz' does not exist on node Agent-1",
        ],
    )
    def test_should_classify_as_fixable_when_error_is_a_code_or_wiring_bug(self, message):
        assert classify_run_error(message) is RunErrorKind.FIXABLE

    def test_should_classify_keyerror_as_fixable_not_external_even_when_it_mentions_api_key(self):
        # Adversarial: a missing dict key named 'api_key' in the SPEC is a
        # code/wiring bug the LLM can fix — it is NOT a missing credential.
        # The Python-exception marker must win over the 'api key' substring.
        assert classify_run_error("KeyError: 'api_key'") is RunErrorKind.FIXABLE


class TestUnknownAndEmpty:
    @pytest.mark.parametrize("message", ["", "   ", None])
    def test_should_classify_empty_error_as_unknown(self, message):
        assert classify_run_error(message) is RunErrorKind.UNKNOWN

    def test_should_classify_unmatched_error_as_unknown(self):
        assert classify_run_error("something weird happened deep in the engine") is RunErrorKind.UNKNOWN

    def test_should_be_case_insensitive(self):
        assert classify_run_error("INCORRECT API KEY PROVIDED") is RunErrorKind.EXTERNAL_RESOURCE
        assert classify_run_error("attributeerror: boom") is RunErrorKind.FIXABLE
