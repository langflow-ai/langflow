"""CRUD API for authz_role rows (enforcement is delegated to authorization plugins)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from lfx.log.logger import logger
from lfx.services.authorization import AuthorizationMutation, AuthorizationMutationKind
from lfx.utils.util_strings import escape_like_pattern
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.authz_roles import RoleCreate, RoleRead, RoleUpdate
from langflow.services.authorization.admin import administration_audit_details, ensure_administration_permission
from langflow.services.authorization.lifecycle import (
    acquire_identity_mutation_lock,
    safe_identity_mutation_committed,
    stage_identity_mutation,
)
from langflow.services.authorization.utils import audit_decision
from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/roles", tags=["Authorization"])

# Match ``authz_shares``: cap any single list call so an authenticated client
# (or a buggy frontend) can't enumerate the entire role/team catalog in one
# request. 100 default / 200 max is enough for typical UI dropdowns.
_LIST_MAX_LIMIT = 200
_LIST_DEFAULT_LIMIT = 100
OperationId = Annotated[str | None, Header(alias="X-Langflow-Operation-ID", max_length=128)]


async def _require_role_administrator(user, *, operation_id: str | None = None) -> None:
    await ensure_administration_permission(
        user,
        resource="role",
        authorization_service=get_authorization_service(),
        action="role:manage",
        obj="role:*",
        operation_id=operation_id,
    )


async def _require_superuser_dependency(
    current_user: CurrentActiveUser,
    operation_id: OperationId = None,
) -> None:
    """Run the superuser gate as a route dependency, i.e. before body validation.

    FastAPI solves a route's ``dependencies`` before validating that route's own
    body, so an unauthorised caller is refused whatever they post. Gated only in
    the endpoint body, they first receive the same 422 field names and enum
    values a superuser would, which lets them map the request contract of a
    route they cannot invoke.

    The in-body call is kept as well: it is the gate for anything that reaches
    the endpoint function without FastAPI resolving dependencies.
    """
    await _require_role_administrator(current_user, operation_id=operation_id)


SUPERUSER_ONLY = [Depends(_require_superuser_dependency)]


async def _detect_parent_cycle(
    session: DbSession,
    *,
    role_id: UUID,
    proposed_parent_id: UUID,
) -> bool:
    """Walk the parent chain from ``proposed_parent_id``; True if ``role_id`` appears.

    Used to reject ``PATCH`` requests that would set a role as its own ancestor.
    Walks at most ``len(all_roles)`` steps so a pre-existing cycle terminates.
    """
    visited: set[UUID] = set()
    cursor: UUID | None = proposed_parent_id
    while cursor is not None and cursor not in visited:
        if cursor == role_id:
            return True
        visited.add(cursor)
        parent = await session.get(AuthzRole, cursor)
        if parent is None:
            return False
        cursor = parent.parent_role_id
    return False


@router.get("", response_model=list[RoleRead])
@router.get("/", response_model=list[RoleRead])
async def list_roles(
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001 — any authenticated user can list
    is_system: Annotated[bool | None, Query(description="Filter by is_system flag")] = None,
    name: Annotated[str | None, Query(description="Substring match on role name")] = None,
    exact_name: Annotated[str | None, Query(description="Exact match on role name")] = None,
    limit: Annotated[int, Query(ge=1, le=_LIST_MAX_LIMIT)] = _LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RoleRead]:
    """List roles. Open to authenticated users so the UI can populate dropdowns.

    Paginated via ``limit`` / ``offset`` so a single call cannot return the
    entire catalog of roles + their permissions. Stable order is ``(name, id)``
    so ``offset`` is deterministic across calls.
    """
    stmt = select(AuthzRole)
    if is_system is not None:
        stmt = stmt.where(AuthzRole.is_system == is_system)
    if name:
        stmt = stmt.where(AuthzRole.name.ilike(f"%{escape_like_pattern(name)}%", escape="\\"))
    if exact_name is not None:
        stmt = stmt.where(AuthzRole.name == exact_name)
    stmt = stmt.order_by(AuthzRole.name, AuthzRole.id).offset(offset).limit(limit)
    rows = (await session.exec(stmt)).all()
    return [RoleRead.model_validate(row) for row in rows]


@router.get("/{role_id}", response_model=RoleRead)
async def read_role(
    role_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,  # noqa: ARG001 — any authenticated user can read
) -> RoleRead:
    role = await session.get(AuthzRole, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return RoleRead.model_validate(role)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED, dependencies=SUPERUSER_ONLY)
@router.post("/", response_model=RoleRead, status_code=status.HTTP_201_CREATED, dependencies=SUPERUSER_ONLY)
async def create_role(
    payload: RoleCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
    response: Response,
    operation_id: OperationId = None,
) -> RoleRead:
    """Create a custom (non-system) role."""
    await _require_role_administrator(current_user, operation_id=operation_id)
    authorization_service = get_authorization_service()
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.ROLE_CREATED,
    )

    if payload.parent_role_id is not None:
        parent = await session.get(AuthzRole, payload.parent_role_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent_role_id does not reference an existing role",
            )

    role = AuthzRole(
        name=payload.name,
        description=payload.description,
        is_system=False,
        permissions=list(payload.permissions),
        parent_role_id=payload.parent_role_id,
        created_by=current_user.id,
    )
    session.add(role)
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.ROLE_CREATED,
        entity_id=role.id,
        actor_user_id=current_user.id,
        role_id=role.id,
        policy_relevant_fields=("name", "permissions", "parent_role_id"),
    )
    try:
        await session.flush()
        await stage_identity_mutation(authorization_service, session, mutation)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role with name {payload.name!r} already exists",
        ) from exc
    await safe_identity_mutation_committed(authorization_service, mutation)
    await session.refresh(role)
    await audit_decision(
        user_id=current_user.id,
        action="role:create",
        obj=f"role:{role.id}",
        result="allow",
        details=administration_audit_details(
            {
                "role_name": role.name,
                "permissions": list(role.permissions),
                "parent_role_id": str(role.parent_role_id) if role.parent_role_id else None,
            },
            operation_id=operation_id,
        ),
    )
    response.headers["Location"] = f"/api/v1/authz/roles/{role.id}"
    logger.info("Created role %s (id=%s)", role.name, role.id)
    return RoleRead.model_validate(role)


@router.patch("/{role_id}", response_model=RoleRead, dependencies=SUPERUSER_ONLY)
async def update_role(
    role_id: UUID,
    payload: RoleUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
    operation_id: OperationId = None,
) -> RoleRead:
    """Update fields on a custom role. System roles are read-only."""
    await _require_role_administrator(current_user, operation_id=operation_id)
    authorization_service = get_authorization_service()
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.ROLE_UPDATED,
        entity_id=role_id,
    )

    role = await session.get(AuthzRole, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System roles cannot be modified",
        )

    # Use presence checks (model_fields_set) rather than ``is not None`` so PATCH
    # can clear nullable fields. An explicit ``"description": null`` in the body
    # marks the field as set and assigns None; omitting it leaves the row alone.
    fields_set = payload.model_fields_set
    previous_name = role.name

    if "parent_role_id" in fields_set:
        if payload.parent_role_id is None:
            role.parent_role_id = None
        else:
            if payload.parent_role_id == role.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A role cannot be its own parent",
                )
            parent = await session.get(AuthzRole, payload.parent_role_id)
            if parent is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="parent_role_id does not reference an existing role",
                )
            if await _detect_parent_cycle(session, role_id=role.id, proposed_parent_id=payload.parent_role_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Setting this parent would create a role hierarchy cycle",
                )
            role.parent_role_id = payload.parent_role_id

    if "description" in fields_set:
        # description is nullable on the DB side — None is a legitimate clear.
        role.description = payload.description

    if "name" in fields_set:
        # name is NOT NULL + unique on the DB side; reject an explicit null at
        # the boundary so the caller gets a clear 400 instead of an opaque
        # IntegrityError that the catch block below mislabels as "Name conflict".
        if payload.name is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="name cannot be null",
            )
        role.name = payload.name

    if "permissions" in fields_set:
        # permissions column is nullable=False (default_factory=list). An empty
        # list is the natural "clear" — None would violate the constraint at
        # commit, so reject it up front.
        if payload.permissions is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="permissions cannot be null; pass an empty list to clear",
            )
        role.permissions = list(payload.permissions)

    role.updated_at = datetime.now(timezone.utc)
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.ROLE_UPDATED,
        entity_id=role.id,
        actor_user_id=current_user.id,
        role_id=role.id,
        policy_relevant_fields=tuple(sorted(fields_set & {"name", "permissions", "parent_role_id"})),
        previous_identifier=previous_name if role.name != previous_name else None,
    )
    try:
        await session.flush()
        await stage_identity_mutation(authorization_service, session, mutation)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Name conflict — another role already uses this name",
        ) from exc
    await safe_identity_mutation_committed(authorization_service, mutation)
    await session.refresh(role)
    await audit_decision(
        user_id=current_user.id,
        action="role:update",
        obj=f"role:{role.id}",
        result="allow",
        details=administration_audit_details(
            {"role_name": role.name, "fields_changed": sorted(fields_set)},
            operation_id=operation_id,
        ),
    )
    logger.info("Updated role %s (id=%s)", role.name, role.id)
    return RoleRead.model_validate(role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=SUPERUSER_ONLY)
async def delete_role(
    role_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    operation_id: OperationId = None,
) -> None:
    """Delete a custom role.

    System roles cannot be deleted; roles with active assignments return 409
    (delete the assignments first).
    """
    await _require_role_administrator(current_user, operation_id=operation_id)
    authorization_service = get_authorization_service()
    await acquire_identity_mutation_lock(
        authorization_service,
        session,
        kind=AuthorizationMutationKind.ROLE_DELETED,
        entity_id=role_id,
    )

    role = await session.get(AuthzRole, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System roles cannot be deleted",
        )

    assigned = (
        await session.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.role_id == role_id).limit(1))
    ).first()
    if assigned is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role still has active assignments — revoke them before deleting",
        )

    role_name = role.name
    mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.ROLE_DELETED,
        entity_id=role_id,
        actor_user_id=current_user.id,
        role_id=role_id,
        policy_relevant_fields=("name", "permissions", "parent_role_id"),
        previous_identifier=role_name,
    )
    await session.delete(role)
    await session.flush()
    await stage_identity_mutation(authorization_service, session, mutation)
    await session.commit()
    await safe_identity_mutation_committed(authorization_service, mutation)
    await audit_decision(
        user_id=current_user.id,
        action="role:delete",
        obj=f"role:{role_id}",
        result="allow",
        details=administration_audit_details({"role_name": role_name}, operation_id=operation_id),
    )
    logger.info("Deleted role id=%s", role_id)
