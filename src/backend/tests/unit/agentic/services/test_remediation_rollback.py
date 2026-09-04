"""A remediation override must not survive a retry that still failed.

``remember`` writes into a PROCESS-GLOBAL cache that ``get_llm`` pre-applies to every
later request for that model. Writing it before the retry proves the fix works means a
remediation that did NOT fix anything silently poisons the model for the whole process.
The override is therefore provisional: promoted on success, rolled back on failure.
"""

import pytest
from langflow.agentic.services.flow_types import FlowExecutionError
from lfx.base.models.model_remediation import (
    cached_overrides,
    find_remediation,
    remember,
    reset_remediation_cache,
    restore_overrides,
)

_RESPONSES_API_ERROR = (
    "Error code: 400 - Function tools with reasoning_effort are not supported for gpt-5.6 "
    "in /v1/chat/completions. To use function tools, use /v1/responses."
)


@pytest.fixture(autouse=True)
def _clean_cache():
    reset_remediation_cache()
    yield
    reset_remediation_cache()


def test_the_gpt_56_error_is_recognized():
    remediation = find_remediation(_RESPONSES_API_ERROR, "OpenAI", already_applied=set())

    assert remediation is not None
    assert remediation.overrides.get("use_responses_api") is True


def test_rollback_undoes_a_provisional_override_on_a_failed_retry():
    """The reviewer's repro: recognized error, remediation applied, retry STILL fails."""
    snapshot = cached_overrides("OpenAI", "gpt-5.6")
    assert snapshot == {}, "precondition: nothing remembered yet"

    remediation = find_remediation(_RESPONSES_API_ERROR, "OpenAI", already_applied=set())
    remember("OpenAI", "gpt-5.6", remediation.overrides)
    assert cached_overrides("OpenAI", "gpt-5.6") == {"use_responses_api": True}

    # The retried run fails anyway -> the turn gives up and must not leave the bet behind.
    restore_overrides("OpenAI", "gpt-5.6", snapshot)

    assert cached_overrides("OpenAI", "gpt-5.6") == {}, (
        "a remediation that did not fix the run must not persist into later requests"
    )


def test_rollback_restores_a_previously_remembered_override_rather_than_dropping_it():
    """A model that already had a working override keeps it when a NEW bet fails."""
    remember("OpenAI", "gpt-5.6", {"use_responses_api": True})
    snapshot = cached_overrides("OpenAI", "gpt-5.6")

    remember("OpenAI", "gpt-5.6", {"some_new_guess": "value"})
    restore_overrides("OpenAI", "gpt-5.6", snapshot)

    assert cached_overrides("OpenAI", "gpt-5.6") == {"use_responses_api": True}


def test_a_successful_retry_keeps_the_override():
    """Promotion path: nothing rolls back, so the fix is remembered for later requests."""
    remediation = find_remediation(_RESPONSES_API_ERROR, "OpenAI", already_applied=set())
    remember("OpenAI", "gpt-5.6", remediation.overrides)

    # success => the caller simply drops the provisional record (no restore call)

    assert cached_overrides("OpenAI", "gpt-5.6") == {"use_responses_api": True}


def test_rollback_is_scoped_to_the_model_it_was_written_for():
    remember("OpenAI", "gpt-5.5", {"use_responses_api": True})
    snapshot_56 = cached_overrides("OpenAI", "gpt-5.6")
    remember("OpenAI", "gpt-5.6", {"use_responses_api": True})

    restore_overrides("OpenAI", "gpt-5.6", snapshot_56)

    assert cached_overrides("OpenAI", "gpt-5.6") == {}
    assert cached_overrides("OpenAI", "gpt-5.5") == {"use_responses_api": True}


def test_flow_execution_error_exposes_the_raw_message_the_matcher_needs():
    error = FlowExecutionError(_RESPONSES_API_ERROR)

    assert find_remediation(error.original_error_message, "OpenAI", already_applied=set()) is not None
