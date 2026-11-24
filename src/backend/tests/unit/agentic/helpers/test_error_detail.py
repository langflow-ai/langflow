"""Tests for the structured failure ``detail`` object on the SSE error event.

``build_error_detail`` is additive: the existing ``message`` field of the
error event stays byte-identical, and ``detail`` carries step / component_id /
tool / raw_cause / recommendation for the frontend "Error details" expander.
"""

import json

from langflow.agentic.helpers.error_handling import (
    ERROR_PATTERNS,
    MAX_RAW_CAUSE_LENGTH,
    build_error_detail,
    extract_friendly_error,
    get_error_recommendation,
)
from langflow.agentic.helpers.sse import format_error_event


class TestBuildErrorDetail:
    def test_should_extract_component_id_from_build_wrapper(self):
        raw = "Error building Component OpenAIModel-x1: Error code: 401 - Incorrect API key provided"
        detail = build_error_detail(raw, step="generating_flow", include_raw_cause=True)

        assert detail is not None
        assert detail["step"] == "generating_flow"
        assert detail["component_id"] == "OpenAIModel-x1"
        assert detail["raw_cause"] == raw
        assert detail["recommendation"] == "Check the API key in Settings → Model Providers."

    def test_should_extract_tool_name_when_present(self):
        raw = "Error running graph: tool 'web_search' failed with a connection error"
        detail = build_error_detail(raw)

        assert detail is not None
        assert detail["tool"] == "web_search"
        assert detail["recommendation"] == "Check your network connection and try again."

    def test_should_cap_raw_cause_at_limit(self):
        raw = "x" * (MAX_RAW_CAUSE_LENGTH + 500)
        detail = build_error_detail(raw, include_raw_cause=True)

        assert detail is not None
        assert len(detail["raw_cause"]) == MAX_RAW_CAUSE_LENGTH

    def test_should_map_rate_limit_to_wait_and_retry(self):
        detail = build_error_detail("Error code: 429 - rate limit exceeded for gpt-4")

        assert detail is not None
        assert detail["recommendation"] == "Wait a moment and retry the request."

    def test_should_map_recursion_limit_to_smaller_parts(self):
        detail = build_error_detail("GraphRecursionError: recursion limit of 25 reached")

        assert detail is not None
        assert detail["recommendation"] == "Break the request into smaller parts and try again."

    def test_should_omit_recommendation_for_unknown_errors(self):
        detail = build_error_detail("something entirely unrecognizable happened", include_raw_cause=True)

        assert detail is not None
        assert "recommendation" not in detail
        assert detail["raw_cause"] == "something entirely unrecognizable happened"

    def test_should_omit_component_and_tool_when_not_extractable(self):
        detail = build_error_detail("Request timed out after 60s")

        assert detail is not None
        assert "component_id" not in detail
        assert "tool" not in detail

    def test_should_return_step_only_detail_without_raw_error(self):
        assert build_error_detail(None, step="generating") == {"step": "generating"}

    def test_should_return_none_when_nothing_to_report(self):
        assert build_error_detail(None) is None
        assert build_error_detail("") is None


class TestRawCauseSuperuserGate:
    """SECURITY — ``raw_cause`` is the pre-truncation internal error.

    FlowExecutionError deliberately keeps raw errors out of public HTTP
    detail; the SSE ``detail`` must honor the same invariant. Only a
    superuser (Desktop/AUTO_LOGIN included) may receive ``raw_cause``.
    """

    def test_should_omit_raw_cause_by_default(self):
        raw = "Error building Component Agent-x1: Error code: 401 - Incorrect API key sk-secret"
        detail = build_error_detail(raw, step="generating")

        assert detail is not None
        assert "raw_cause" not in detail
        # Everything non-sensitive stays for everyone.
        assert detail["step"] == "generating"
        assert detail["component_id"] == "Agent-x1"
        assert detail["recommendation"] == "Check the API key in Settings → Model Providers."

    def test_should_include_raw_cause_when_opted_in(self):
        raw = "Error building Component Agent-x1: Error code: 401 - Incorrect API key provided"
        detail = build_error_detail(raw, step="generating", include_raw_cause=True)

        assert detail is not None
        assert detail["raw_cause"] == raw

    def test_should_return_none_for_unattributable_error_without_opt_in(self):
        # No step / component / tool / recommendation and no raw_cause → nothing to report.
        assert build_error_detail("zqx unattributable gibberish") is None


class TestRecommendationCoverage:
    def test_every_error_pattern_category_has_a_recommendation(self):
        for patterns, _message in ERROR_PATTERNS:
            sample = f"failure: {patterns[0]}"
            assert get_error_recommendation(sample) is not None, f"No recommendation for {patterns[0]!r}"

    def test_friendly_messages_are_unchanged_by_the_rules_restructure(self):
        assert extract_friendly_error("Error code: 401 unauthorized") == "Authentication failed. Check your API key."
        assert (
            extract_friendly_error("rate limit exceeded") == "Rate limit exceeded. Please wait a moment and try again."
        )


class TestFormatErrorEventCompatibility:
    def test_should_be_byte_identical_without_detail(self):
        assert format_error_event("boom") == 'data: {"event": "error", "message": "boom"}\n\n'

    def test_should_append_detail_object_when_provided(self):
        event = format_error_event("boom", detail={"step": "generating", "raw_cause": "boom boom"})
        payload = json.loads(event.removeprefix("data: ").strip())

        assert payload["event"] == "error"
        assert payload["message"] == "boom"
        assert payload["detail"] == {"step": "generating", "raw_cause": "boom boom"}

    def test_should_omit_detail_key_for_empty_detail(self):
        assert format_error_event("boom", detail=None) == 'data: {"event": "error", "message": "boom"}\n\n'
        assert format_error_event("boom", detail={}) == 'data: {"event": "error", "message": "boom"}\n\n'
