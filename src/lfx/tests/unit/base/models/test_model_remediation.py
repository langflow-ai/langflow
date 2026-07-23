"""Tests for provider-agnostic, error-driven model remediation.

The constraint some models impose (e.g. OpenAI gpt-5.6 rejecting function tools
+ reasoning_effort on /v1/chat/completions) is not exposed by any provider's
model listing, so remediation is matched on the provider's ERROR TEXT and the
winning overrides are remembered per model (discover-once).
"""

import pytest
from lfx.base.models.model_remediation import (
    Remediation,
    cached_overrides,
    find_remediation,
    remember,
    reset_remediation_cache,
)

GPT56_ERROR = (
    "Error building Component Agent: Error code: 400 - {'error': {'message': "
    '"Function tools with reasoning_effort are not supported for gpt-5.6 in '
    "/v1/chat/completions. To use function tools, use /v1/responses or set "
    "reasoning_effort to 'none'.\", 'type': 'invalid_request_error'}}"
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

    def test_should_not_match_for_a_different_provider(self):
        assert find_remediation(GPT56_ERROR, provider="Anthropic", already_applied=set()) is None

    def test_should_not_match_unrelated_errors(self):
        assert find_remediation("rate limit exceeded", provider="OpenAI", already_applied=set()) is None

    def test_should_skip_a_remediation_already_applied(self):
        rem = find_remediation(GPT56_ERROR, provider="OpenAI", already_applied=set())
        assert rem is not None
        assert find_remediation(GPT56_ERROR, provider="OpenAI", already_applied={rem.name}) is None

    def test_matches_is_case_insensitive(self):
        assert find_remediation(GPT56_ERROR.upper(), provider="OpenAI", already_applied=set()) is not None


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
