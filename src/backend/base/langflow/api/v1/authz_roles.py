"""CRUD API for authz_role rows (enforcement is delegated to authorization plugins)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas.authz_roles import RoleCreate, RoleRead, RoleUpdate
from langflow.services.database.models.auth import AuthzRole, AuthzRoleAssignment
from langflow.services.deps import get_authorization_service

router = APIRouter(prefix="/authz/roles", tags=["Authorization"])


def _require_superuser(user) -> None:
    """Superuser-only gate. Role admin is an operations action."""
    if not getattr(user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser required to administer roles.",
        )


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
) -> list[RoleRead]:
    """List all roles. Open to authenticated users so the UI can populate dropdowns."""
    stmt = select(AuthzRole)
    if is_system is not None:
        stmt = stmt.where(AuthzRole.is_system == is_system)
    if name:
        stmt = stmt.where(AuthzRole.name.ilike(f"%{name}%"))
    rows = (await session.exec(stmt.order_by(AuthzRole.name))).all()
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


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> RoleRead:
    """Create a custom (non-system) role. Superuser-only."""
    _require_superuser(current_user)

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
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role with name {payload.name!r} already exists",
        ) from exc
    await session.refresh(role)
    await get_authorization_service().invalidate_all()
    logger.info("Created role %s (id=%s)", role.name, role.id)
    return RoleRead.model_validate(role)


@router.patch("/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: UUID,
    payload: RoleUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> RoleRead:
    """Update fields on a custom role. System roles are read-only."""
    _require_superuser(current_user)

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

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Name conflict — another role already uses this name",
        ) from exc
    await session.refresh(role)
    await get_authorization_service().invalidate_role(role.id)
    logger.info("Updated role %s (id=%s)", role.name, role.id)
    return RoleRead.model_validate(role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    """Delete a custom role.

    System roles cannot be deleted; roles with active assignments return 409
    (delete the assignments first).
    """
    _require_superuser(current_user)

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

    await session.delete(role)
    await session.commit()
    await get_authorization_service().invalidate_role(role_id)
    logger.info("Deleted role id=%s", role_id)
