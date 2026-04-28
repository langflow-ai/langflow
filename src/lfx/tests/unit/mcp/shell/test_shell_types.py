"""Tests for shell types — enums and result dataclasses."""

from __future__ import annotations

import dataclasses

import pytest
from lfx.mcp.shell.shell_types import (
    CommandIntent,
    ExecutionResult,
    RejectionReason,
    ValidationResult,
)


class TestCommandIntent:
    def test_should_expose_all_required_categories(self):
        names = {member.name for member in CommandIntent}
        assert names == {
            "READ_ONLY",
            "WRITE",
            "DESTRUCTIVE",
            "NETWORK",
            "PROCESS_MANAGEMENT",
            "PACKAGE_MANAGEMENT",
            "SYSTEM_ADMIN",
            "UNKNOWN",
        }


class TestRejectionReason:
    def test_should_expose_documented_reasons(self):
        names = {member.value for member in RejectionReason}
        assert "destructive_pattern" in names
        assert "mode_violation" in names
        assert "path_traversal" in names
        assert "unknown_classification" in names
        assert "input_too_large" in names


class TestValidationResult:
    def test_should_construct_ok_result(self):
        result = ValidationResult.ok()
        assert result.is_ok is True
        assert result.reason is None
        assert result.message == ""

    def test_should_construct_rejection_with_reason_and_message(self):
        result = ValidationResult.reject(RejectionReason.DESTRUCTIVE_PATTERN, "rm -rf /")
        assert result.is_ok is False
        assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN
        assert "rm -rf /" in result.message

    def test_should_be_immutable(self):
        result = ValidationResult.ok()
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.is_ok = False  # type: ignore[misc]


class TestExecutionResult:
    def test_should_construct_with_required_fields(self):
        result = ExecutionResult(stdout="out", stderr="err", exit_code=0, timed_out=False)
        assert result.stdout == "out"
        assert result.stderr == "err"
        assert result.exit_code == 0
        assert result.timed_out is False

    def test_to_dict_should_omit_rejection_fields_for_normal_result(self):
        result = ExecutionResult(stdout="ok", stderr="", exit_code=0, timed_out=False)
        payload = result.to_dict()
        assert payload == {"stdout": "ok", "stderr": "", "exit_code": 0, "timed_out": False}
        assert "rejected" not in payload
        assert "rejection_reason" not in payload

    def test_to_dict_should_include_rejection_fields_when_rejected(self):
        result = ExecutionResult(
            stdout="",
            stderr="rejected: rm -rf /",
            exit_code=-1,
            timed_out=False,
            rejected=True,
            rejection_reason=RejectionReason.DESTRUCTIVE_PATTERN,
        )
        payload = result.to_dict()
        assert payload["rejected"] is True
        assert payload["rejection_reason"] == "destructive_pattern"
        assert payload["exit_code"] == -1
