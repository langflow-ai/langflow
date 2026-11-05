"""Trigger errors carry stable codes so the UI can show them in the reader's language."""

from __future__ import annotations

import pytest
from langflow.services.triggers.constants import CONNECTION_NOT_AUTHORIZED_ERROR
from langflow.services.triggers.error_codes import (
    CRON_NEVER_MATCHES_ERROR,
    INVALID_CRON_ERROR,
    NODE_REMOVED_ERROR,
    SOURCE_SETTINGS_CHANGED_ERROR,
    TIMEZONE_REQUIRED_ERROR,
    UNKNOWN_TIMEZONE_ERROR,
    CodedTriggerError,
    TriggerErrorCode,
    last_error_code,
    refusal_detail,
)
from langflow.services.triggers.providers.slack.arming import SlackTriggerArmingError
from langflow.services.triggers.reconciliation import validate_single_trigger_per_flow
from langflow.services.triggers.schedule_config import InvalidScheduleError, validate_schedule_config


@pytest.mark.parametrize(
    ("stored", "code"),
    [
        (NODE_REMOVED_ERROR, "node_removed"),
        (SOURCE_SETTINGS_CHANGED_ERROR, "source_settings_changed"),
        (CONNECTION_NOT_AUTHORIZED_ERROR, "connection_not_authorized"),
        (INVALID_CRON_ERROR, "invalid_cron"),
        (CRON_NEVER_MATCHES_ERROR, "cron_never_matches"),
        (TIMEZONE_REQUIRED_ERROR, "timezone_required"),
        (UNKNOWN_TIMEZONE_ERROR, "unknown_timezone"),
    ],
)
def test_a_stored_error_the_server_writes_has_a_code(stored: str, code: str) -> None:
    assert last_error_code(stored) == code


@pytest.mark.parametrize(
    "stored",
    [
        None,
        "",
        "Provider returned 502",
        f"An administrator resumed this trigger, but it could not start: {INVALID_CRON_ERROR}",
    ],
)
def test_text_only_a_person_can_read_has_no_code(stored: str | None) -> None:
    assert last_error_code(stored) is None


@pytest.mark.parametrize(
    ("config", "code"),
    [
        ({"cron": "61 * * * *"}, "invalid_cron"),
        ({"cron": "0 0 31 2 *"}, "cron_never_matches"),
        ({"cron": "0 3 * * *", "timezone": " "}, "timezone_required"),
        ({"cron": "0 3 * * *", "timezone": "Mars/Olympus"}, "unknown_timezone"),
    ],
)
def test_schedule_validation_errors_are_the_coded_strings(config: dict, code: str) -> None:
    with pytest.raises(InvalidScheduleError) as raised:
        validate_schedule_config(config)

    assert refusal_detail(raised.value) == {"code": code, "message": str(raised.value)}


def test_a_refusal_keeps_its_own_code_and_its_english_message() -> None:
    error = CodedTriggerError(TriggerErrorCode.BACKGROUND_RUNS_NOT_ALLOWED, "Turn on Allow background runs.")

    assert refusal_detail(error) == {"code": "background_runs_not_allowed", "message": "Turn on Allow background runs."}


def test_an_uncoded_refusal_says_so() -> None:
    assert refusal_detail(ValueError("The trigger no longer exists.")) == {
        "code": None,
        "message": "The trigger no longer exists.",
    }


def test_multiple_canvas_triggers_have_a_translatable_refusal() -> None:
    graph = {"nodes": [{"data": {"type": "ScheduleTrigger"}}, {"data": {"type": "InboundWebhookTrigger"}}]}
    with pytest.raises(ValueError, match="only one trigger") as raised:
        validate_single_trigger_per_flow(graph)

    assert refusal_detail(raised.value) == {
        "code": "multiple_triggers",
        "message": "A flow can have only one trigger. Remove the extra triggers and try again.",
    }


def test_a_slack_arming_error_is_coded_only_when_the_ui_can_translate_it() -> None:
    assert (
        SlackTriggerArmingError("x", code=TriggerErrorCode.BACKGROUND_RUNS_NOT_ALLOWED).code
        == "background_runs_not_allowed"
    )
    assert SlackTriggerArmingError("x").code is None
