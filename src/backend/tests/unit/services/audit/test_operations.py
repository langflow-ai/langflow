"""Operation bookkeeping: safe failure codes, attempted shape, and one denial per request."""

from __future__ import annotations

import sqlite3
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.audit.operations import (
    UNKNOWN_RESOURCE_ID,
    AuditedOperation,
    classify_failure,
    describe_flow_body,
    describe_project_body,
)
from langflow.services.audit.vocabulary import (
    FLOW_WRITE,
    AuditErrorCode,
    AuditOperation,
    AuditResourceType,
    AuditResult,
)
from langflow.services.database.models.flow.model import FlowUpdate
from langflow.services.database.models.folder.model import FolderCreate
from sqlalchemy.exc import IntegrityError, OperationalError

from .conftest import user_actor

FLOW = AuditResourceType.FLOW
PROJECT = AuditResourceType.PROJECT


def _wrapped(outer: Exception, cause: Exception) -> Exception:
    try:
        try:
            raise cause
        except Exception as inner:
            raise outer from inner
    except Exception as raised:
        return raised


@pytest.mark.parametrize(
    ("exc", "resource_type", "expected"),
    [
        (HTTPException(404, "Flow not found"), FLOW, AuditErrorCode.FLOW_NOT_FOUND),
        (HTTPException(400, "Folder not found"), FLOW, AuditErrorCode.PROJECT_NOT_FOUND),
        (HTTPException(404, "Project not found"), PROJECT, AuditErrorCode.PROJECT_NOT_FOUND),
        (HTTPException(400, "Endpoint name must be unique"), FLOW, AuditErrorCode.FLOW_NAME_CONFLICT),
        (HTTPException(409, "Project name must be unique"), PROJECT, AuditErrorCode.PROJECT_NAME_CONFLICT),
        (HTTPException(422, "Flow(s) with the following IDs already exist: x"), FLOW, AuditErrorCode.FLOW_ID_CONFLICT),
        (HTTPException(400, "No flows found in the data"), PROJECT, AuditErrorCode.INVALID_CONTENT),
        (
            HTTPException(403, "Cannot delete the 'Langflow Assistant' folder"),
            PROJECT,
            AuditErrorCode.CONSTRAINT_VIOLATION,
        ),
        (HTTPException(423, "Flow is locked"), FLOW, AuditErrorCode.CONSTRAINT_VIOLATION),
        (HTTPException(503, "busy"), FLOW, AuditErrorCode.SERVICE_UNAVAILABLE),
        (HTTPException(500, "Could not update the flow."), FLOW, AuditErrorCode.INTERNAL_ERROR),
        (RuntimeError("boom"), FLOW, AuditErrorCode.INTERNAL_ERROR),
    ],
)
def test_failures_map_to_a_safe_code(exc, resource_type, expected):
    assert classify_failure(exc, resource_type) is expected


def test_a_generic_500_is_classified_by_the_database_error_behind_it():
    locked = OperationalError("UPDATE ...", {}, sqlite3.OperationalError("database is locked"))
    violated = IntegrityError("INSERT ...", {}, sqlite3.IntegrityError("CHECK constraint failed"))

    assert (
        classify_failure(_wrapped(HTTPException(500, "The database rejected the request."), locked), PROJECT)
        is AuditErrorCode.SERVICE_UNAVAILABLE
    )
    assert (
        classify_failure(_wrapped(HTTPException(500, "Could not create the flow."), violated), FLOW)
        is AuditErrorCode.CONSTRAINT_VIOLATION
    )


def test_a_client_error_keeps_its_own_code_even_with_a_database_cause():
    violated = IntegrityError("INSERT ...", {}, sqlite3.IntegrityError("UNIQUE constraint failed"))

    exc = _wrapped(HTTPException(409, "Project name must be unique"), violated)

    assert classify_failure(exc, PROJECT) is AuditErrorCode.PROJECT_NAME_CONFLICT


def test_a_failure_without_an_identity_uses_the_unknown_resource_id():
    operation = AuditedOperation(
        resource_type=FLOW, action=FLOW_WRITE, operation=AuditOperation.PATCH, actor=user_actor()
    )

    draft = operation.draft(AuditResult.FAILED, AuditErrorCode.INTERNAL_ERROR)

    assert draft.resource_id == UNKNOWN_RESOURCE_ID
    assert draft.event_type.value == "action"


def test_a_project_body_describes_its_attempted_shape_without_values():
    body = FolderCreate(name="secret-name", description="secret text", flows_list=[uuid4(), uuid4()])

    described = describe_project_body("project")({"project": body})

    assert described["attempted_fields"] == {"name", "description", "flows"}
    assert described["requested_flow_count"] == 2
    assert described["resource_name"] == "secret-name"


def test_a_flow_patch_prefers_the_known_name_over_the_attempted_one():
    loaded = type("Loaded", (), {"name": "current-name"})()

    described = describe_flow_body("flow", loaded_param="db_flow")({"flow": FlowUpdate(name="new"), "db_flow": loaded})

    assert described == {"resource_name": "current-name", "attempted_fields": {"name"}}


def test_a_denial_draft_is_an_authz_event():
    operation = AuditedOperation(
        resource_type=PROJECT,
        action="project:write",
        operation=AuditOperation.PATCH,
        actor=user_actor(),
        resource_id=uuid4(),
        attempted_fields=["description"],
        requested_flow_count=None,
    )

    draft = operation.draft(AuditResult.DENY, AuditErrorCode.PERMISSION_DENIED)

    assert (draft.event_type.value, draft.result.value, draft.error_code) == (
        "authz",
        "deny",
        AuditErrorCode.PERMISSION_DENIED,
    )
    assert draft.details == {"schema_version": 1, "attempted_fields": ["description"]}
