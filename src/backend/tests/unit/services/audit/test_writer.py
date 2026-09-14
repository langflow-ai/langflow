"""Creating events: validation, same-transaction staging, and attribution."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from langflow.services.audit.attribution import (
    AuditActor,
    AuditRequestContextMiddleware,
    current_request_id,
    resolve_audit_actor,
)
from langflow.services.audit.details import AuditContractError
from langflow.services.audit.vocabulary import (
    FLOW_WRITE,
    PROJECT_DELETE,
    AuditActorType,
    AuditErrorCode,
    AuditEventType,
    AuditOperation,
    AuditResult,
)
from langflow.services.audit.writer import build_audit_event, stage_audit_event
from langflow.services.auth.context import AuthCredentialContext, clear_current_auth_context, set_current_auth_context
from langflow.services.database.models.audit_event.model import AuditEvent
from lfx.services.session import NoopSession
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from .conftest import project_patch_draft, user_actor


async def _stored(session) -> list[AuditEvent]:
    return list((await session.exec(select(AuditEvent))).all())


async def test_a_staged_event_commits_with_the_mutation(audit_session, audit_enabled):  # noqa: ARG001
    before = datetime.now(timezone.utc)

    staged = stage_audit_event(audit_session, project_patch_draft())
    await audit_session.commit()

    [row] = await _stored(audit_session)
    assert row.id == staged.id
    assert row.details == {"schema_version": 1, "description": "Routes customer questions"}
    assert row.request_id is not None
    assert row.timestamp.replace(tzinfo=timezone.utc) >= before.replace(microsecond=0)


async def test_a_staged_event_disappears_when_the_mutation_rolls_back(audit_session, audit_enabled):  # noqa: ARG001
    stage_audit_event(audit_session, project_patch_draft())
    await audit_session.rollback()

    assert await _stored(audit_session) == []


async def test_nothing_is_staged_when_auditing_is_off(audit_session, audit_disabled):  # noqa: ARG001
    assert stage_audit_event(audit_session, project_patch_draft()) is None
    await audit_session.commit()

    assert await _stored(audit_session) == []


def test_a_stateless_runtime_stages_nothing_and_does_not_raise(audit_enabled):  # noqa: ARG001
    assert stage_audit_event(NoopSession(), project_patch_draft()) is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"event_type": AuditEventType.AUTHZ, "result": AuditResult.SUCCEEDED}, "not a result"),
        ({"event_type": AuditEventType.ACTION, "result": AuditResult.DENY}, "not a result"),
        ({"action": FLOW_WRITE}, "not an action on"),
        ({"action": "project:read"}, "not an action on"),
        ({"result": AuditResult.FAILED, "details": {"schema_version": 1}}, "error_code is required"),
        ({"error_code": AuditErrorCode.INTERNAL_ERROR}, "error_code is required"),
    ],
)
def test_a_draft_that_breaks_the_contract_is_refused(overrides, message):
    with pytest.raises(AuditContractError, match=message):
        build_audit_event(project_patch_draft(**overrides))


def test_an_overlong_resource_name_is_bounded_instead_of_failing_the_write():
    event = build_audit_event(project_patch_draft(resource_name="p" * 400))

    assert len(event.resource_name) == 255


def test_a_denial_is_built_with_its_error_code():
    event = build_audit_event(
        project_patch_draft(
            action=PROJECT_DELETE,
            operation=AuditOperation.DELETE,
            event_type=AuditEventType.AUTHZ,
            result=AuditResult.DENY,
            error_code=AuditErrorCode.PERMISSION_DENIED,
            details={"schema_version": 1, "attempted_fields": []},
        )
    )

    assert (event.event_type, event.result, event.error_code) == ("authz", "deny", "PERMISSION_DENIED")


@pytest.mark.parametrize(
    ("event_type", "result"),
    [("authz", "succeeded"), ("action", "allow"), ("action", "deny"), ("authz", "failed"), ("action", "maybe")],
)
async def test_the_database_refuses_an_impossible_type_and_result(audit_session, event_type, result):
    row = build_audit_event(project_patch_draft())
    row.event_type, row.result = event_type, result
    audit_session.add(row)

    with pytest.raises(IntegrityError):
        await audit_session.commit()


@pytest.mark.parametrize(("issuer", "subject"), [("https://idp.example", None), (None, "alice")])
async def test_the_database_refuses_half_an_acting_identity(audit_session, issuer, subject):
    row = build_audit_event(project_patch_draft())
    row.acting_issuer, row.acting_subject = issuer, subject
    audit_session.add(row)

    with pytest.raises(IntegrityError):
        await audit_session.commit()


def test_an_acting_identity_must_be_complete_and_bounded():
    with pytest.raises(AuditContractError):
        AuditActor(user_id=uuid4(), actor_type=AuditActorType.API_KEY, actor_id=uuid4(), acting_subject="alice")
    with pytest.raises(AuditContractError):
        AuditActor(
            user_id=uuid4(),
            actor_type=AuditActorType.API_KEY,
            actor_id=uuid4(),
            acting_issuer="https://idp.example",
            acting_subject="s" * 513,
        )


async def test_a_non_uuid_jwt_subject_is_stored(audit_session, audit_enabled):  # noqa: ARG001
    actor = AuditActor(
        user_id=uuid4(),
        actor_type=AuditActorType.API_KEY,
        actor_id=uuid4(),
        acting_issuer="https://idp.example/realms/acme",
        acting_subject="auth0|65f2c9e1b7",
    )
    stage_audit_event(audit_session, project_patch_draft(actor=actor))
    await audit_session.commit()

    [row] = await _stored(audit_session)
    assert (row.acting_issuer, row.acting_subject) == ("https://idp.example/realms/acme", "auth0|65f2c9e1b7")


def test_an_api_key_request_is_attributed_to_the_key_under_its_account():
    user_id, key_id = uuid4(), uuid4()
    set_current_auth_context(AuthCredentialContext(method="api_key", api_key_id=key_id))
    try:
        actor = resolve_audit_actor(user_id)
    finally:
        clear_current_auth_context()

    assert (actor.user_id, actor.actor_type, actor.actor_id) == (user_id, AuditActorType.API_KEY, key_id)


def test_a_session_request_is_attributed_to_the_user():
    user_id = uuid4()
    set_current_auth_context(AuthCredentialContext(method="jwt"))
    try:
        actor = resolve_audit_actor(user_id)
    finally:
        clear_current_auth_context()

    assert actor == user_actor(user_id)


def test_a_request_without_a_user_is_attributed_to_unknown():
    actor = resolve_audit_actor(None)

    assert (actor.user_id, actor.actor_type, actor.actor_id) == (None, AuditActorType.UNKNOWN, None)


async def test_every_request_gets_its_own_correlation_id_shared_by_its_events():
    async def read_in_child_task() -> UUID:
        await asyncio.sleep(0)
        return current_request_id()

    async def endpoint(_request):
        first = current_request_id()
        nested = await asyncio.create_task(read_in_child_task())
        return JSONResponse({"first": str(first), "nested": str(nested)})

    app = AuditRequestContextMiddleware(Starlette(routes=[Route("/", endpoint)]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(*(client.get("/") for _ in range(20)))

    bodies = [response.json() for response in responses]
    assert all(body["first"] == body["nested"] for body in bodies)
    assert len({body["first"] for body in bodies}) == 20
    assert all(UUID(body["first"]) for body in bodies)


def test_work_outside_a_request_never_reuses_a_correlation_id():
    assert current_request_id() != current_request_id()
