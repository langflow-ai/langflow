"""Tests for provider-agnostic, error-driven model remediation.

The constraint some models impose (e.g. OpenAI gpt-5.6 rejecting function tools
+ reasoning_effort on /v1/chat/completions) is not exposed by any provider's
model listing, so remediation is matched on the provider's ERROR TEXT and the
winning overrides are remembered per model (discover-once).
"""

from types import SimpleNamespace

import pytest
from lfx.base.models.model_remediation import (
    Remediation,
    apply_overrides_to_model,
    cached_overrides,
    find_remediation,
    remember,
    reset_remediation_cache,
)

GPT56_ERROR = (
    "Error building Component Agent: Error code: 400 - {'error': {'message': "
    '"Function tools with reasoning_effort are not supported for gpt-5.6-luna in '
    "/v1/chat/completions. To use function tools, use /v1/responses or set "
    "reasoning_effort to 'none'.\", 'type': 'invalid_request_error'}}"
)

# Verbatim Amazon Bedrock Converse responses from us.anthropic.claude-opus-5-5, which rejects
# each field on its own 400 once the previous one is cleared.
BEDROCK_TOP_K_ERROR = (
    "An error occurred (ValidationException) when calling the Converse operation: "
    "The model returned the following errors: `top_k` is deprecated for this model."
)
BEDROCK_TOP_P_ERROR = (
    "An error occurred (ValidationException) when calling the Converse operation: "
    "The model returned the following errors: `top_p` is deprecated for this model."
)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_remediation_cache()
    yield
    reset_remediation_cache()


class TestFindRemediation:
    def test_should_match_openai_responses_api_constraint(self):
        rem = find_remediation(GPT56_ERROR, provider="OpenAI", already_applied=set())
        assert rem is not None
        assert rem.overrides == {"use_responses_api": True}

    def test_should_not_match_openai_responses_api_constraint_when_provider_is_unknown(self):
        rem = find_remediation(GPT56_ERROR, provider=None, already_applied=set())
        assert rem is None

    def test_should_match_alternate_openai_responses_api_wording(self):
        error = "reasoning_effort is incompatible with function tools. To use function tools, use /v1/responses."
        rem = find_remediation(error, provider="OpenAI", already_applied=set())
        assert rem is not None
        assert rem.overrides == {"use_responses_api": True}

    def test_should_not_match_for_a_different_provider(self):
        assert find_remediation(GPT56_ERROR, provider="Anthropic", already_applied=set()) is None

    def test_should_not_match_unrelated_errors(self):
        assert find_remediation("rate limit exceeded", provider="OpenAI", already_applied=set()) is None

    def test_should_not_match_an_unrelated_responses_api_suggestion(self):
        error = "This feature is only available through /v1/responses."
        assert find_remediation(error, provider=None, already_applied=set()) is None

    def test_should_skip_a_remediation_already_applied(self):
        rem = find_remediation(GPT56_ERROR, provider="OpenAI", already_applied=set())
        assert rem is not None
        assert find_remediation(GPT56_ERROR, provider="OpenAI", already_applied={rem.name}) is None

    def test_matches_is_case_insensitive(self):
        assert find_remediation(GPT56_ERROR.upper(), provider="OpenAI", already_applied=set()) is not None

    @pytest.mark.parametrize(
        ("error", "overrides"),
        [(BEDROCK_TOP_K_ERROR, {"top_k": None}), (BEDROCK_TOP_P_ERROR, {"top_p": None})],
        ids=["top_k", "top_p"],
    )
    def test_should_match_claude_top_k_and_top_p_rejections(self, error, overrides):
        rem = find_remediation(error, provider=None, already_applied=set())
        assert rem is not None
        assert rem.overrides == overrides


class TestApplyOverridesToModel:
    def test_should_clear_a_field_carried_in_additional_model_request_fields(self):
        """ChatBedrockConverse has no top_k attribute; it sends top_k from that dict."""
        model = SimpleNamespace(additional_model_request_fields={"top_k": 250, "thinking": {"type": "adaptive"}})

        assert apply_overrides_to_model(model, {"top_k": None}) is True
        assert model.additional_model_request_fields == {"thinking": {"type": "adaptive"}}
        # Nothing left to clear, so a repeat of the same error is not retried.
        assert apply_overrides_to_model(model, {"top_k": None}) is False


class TestRemediationCache:
    def test_remember_and_read_overrides_per_model(self):
        assert cached_overrides("OpenAI", "gpt-5.6") == {}
        remember("OpenAI", "gpt-5.6", {"use_responses_api": True})
        assert cached_overrides("OpenAI", "gpt-5.6") == {"use_responses_api": True}

    def test_cache_is_scoped_per_model(self):
        remember("OpenAI", "gpt-5.6", {"use_responses_api": True})
        assert cached_overrides("OpenAI", "gpt-5.5") == {}

    def test_remember_merges_overrides(self):
        remember("OpenAI", "gpt-5.6", {"use_responses_api": True})
        remember("OpenAI", "gpt-5.6", {"reasoning_effort": "medium"})
        assert cached_overrides("OpenAI", "gpt-5.6") == {
            "use_responses_api": True,
            "reasoning_effort": "medium",
        }

    def test_returned_overrides_are_a_copy(self):
        remember("OpenAI", "gpt-5.6", {"use_responses_api": True})
        got = cached_overrides("OpenAI", "gpt-5.6")
        got["mutated"] = True
        assert "mutated" not in cached_overrides("OpenAI", "gpt-5.6")


class TestRemediationDataclass:
    def test_provider_scoping_and_marker_matching(self):
        rem = Remediation(
            name="x",
            markers=("needs-responses",),
            overrides={"use_responses_api": True},
            providers=("OpenAI",),
        )
        assert rem.matches("this NEEDS-RESPONSES now", "OpenAI") is True
        assert rem.matches("this needs-responses now", "Anthropic") is False
        assert rem.matches("unrelated", "OpenAI") is False
