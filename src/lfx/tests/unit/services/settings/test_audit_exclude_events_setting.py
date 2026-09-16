"""LANGFLOW_AUDIT_EXCLUDE_EVENTS: parsed from a comma-separated env var into normalized entries."""

from __future__ import annotations

import pytest
from lfx.services.settings.base import Settings


def test_nothing_is_excluded_by_default(monkeypatch):
    monkeypatch.delenv("LANGFLOW_AUDIT_EXCLUDE_EVENTS", raising=False)

    assert Settings().audit_exclude_events == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("flow:execute", ["flow:execute"]),
        ("flow:execute,project:delete", ["flow:execute", "project:delete"]),
        (" flow:execute ,  project:delete ", ["flow:execute", "project:delete"]),
        ("Flow:Execute,PROJECT:*", ["flow:execute", "project:*"]),
        ("flow:execute,,project:delete,", ["flow:execute", "project:delete"]),
        ("flow:execute,flow:execute,FLOW:EXECUTE", ["flow:execute"]),
        ("", []),
        (" , ,", []),
    ],
)
def test_the_env_var_is_split_trimmed_lowercased_and_deduplicated(monkeypatch, raw, expected):
    monkeypatch.setenv("LANGFLOW_AUDIT_EXCLUDE_EVENTS", raw)

    assert Settings().audit_exclude_events == expected


def test_an_unrecognized_entry_is_kept_for_the_application_to_report(monkeypatch):
    monkeypatch.setenv("LANGFLOW_AUDIT_EXCLUDE_EVENTS", "flows.execute")

    assert Settings().audit_exclude_events == ["flows.execute"]


def test_assigning_a_string_at_runtime_is_normalized_the_same_way(monkeypatch):
    monkeypatch.delenv("LANGFLOW_AUDIT_EXCLUDE_EVENTS", raising=False)
    settings = Settings()

    settings.audit_exclude_events = " Project:Write , flow:delete"

    assert settings.audit_exclude_events == ["project:write", "flow:delete"]
