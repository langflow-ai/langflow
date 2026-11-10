"""Which audited actions an operator excluded, and which entries were ignored and why."""

from __future__ import annotations

import pytest
from langflow.services.audit import exclusions
from langflow.services.audit.exclusions import (
    compile_exclusions,
    ignored_exclusion_warnings,
    is_action_audited,
    warn_about_ignored_exclusions,
)
from langflow.services.audit.vocabulary import (
    ACTIONS_BY_RESOURCE_TYPE,
    FLOW_CREATE,
    FLOW_DELETE,
    FLOW_WRITE,
    PROJECT_CREATE,
    PROJECT_DELETE,
    PROJECT_WRITE,
    AuditResourceType,
)


def test_an_exact_action_excludes_only_that_action():
    exclusions = compile_exclusions(["project:delete"])

    assert exclusions.actions == frozenset({PROJECT_DELETE})
    assert exclusions.ignored == ()


def test_a_resource_wildcard_excludes_every_action_on_that_resource():
    exclusions = compile_exclusions(["flow:*"])

    assert FLOW_CREATE in exclusions.actions
    assert exclusions.actions == ACTIONS_BY_RESOURCE_TYPE[AuditResourceType.FLOW]


def test_an_action_wildcard_excludes_that_action_on_every_resource():
    exclusions = compile_exclusions(["*:delete"])

    assert exclusions.actions == frozenset({FLOW_DELETE, PROJECT_DELETE})


def test_entries_combine():
    exclusions = compile_exclusions(["project:create", "flow:write", "project:create"])

    assert exclusions.actions == frozenset({PROJECT_CREATE, FLOW_WRITE})


def test_entries_are_normalized_even_when_they_bypass_settings():
    exclusions = compile_exclusions(["  Project:Delete  ", ""])

    assert exclusions.actions == frozenset({PROJECT_DELETE})
    assert exclusions.ignored == ()


@pytest.mark.parametrize(
    ("entry", "suggestion"),
    [
        ("projects.delete", "project:delete"),
        ("flows.write", "flow:write"),
        ("project.delete", "project:delete"),
        ("flows:*", "flow:*"),
    ],
)
def test_a_near_miss_is_ignored_and_the_right_spelling_is_suggested(entry, suggestion):
    exclusions = compile_exclusions([entry])

    assert exclusions.actions == frozenset()
    [ignored] = exclusions.ignored
    assert ignored.entry == entry
    assert suggestion in ignored.reason


@pytest.mark.parametrize(
    "entry",
    [
        "deployment:delete",
        "flow:read",
        "flow",
        "*:read",
        "flow:execute:now",
        "flow:",
        ":delete",
        "flow delete",
    ],
)
def test_an_entry_that_names_nothing_audited_is_ignored_and_excludes_nothing(entry):
    exclusions = compile_exclusions([entry])

    assert exclusions.actions == frozenset()
    assert [ignored.entry for ignored in exclusions.ignored] == [entry]


@pytest.mark.parametrize("entry", ["*:*", "*"])
def test_excluding_everything_is_refused_in_favour_of_turning_auditing_off(entry):
    exclusions = compile_exclusions([entry])

    assert exclusions.actions == frozenset()
    [ignored] = exclusions.ignored
    assert "LANGFLOW_AUDIT_ENABLED" in ignored.reason


def test_an_ignored_entry_does_not_cancel_the_valid_ones_around_it():
    exclusions = compile_exclusions(["projects.delete", "flow:write", "*:*"])

    assert exclusions.actions == frozenset({FLOW_WRITE})
    assert [ignored.entry for ignored in exclusions.ignored] == ["projects.delete", "*:*"]


def test_the_current_settings_decide_whether_an_action_is_audited(excluded_events):
    excluded_events("project:delete")

    assert is_action_audited(PROJECT_DELETE) is False
    assert is_action_audited(PROJECT_WRITE) is True


def test_a_settings_change_takes_effect_without_a_restart(excluded_events):
    excluded_events("project:delete")
    assert is_action_audited(PROJECT_DELETE) is False

    excluded_events("")

    assert is_action_audited(PROJECT_DELETE) is True


def test_every_action_is_audited_when_nothing_is_excluded(excluded_events):
    excluded_events("")

    assert all(is_action_audited(action) for action in (PROJECT_CREATE, PROJECT_WRITE, FLOW_DELETE))


def test_startup_warnings_name_each_ignored_entry_and_nothing_else(excluded_events):
    excluded_events("projects.delete,flow:write,*:*")

    warnings = ignored_exclusion_warnings()

    assert len(warnings) == 2
    assert "projects.delete" in warnings[0]
    assert "project:delete" in warnings[0]
    assert "*:*" in warnings[1]


def test_no_warning_when_every_entry_is_valid(excluded_events):
    excluded_events("flow:*,*:delete")

    assert ignored_exclusion_warnings() == []


@pytest.fixture
def captured_warnings(monkeypatch) -> list[str]:
    captured: list[str] = []

    async def capture(message: str, *args: object) -> None:
        captured.append(message % args if args else message)

    monkeypatch.setattr(exclusions.logger, "awarning", capture)
    return captured


@pytest.mark.usefixtures("audit_enabled")
async def test_startup_logs_one_warning_per_ignored_entry(excluded_events, captured_warnings):
    excluded_events("projects.delete,flow:write,deployment:delete")

    await warn_about_ignored_exclusions()

    assert len(captured_warnings) == 2
    assert "projects.delete" in captured_warnings[0]
    assert "deployment:delete" in captured_warnings[1]


@pytest.mark.usefixtures("audit_disabled")
async def test_startup_stays_quiet_when_auditing_is_off(excluded_events, captured_warnings):
    excluded_events("projects.delete")

    await warn_about_ignored_exclusions()

    assert captured_warnings == []


@pytest.mark.usefixtures("audit_enabled")
async def test_startup_never_fails_on_the_exclusion_check(monkeypatch, captured_warnings):
    def broken() -> list[str]:
        msg = "settings unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr(exclusions, "ignored_exclusion_warnings", broken)

    await warn_about_ignored_exclusions()

    assert captured_warnings == ["op=warn_about_ignored_exclusions outcome=failed error=RuntimeError"]
