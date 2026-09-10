"""CRUD API for authz_role_assignment rows.

Assignments bind a user to a role within an optional domain. The actual policy
compilation (rule rows in the policy-rule table) is performed by the
authorization plugin — OSS keeps the assignment table and invalidates the
plugin's cache on write so the next ``enforce()`` picks up the change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from lfx.log.logger import logger
from lfx.services.authorization import (
    AuthorizationMutation,
    AuthorizationMutationKind,
    AuthorizationMutationRejected,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.authz_role_assignments import (
    RoleAssignmentCreate,
    RoleAssignmentGrantSummary,
    RoleAssignmentRead,
)
from langflow.services.authorization.audit import AUDIT_EVENT_ACCESS, AUDIT_EVENT_MUTATION
from langflow.services.authorization.lifecycle import (
    acquire_identity_mutation_lock,
    safe_identity_mutation_committed,
    stage_identity_mutation,
    validate_identity_mutation,
)
from langflow.services.authorization.utils import audit_decision
from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment, AuthzRoleAssignmentGrant
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/role-assignments", tags=["Authorization"], include_in_schema=False)

# See ``authz_roles._LIST_MAX_LIMIT`` — same bound, applied to assignments.
_LIST_MAX_LIMIT = 200
_LIST_DEFAULT_LIMIT = 100


async def _audit_deny(*, user_id: UUID, action: str, obj: str, status_code: int, reason: str) -> None:
    await audit_decision(
        user_id=user_id,
        action=action,
        obj=obj,
        result="deny",
        details={"event": AUDIT_EVENT_ACCESS, "status_code": status_code, "reason": reason},
    )


async def _require_superuser(user, *, action: str, obj: str) -> None:
    if not getattr(user, "is_superuser", False):
        await _audit_deny(
            user_id=user.id,
            action=action,
            obj=obj,
            status_code=status.HTTP_403_FORBIDDEN,
            reason="superuser_required",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser required to administer role assignments.",
        )


async def _require_superuser_dependency(request: Request, current_user: CurrentActiveUser) -> None:
    """Run the superuser gate as a route dependency, i.e. before body validation.

    FastAPI solves a route's ``dependencies`` before validating that route's own
    body, so an unauthorised caller is refused whatever they post. Gated only in
    the endpoint body, they first receive the same 422 field names and enum
    values a superuser would, which lets them map the request contract of a
    route they cannot invoke.

    The in-body call is kept as well: it is the gate for anything that reaches
    the endpoint function without FastAPI resolving dependencies.
    """
    assignment_id = request.path_params.get("assignment_id", "*")
    action = "role_assignment:create" if request.method == "POST" else "role_assignment:delete"
    await _require_superuser(current_user, action=action, obj=f"role_assignment:{assignment_id}")


SUPERUSER_ONLY = [Depends(_require_superuser_dependency)]


async def _assignment_reads(session, assignments: list[AuthzRoleAssignment]) -> list[RoleAssignmentRead]:
    """Serialize effective assignments with source summaries in two queries."""
    if not assignments:
        return []
    assignment_ids = [assignment.id for assignment in assignments]
    grants = (
        await session.exec(
            select(AuthzRoleAssignmentGrant)
            .where(AuthzRoleAssignmentGrant.assignment_id.in_(assignment_ids))
            .order_by(
                AuthzRoleAssignmentGrant.assignment_id,
                AuthzRoleAssignmentGrant.source_kind,
                AuthzRoleAssignmentGrant.provider_id,
                AuthzRoleAssignmentGrant.external_group,
            )
        )
    ).all()
    grants_by_assignment: dict[UUID, list[RoleAssignmentGrantSummary]] = {}
    for grant in grants:
        grants_by_assignment.setdefault(grant.assignment_id, []).append(
            RoleAssignmentGrantSummary.model_validate(grant)
        )
    return [
        RoleAssignmentRead.model_validate(assignment).model_copy(
            update={"grant_sources": grants_by_assignment.get(assignment.id, [])}
        )
        for assignment in assignments
    ]


def _assignment_match(payload: RoleAssignmentCreate):
    domain_match = (
        AuthzRoleAssignment.domain_id.is_(None)
        if payload.domain_id is None
        else AuthzRoleAssignment.domain_id == payload.domain_id
    )
    return (
        AuthzRoleAssignment.user_id == payload.user_id,
        AuthzRoleAssignment.role_id == payload.role_id,
        AuthzRoleAssignment.domain_type == payload.domain_type,
        domain_match,
    )


@router.get("", response_model=list[RoleAssignmentRead])
@router.get("/", response_model=list[RoleAssignmentRead])
async def list_assignments(
    session: DbSession,
    current_user: CurrentActiveUser,
    user_id: Annotated[UUID | None, Query(description="Filter by user")] = None,
    role_id: Annotated[UUID | None, Query(description="Filter by role")] = None,
    domain_type: Annotated[str | None, Query()] = None,
    domain_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_LIST_MAX_LIMIT)] = _LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RoleAssignmentRead]:
    """List role assignments scoped to one user.

    * Omitting ``user_id`` defaults to the caller — no superuser needed.
    * Passing ``user_id == self.id`` is the same as omitting it.
    * Passing a different ``user_id`` requires superuser; otherwise 403.

    Results are always filtered by the resolved ``user_id``. Admins who need
    cross-user lookups make one call per user. Paginated via ``limit`` /
    ``offset`` (default 100, max 200).
    """
    if user_id is None:
        user_id = current_user.id
    elif user_id != current_user.id:
        await _require_superuser(
            current_user,
            action="role_assignment:read",
            obj=f"user:{user_id}",
        )
    stmt = select(AuthzRoleAssignment).where(AuthzRoleAssignment.user_id == user_id)
    if role_id is not None:
        stmt = stmt.where(AuthzRoleAssignment.role_id == role_id)
    if domain_type is not None:
        stmt = stmt.where(AuthzRoleAssignment.domain_type == domain_type)
    if domain_id is not None:
        stmt = stmt.where(AuthzRoleAssignment.domain_id == domain_id)
    stmt = stmt.order_by(AuthzRoleAssignment.assigned_at.desc(), AuthzRoleAssignment.id).offset(offset).limit(limit)
    rows = (await session.exec(stmt)).all()
    return await _assignment_reads(session, list(rows))


@router.post("", response_model=RoleAssignmentRead, status_code=status.HTTP_201_CREATED, dependencies=SUPERUSER_ONLY)
@router.post("/", response_model=RoleAssignmentRead, status_code=status.HTTP_201_CREATED, dependencies=SUPERUSER_ONLY)
async def create_assignment(
    payload: RoleAssignmentCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> RoleAssignmentRead:
    """Assign a role to a user. Superuser-only."""
    await _require_superuser(current_user, action="role_assignment:create", obj="role_assignment:*")
    authorization_service = get_authorization_service()
    # Let authorization plugins acquire their transaction-scoped policy-write
    # lock before the first canonical identity read or write. An external
    # compiler may need the same global lock later while staging derived policy.
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.ROLE_ASSIGNMENT_CREATED,
        affected_user_ids=(payload.user_id,),
    )

    user = await session.get(User, payload.user_id)
    if user is None:
        await _audit_deny(
            user_id=current_user.id,
            action="role_assignment:create",
            obj="role_assignment:*",
            status_code=status.HTTP_404_NOT_FOUND,
            reason="user_not_found",
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_id not found")
    role = await session.get(AuthzRole, payload.role_id)
    if role is None:
        await _audit_deny(
            user_id=current_user.id,
            action="role_assignment:create",
            obj="role_assignment:*",
            status_code=status.HTTP_404_NOT_FOUND,
            reason="role_not_found",
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="role_id not found")

    candidate = AuthzRoleAssignment(
        user_id=payload.user_id,
        role_id=payload.role_id,
        domain_type=payload.domain_type,
        domain_id=payload.domain_id,
        assigned_at=datetime.now(timezone.utc),
        assigned_by=current_user.id,
    )
    assignment = (await session.exec(select(AuthzRoleAssignment).where(*_assignment_match(payload)))).first()
    effective_assignment_created = assignment is None
    if assignment is None:
        assignment = candidate
        session.add(assignment)
        await session.flush()
    else:
        existing_manual = (
            await session.exec(
                select(AuthzRoleAssignmentGrant).where(
                    AuthzRoleAssignmentGrant.assignment_id == assignment.id,
                    AuthzRoleAssignmentGrant.source_kind == "manual",
                )
            )
        ).first()
        if existing_manual is not None:
            await _audit_deny(
                user_id=current_user.id,
                action="role_assignment:create",
                obj="role_assignment:*",
                status_code=status.HTTP_409_CONFLICT,
                reason="manual_assignment_already_exists",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Manual assignment already exists for this user/role/domain",
            )

    session.add(
        AuthzRoleAssignmentGrant(
            assignment_id=assignment.id,
            source_kind="manual",
            administrative_actor=current_user.id,
        )
    )
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.ROLE_ASSIGNMENT_CREATED,
        entity_id=assignment.id,
        actor_user_id=current_user.id,
        affected_user_ids=(payload.user_id,),
        role_id=payload.role_id,
        domain_type=payload.domain_type,
        domain_id=payload.domain_id,
        policy_relevant_fields=("user_id", "role_id", "domain_type", "domain_id"),
    )
    try:
        await session.flush()
        if effective_assignment_created:
            await stage_identity_mutation(authorization_service, session, mutation)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        await _audit_deny(
            user_id=current_user.id,
            action="role_assignment:create",
            obj="role_assignment:*",
            status_code=status.HTTP_409_CONFLICT,
            reason="assignment_conflict",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignment already exists for this user/role/domain",
        ) from exc
    if effective_assignment_created:
        await safe_identity_mutation_committed(authorization_service, mutation)
    await session.refresh(assignment)
    await audit_decision(
        user_id=current_user.id,
        action="role_assignment:create",
        obj=f"role_assignment:{assignment.id}",
        result="allow",
        details={
            "event": AUDIT_EVENT_MUTATION,
            "assignment_id": str(assignment.id),
            "subject_type": "user",
            "user_id": str(payload.user_id),
            "role_id": str(payload.role_id),
            "role_name": role.name,
            "domain_type": payload.domain_type,
            "domain_id": str(payload.domain_id) if payload.domain_id else None,
        },
    )
    logger.info(
        "Assigned role=%s to user=%s (domain=%s/%s)",
        role.name,
        payload.user_id,
        payload.domain_type,
        payload.domain_id,
    )
    return (await _assignment_reads(session, [assignment]))[0]


@router.delete(
    "/{assignment_id}",
    response_model=RoleAssignmentRead,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_204_NO_CONTENT: {"description": "Manual assignment fully revoked."}},
    dependencies=SUPERUSER_ONLY,
)
async def delete_assignment(
    assignment_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> RoleAssignmentRead | Response:
    """Remove a manual grant, returning the assignment when another source preserves it."""
    await _require_superuser(
        current_user,
        action="role_assignment:delete",
        obj=f"role_assignment:{assignment_id}",
    )

    authorization_service = get_authorization_service()
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.ROLE_ASSIGNMENT_DELETED,
        entity_id=assignment_id,
    )

    # Re-read the assignment and all provenance under row locks on dialects
    # that support SELECT FOR UPDATE after the plugin's lock-only preflight.
    # Validation remains reserved for an actual effective-row deletion,
    # preserving existing hook semantics when only a manual source is removed.
    assignment = await session.get(
        AuthzRoleAssignment,
        assignment_id,
        populate_existing=True,
        with_for_update=True,
    )
    if assignment is None:
        await _audit_deny(
            user_id=current_user.id,
            action="role_assignment:delete",
            obj=f"role_assignment:{assignment_id}",
            status_code=status.HTTP_404_NOT_FOUND,
            reason="assignment_not_found",
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    grants = (
        await session.exec(
            select(AuthzRoleAssignmentGrant)
            .where(AuthzRoleAssignmentGrant.assignment_id == assignment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()
    manual_grant = next((grant for grant in grants if grant.source_kind == "manual"), None)
    if grants and manual_grant is None:
        await _audit_deny(
            user_id=current_user.id,
            action="role_assignment:delete",
            obj=f"role_assignment:{assignment_id}",
            status_code=status.HTTP_409_CONFLICT,
            reason="idp_assignment_delete_forbidden",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="IdP-derived assignments cannot be deleted through the manual assignment API",
        )
    if manual_grant is not None and len(grants) > 1:
        surviving_grants = [grant for grant in grants if grant is not manual_grant]
        await session.delete(manual_grant)
        await session.commit()
        await audit_decision(
            user_id=current_user.id,
            action="role_assignment:delete_manual_source",
            obj=f"role_assignment:{assignment_id}",
            result="allow",
            details={
                "event": AUDIT_EVENT_MUTATION,
                "assignment_id": str(assignment_id),
                "subject_type": "user",
                "user_id": str(assignment.user_id),
                "role_id": str(assignment.role_id),
                "domain_type": assignment.domain_type,
                "domain_id": str(assignment.domain_id) if assignment.domain_id else None,
                "effective_assignment_preserved": True,
                "surviving_grant_sources": [
                    {
                        "source_kind": grant.source_kind,
                        "provider_id": grant.provider_id,
                        "external_group": grant.external_group,
                    }
                    for grant in surviving_grants
                ],
            },
        )
        return RoleAssignmentRead.model_validate(assignment).model_copy(
            update={"grant_sources": [RoleAssignmentGrantSummary.model_validate(grant) for grant in surviving_grants]}
        )

    user_id = assignment.user_id
    role_id = assignment.role_id
    domain_type = assignment.domain_type
    domain_id = assignment.domain_id
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.ROLE_ASSIGNMENT_DELETED,
        entity_id=assignment_id,
        actor_user_id=current_user.id,
        affected_user_ids=(user_id,),
        role_id=role_id,
        domain_type=domain_type,
        domain_id=domain_id,
        policy_relevant_fields=("user_id", "role_id", "domain_type", "domain_id"),
    )
    try:
        await validate_identity_mutation(authorization_service, session, mutation)
    except AuthorizationMutationRejected as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.public_detail) from exc

    await session.delete(assignment)
    await session.flush()
    await stage_identity_mutation(authorization_service, session, mutation)
    await session.commit()
    await safe_identity_mutation_committed(authorization_service, mutation)
    await audit_decision(
        user_id=current_user.id,
        action="role_assignment:delete",
        obj=f"role_assignment:{assignment_id}",
        result="allow",
        details={
            "event": AUDIT_EVENT_MUTATION,
            "assignment_id": str(assignment_id),
            "subject_type": "user",
            "user_id": str(user_id),
            "role_id": str(role_id),
            "domain_type": domain_type,
            "domain_id": str(domain_id) if domain_id else None,
        },
    )
    logger.info("Revoked role assignment id=%s (user=%s)", assignment_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
