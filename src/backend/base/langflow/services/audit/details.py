"""The safe ``details`` contract, versioned per resource type.

A producer hands in a mapping and gets back the exact JSON that will be stored,
or an ``AuditContractError``. Unknown keys are rejected rather than persisted, so
no producer can widen what an event carries: no graph, no component setting, no
Flow description, no request body, no exception text.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    ValidationError,
    model_validator,
)

from langflow.services.audit.vocabulary import AuditResourceType, AuditResult
from langflow.services.database.models.audit_event.model import RESOURCE_NAME_MAX_LENGTH

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

SCHEMA_VERSION = 1
FIELD_NAMES_LIMIT = 16
FLOW_CHANGES_LIMIT = 100
_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

COMMITTED_RESULTS = frozenset({AuditResult.SUCCEEDED})
ATTEMPT_RESULTS = frozenset({AuditResult.FAILED, AuditResult.DENY})


class AuditContractError(ValueError):
    """An event that does not satisfy the audit contract; never persisted."""


def field_names(names: Iterable[str]) -> list[str]:
    """Unique, sorted and capped, as the contract requires of every name list."""
    normalized = sorted(set(names))
    invalid = [name for name in normalized if not _FIELD_NAME.fullmatch(name)]
    if invalid:
        msg = f"Not a field name: {invalid[0]!r}"
        raise AuditContractError(msg)
    return normalized[:FIELD_NAMES_LIMIT]


def bounded_name(name: str | None) -> str | None:
    """An event-time name that always fits its column."""
    return None if name is None else name[:RESOURCE_NAME_MAX_LENGTH]


FieldNameList = Annotated[list[str], AfterValidator(field_names)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FlowChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"


_CHANGE_ORDER = {FlowChangeKind.ADDED: 0, FlowChangeKind.REMOVED: 1, FlowChangeKind.UPDATED: 2}


class FlowChange(_Strict):
    id: UUID
    name: str = Field(max_length=RESOURCE_NAME_MAX_LENGTH)
    change: FlowChangeKind


class FlowMembershipSummary(_Strict):
    """Exact membership counts plus a bounded, deterministic identity delta."""

    before_count: NonNegativeInt
    after_count: NonNegativeInt
    updated_count: NonNegativeInt
    changes: list[FlowChange] = Field(max_length=FLOW_CHANGES_LIMIT)
    truncated: bool

    @model_validator(mode="after")
    def _counts_agree(self) -> FlowMembershipSummary:
        if self.updated_count > min(self.before_count, self.after_count):
            msg = "updated_count cannot exceed the smaller membership count"
            raise ValueError(msg)
        expected = {
            FlowChangeKind.ADDED: self.after_count - self.updated_count,
            FlowChangeKind.REMOVED: self.before_count - self.updated_count,
            FlowChangeKind.UPDATED: self.updated_count,
        }
        listed = {kind: sum(1 for entry in self.changes if entry.change is kind) for kind in FlowChangeKind}
        if self.truncated:
            if len(self.changes) != FLOW_CHANGES_LIMIT or any(listed[kind] > expected[kind] for kind in FlowChangeKind):
                msg = "a truncated summary lists exactly the change limit, within the counts"
                raise ValueError(msg)
        elif listed != expected:
            msg = "an untruncated summary must list every change the counts imply"
            raise ValueError(msg)
        return self


def summarize_flow_membership(
    before: Mapping[UUID, str],
    after: Mapping[UUID, str],
) -> FlowMembershipSummary:
    """Classify Flows by identity alone; content is never compared.

    Added and updated Flows carry their post-operation name, removed Flows their
    pre-operation name.
    """
    changes = [
        *(
            FlowChange(id=flow_id, name=bounded_name(name) or "", change=FlowChangeKind.ADDED)
            for flow_id, name in after.items()
            if flow_id not in before
        ),
        *(
            FlowChange(id=flow_id, name=bounded_name(name) or "", change=FlowChangeKind.REMOVED)
            for flow_id, name in before.items()
            if flow_id not in after
        ),
        *(
            FlowChange(id=flow_id, name=bounded_name(name) or "", change=FlowChangeKind.UPDATED)
            for flow_id, name in after.items()
            if flow_id in before
        ),
    ]
    changes.sort(key=lambda entry: (_CHANGE_ORDER[entry.change], str(entry.id)))
    return FlowMembershipSummary(
        before_count=len(before),
        after_count=len(after),
        updated_count=sum(1 for flow_id in after if flow_id in before),
        changes=changes[:FLOW_CHANGES_LIMIT],
        truncated=len(changes) > FLOW_CHANGES_LIMIT,
    )


class ProjectDetailsV1(_Strict):
    schema_version: Literal[1]
    description: str | None = None
    flows: FlowMembershipSummary | None = None
    attempted_fields: FieldNameList | None = None
    requested_flow_count: NonNegativeInt | None = None


class FlowProjectChange(_Strict):
    before_id: UUID | None
    after_id: UUID | None

    @model_validator(mode="after")
    def _is_a_change(self) -> FlowProjectChange:
        if self.before_id == self.after_id:
            msg = "a project change must move the flow"
            raise ValueError(msg)
        return self


class FlowDetailsV1(_Strict):
    schema_version: Literal[1]
    written_fields: FieldNameList | None = None
    project: FlowProjectChange | None = None
    attempted_fields: FieldNameList | None = None


_COMMITTED_KEYS: dict[AuditResourceType, frozenset[str]] = {
    AuditResourceType.PROJECT: frozenset({"description", "flows"}),
    AuditResourceType.FLOW: frozenset({"written_fields", "project"}),
}
_ATTEMPT_KEYS: dict[AuditResourceType, frozenset[str]] = {
    AuditResourceType.PROJECT: frozenset({"attempted_fields", "requested_flow_count"}),
    AuditResourceType.FLOW: frozenset({"attempted_fields"}),
}
_SCHEMAS: dict[tuple[AuditResourceType, int], type[_Strict]] = {
    (AuditResourceType.PROJECT, 1): ProjectDetailsV1,
    (AuditResourceType.FLOW, 1): FlowDetailsV1,
}


def _allowed_keys(resource_type: AuditResourceType, result: AuditResult) -> frozenset[str]:
    if result in COMMITTED_RESULTS:
        return _COMMITTED_KEYS[resource_type]
    if result in ATTEMPT_RESULTS:
        return _ATTEMPT_KEYS[resource_type]
    return frozenset()


def validate_details(
    resource_type: AuditResourceType,
    result: AuditResult,
    details: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the JSON to store, or raise ``AuditContractError``.

    Committed changes appear only on a succeeded event and attempted shape only
    on a failed or denied one, so an attempt can never read as a change.
    """
    version = details.get("schema_version")
    schema = _SCHEMAS.get((resource_type, version)) if type(version) is int else None
    if schema is None:
        msg = f"No details schema {version!r} for resource type {resource_type.value!r}"
        raise AuditContractError(msg)
    try:
        parsed = schema.model_validate(details)
    except ValidationError as exc:
        msg = f"Invalid {resource_type.value} details: {exc.errors()[0]['msg']}"
        raise AuditContractError(msg) from exc
    stored = parsed.model_dump(mode="json", exclude_unset=True)
    unexpected = set(stored) - {"schema_version"} - _allowed_keys(resource_type, result)
    if unexpected:
        msg = f"{sorted(unexpected)} not allowed on a {result.value} {resource_type.value} event"
        raise AuditContractError(msg)
    return stored
