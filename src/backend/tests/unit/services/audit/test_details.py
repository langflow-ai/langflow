"""The safe details contract: what an event may carry, and what it never can."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from langflow.services.audit.details import (
    FIELD_NAMES_LIMIT,
    FLOW_CHANGES_LIMIT,
    AuditContractError,
    field_names,
    summarize_flow_membership,
    validate_details,
)
from langflow.services.audit.vocabulary import AuditResourceType, AuditResult

PROJECT = AuditResourceType.PROJECT
FLOW = AuditResourceType.FLOW


def _ids(count: int) -> list[UUID]:
    return sorted((uuid4() for _ in range(count)), key=str)


def test_description_written_as_null_is_kept_distinct_from_a_description_not_written():
    written_null = validate_details(PROJECT, AuditResult.SUCCEEDED, {"schema_version": 1, "description": None})
    not_written = validate_details(PROJECT, AuditResult.SUCCEEDED, {"schema_version": 1})

    assert written_null == {"schema_version": 1, "description": None}
    assert not_written == {"schema_version": 1}


def test_description_is_stored_complete_rather_than_truncated():
    description = "x" * 10_000

    stored = validate_details(PROJECT, AuditResult.SUCCEEDED, {"schema_version": 1, "description": description})

    assert stored["description"] == description


@pytest.mark.parametrize(
    "details",
    [
        {"schema_version": 1, "graph": {"nodes": []}},
        {"schema_version": 1, "request_body": "{}"},
        {"schema_version": 1, "error": "Traceback (most recent call last)"},
        {
            "schema_version": 1,
            "flows": {
                "before_count": 0,
                "after_count": 0,
                "updated_count": 0,
                "changes": [],
                "truncated": False,
                "data": {},
            },
        },
    ],
)
def test_unknown_keys_are_rejected_rather_than_persisted(details):
    with pytest.raises(AuditContractError):
        validate_details(PROJECT, AuditResult.SUCCEEDED, details)


@pytest.mark.parametrize("version", [None, 0, 2, "1", True])
def test_an_unknown_schema_version_is_rejected(version):
    with pytest.raises(AuditContractError):
        validate_details(PROJECT, AuditResult.SUCCEEDED, {"schema_version": version})


def test_a_failed_event_cannot_claim_committed_changes():
    with pytest.raises(AuditContractError, match="not allowed on a failed"):
        validate_details(PROJECT, AuditResult.FAILED, {"schema_version": 1, "description": "attempted text"})


def test_a_succeeded_event_cannot_carry_attempted_shape():
    with pytest.raises(AuditContractError, match="not allowed on a succeeded"):
        validate_details(PROJECT, AuditResult.SUCCEEDED, {"schema_version": 1, "attempted_fields": ["name"]})


def test_a_denial_keeps_only_the_attempted_shape():
    stored = validate_details(
        PROJECT,
        AuditResult.DENY,
        {"schema_version": 1, "attempted_fields": ["flows", "description", "flows"], "requested_flow_count": 3},
    )

    assert stored == {"schema_version": 1, "attempted_fields": ["description", "flows"], "requested_flow_count": 3}


def test_field_names_are_unique_sorted_and_capped():
    names = [f"field_{index:02d}" for index in reversed(range(40))] * 2

    normalized = field_names(names)

    assert normalized == sorted(set(names))[:FIELD_NAMES_LIMIT]


@pytest.mark.parametrize("name", ["Name", "sk-live-123", "a b", "", "x" * 65, "1st"])
def test_a_value_cannot_pass_as_a_field_name(name):
    with pytest.raises(AuditContractError):
        field_names([name])


def test_membership_is_classified_by_identity_and_ordered_deterministically():
    kept, removed, added = _ids(2), _ids(1), _ids(1)
    before = {flow_id: f"old-{index}" for index, flow_id in enumerate([*kept, *removed])}
    after = {flow_id: f"new-{index}" for index, flow_id in enumerate([*kept, *added])}

    summary = summarize_flow_membership(before, after)

    assert (summary.before_count, summary.after_count, summary.updated_count) == (3, 3, 2)
    assert [entry.change.value for entry in summary.changes] == ["added", "removed", "updated", "updated"]
    assert summary.changes[1].name == "old-2"
    assert summary.changes[2].name.startswith("new-")
    assert summary.truncated is False


def test_counts_stay_exact_when_the_change_list_is_truncated():
    before = dict.fromkeys(_ids(80), "old")
    after = dict.fromkeys(_ids(90), "new")

    summary = summarize_flow_membership(before, after)

    assert summary.truncated is True
    assert len(summary.changes) == FLOW_CHANGES_LIMIT
    assert (summary.before_count, summary.after_count, summary.updated_count) == (80, 90, 0)


def test_exactly_the_change_limit_is_not_reported_as_truncated():
    summary = summarize_flow_membership({}, dict.fromkeys(_ids(FLOW_CHANGES_LIMIT), "new"))

    assert summary.truncated is False
    assert len(summary.changes) == FLOW_CHANGES_LIMIT


def test_a_hand_built_summary_whose_counts_disagree_is_rejected():
    flow_id = uuid4()
    lying = {
        "schema_version": 1,
        "flows": {
            "before_count": 0,
            "after_count": 5,
            "updated_count": 0,
            "changes": [{"id": str(flow_id), "name": "one", "change": "added"}],
            "truncated": False,
        },
    }

    with pytest.raises(AuditContractError):
        validate_details(PROJECT, AuditResult.SUCCEEDED, lying)


def test_an_overlong_flow_name_is_bounded_in_the_summary():
    summary = summarize_flow_membership({}, {uuid4(): "n" * 1000})

    assert len(summary.changes[0].name) == 255


def test_flow_details_record_a_move_between_projects():
    source, target = uuid4(), uuid4()

    stored = validate_details(
        FLOW,
        AuditResult.SUCCEEDED,
        {
            "schema_version": 1,
            "written_fields": ["folder_id", "data"],
            "project": {"before_id": source, "after_id": target},
        },
    )

    assert stored["written_fields"] == ["data", "folder_id"]
    assert stored["project"] == {"before_id": str(source), "after_id": str(target)}


def test_a_flow_project_change_must_actually_move_the_flow():
    same = uuid4()
    with pytest.raises(AuditContractError):
        validate_details(
            FLOW, AuditResult.SUCCEEDED, {"schema_version": 1, "project": {"before_id": same, "after_id": same}}
        )


def test_flow_details_never_accept_a_description():
    with pytest.raises(AuditContractError):
        validate_details(FLOW, AuditResult.SUCCEEDED, {"schema_version": 1, "description": "secret plan"})
