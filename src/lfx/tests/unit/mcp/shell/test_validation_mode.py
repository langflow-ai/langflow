"""Tests for Stage 3 — mode validation."""

from __future__ import annotations

import pytest
from lfx.mcp.shell.shell_config import ShellMode
from lfx.mcp.shell.shell_types import CommandIntent, RejectionReason
from lfx.mcp.shell.validation_mode import validate_mode


@pytest.mark.parametrize(
    "intent",
    [
        CommandIntent.READ_ONLY,
        CommandIntent.WRITE,
        CommandIntent.NETWORK,
        CommandIntent.PROCESS_MANAGEMENT,
        CommandIntent.PACKAGE_MANAGEMENT,
        CommandIntent.SYSTEM_ADMIN,
    ],
)
def test_should_allow_any_intent_in_read_write_mode(intent: CommandIntent):
    result = validate_mode(intent, ShellMode.READ_WRITE)
    assert result.is_ok is True


def test_should_allow_read_only_intent_in_read_only_mode():
    result = validate_mode(CommandIntent.READ_ONLY, ShellMode.READ_ONLY)
    assert result.is_ok is True


@pytest.mark.parametrize(
    "intent",
    [
        CommandIntent.WRITE,
        CommandIntent.DESTRUCTIVE,
        CommandIntent.NETWORK,
        CommandIntent.PROCESS_MANAGEMENT,
        CommandIntent.PACKAGE_MANAGEMENT,
        CommandIntent.SYSTEM_ADMIN,
    ],
)
def test_should_reject_non_read_only_intents_in_read_only_mode(intent: CommandIntent):
    result = validate_mode(intent, ShellMode.READ_ONLY)
    assert result.is_ok is False
    assert result.reason == RejectionReason.MODE_VIOLATION
    assert "read_only" in result.message.lower()


def test_should_reject_unknown_intent_under_fail_closed_default():
    """UNKNOWN classification is fail-closed in V1 (per plan §10 decision 2)."""
    result = validate_mode(CommandIntent.UNKNOWN, ShellMode.READ_WRITE)
    assert result.is_ok is False
    assert result.reason == RejectionReason.UNKNOWN_CLASSIFICATION


def test_should_reject_unknown_intent_in_read_only_too():
    result = validate_mode(CommandIntent.UNKNOWN, ShellMode.READ_ONLY)
    assert result.is_ok is False
    assert result.reason == RejectionReason.UNKNOWN_CLASSIFICATION
