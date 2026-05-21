"""Unit tests for the CronTrigger component.

Pure instantiation tests — no graph wiring, no DB. Verifies the
component declares the immutable identifier, the expected inputs and
output, and that the two execution paths (manual canvas run vs
worker-injected fire) both produce a tz-aware ISO 8601 string message.
"""

from __future__ import annotations

from datetime import datetime, timezone

from lfx.components.triggers import CronTriggerComponent
from lfx.components.triggers.constants import (
    COMMON_TIMEZONES,
    DEFAULT_CRON_EXPRESSION,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TIMEZONE,
)
from lfx.schema.message import Message


def test_class_identity_is_immutable():
    # ``name`` is persisted in the node id of every saved flow.
    # Pinning the value here makes any accidental rename a test failure.
    assert CronTriggerComponent.name == "CronTrigger"


def test_metadata_for_palette():
    assert CronTriggerComponent.display_name == "Cron Trigger"
    assert CronTriggerComponent.icon == "clock"
    assert "cron" in CronTriggerComponent.description.lower()


def test_inputs_present_with_expected_names():
    component = CronTriggerComponent()
    names = {i.name for i in component.inputs}
    assert names == {"cron_expression", "timezone", "max_attempts", "payload", "fire_time"}


def test_inputs_carry_sensible_defaults():
    component = CronTriggerComponent()
    by_name = {i.name: i for i in component.inputs}
    assert by_name["cron_expression"].value == DEFAULT_CRON_EXPRESSION
    assert by_name["timezone"].value == DEFAULT_TIMEZONE
    assert by_name["max_attempts"].value == DEFAULT_MAX_ATTEMPTS


def test_timezone_dropdown_lists_common_iana_names():
    component = CronTriggerComponent()
    by_name = {i.name: i for i in component.inputs}
    options = by_name["timezone"].options
    # Combobox is true so other zones are allowed; the curated list
    # must at least include UTC and a few well-known regions.
    assert "UTC" in options
    assert "America/Sao_Paulo" in options
    assert "Europe/London" in options
    # The exported tuple should match the dropdown one-to-one.
    assert set(options) == set(COMMON_TIMEZONES)


def test_output_is_single_message_emitter():
    component = CronTriggerComponent()
    assert len(component.outputs) == 1
    only = component.outputs[0]
    assert only.name == "event"
    assert only.method == "build_event"


def test_manual_canvas_run_returns_current_utc():
    """No fire_time → component emits the call instant.

    The exact value is unstable across runs, so we assert it parses
    as ISO 8601 and is recent (within 5 seconds of the test's clock).
    """
    component = CronTriggerComponent()
    before = datetime.now(timezone.utc)
    message = component.build_event()
    after = datetime.now(timezone.utc)
    assert isinstance(message, Message)
    parsed = datetime.fromisoformat(message.text)
    assert before <= parsed <= after
    assert parsed.tzinfo is not None


def test_worker_injection_path_emits_provided_timestamp():
    """Worker-set fire_time → component echoes it verbatim.

    This is the contract relied on by the worker dispatcher: whatever
    tz-aware ISO string the worker writes into the tweak shows up in
    the downstream Message unchanged.
    """
    component = CronTriggerComponent()
    component.fire_time = "2026-05-21T12:34:56+00:00"
    message = component.build_event()
    assert message.text == "2026-05-21T12:34:56+00:00"


def test_status_string_includes_fire_time():
    component = CronTriggerComponent()
    component.fire_time = "2026-05-21T12:34:56+00:00"
    component.build_event()
    assert "2026-05-21T12:34:56+00:00" in str(component.status)


def test_fire_time_whitespace_is_ignored():
    """Defensive: a worker that injects "  ...  " still produces a clean message."""
    component = CronTriggerComponent()
    component.fire_time = "   2026-05-21T12:34:56+00:00   "
    message = component.build_event()
    assert message.text == "2026-05-21T12:34:56+00:00"
