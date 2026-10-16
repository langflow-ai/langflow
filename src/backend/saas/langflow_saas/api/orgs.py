"""Organization CRUD endpoints.

Routes:
  POST   /api/saas/v1/orgs                 — create org
  GET    /api/saas/v1/orgs                 — list caller's orgs
  GET    /api/saas/v1/orgs/{org_id}        — get org details
  PATCH  /api/saas/v1/orgs/{org_id}        — update (admin+)
  DELETE /api/saas/v1/orgs/{org_id}        — delete (owner only)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from langflow_saas.dependencies import CurrentOrgContext, RequireAdmin, RequireOwner, assert_org_match
from langflow_saas.models import (
    Organization,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
    OrgRole,
    Plan,
    PlanRead,
    UserOrganization,
)
from langflow_saas.services import get_audit_service

router = APIRouter(prefix="/orgs", tags=["Organizations"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:63]


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Slug must be 3–63 lowercase alphanumeric characters or hyphens, cannot start or end with a hyphen.",
        )


async def _org_to_read(org: Organization, role: OrgRole, db) -> OrganizationRead:
    plan: Plan | None = None
    if org.plan_id:
        result = await db.exec(select(Plan).where(Plan.id == org.plan_id))
        plan = result.first()

    return OrganizationRead(
        id=org.id,
        name=org.name,
        slug=org.slug,
        owner_id=org.owner_id,
        is_personal=org.is_personal,
        is_active=org.is_active,
        created_at=org.created_at,
        role=role,
        plan=PlanRead.model_validate(plan) if plan else None,
    )


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_org(body: OrganizationCreate, ctx: CurrentOrgContext, request: Request):
    """Create a new organization.  The caller becomes its owner."""
    from langflow.services.deps import session_scope

    slug = body.slug or _slugify(body.name)
    _validate_slug(slug)

    async with session_scope() as db:
        # Check slug uniqueness.
        existing = await db.exec(select(Organization).where(Organization.slug == slug))
        if existing.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{slug}' is already taken.",
            )

        org = Organization(name=body.name, slug=slug, owner_id=ctx.user_id)
        db.add(org)
        await db.flush()  # populate org.id before creating membership

        membership = UserOrganization(user_id=ctx.user_id, org_id=org.id, role=OrgRole.OWNER)
        db.add(membership)
        await db.commit()
        await db.refresh(org)

    await get_audit_service().log(
        action="org.created",
        org_id=org.id,
        user_id=ctx.user_id,
        resource_type="organization",
        resource_id=str(org.id),
        ip_address=request.client.host if request.client else None,
    )

    async with session_scope() as db:
        return await _org_to_read(org, OrgRole.OWNER, db)


@router.get("", response_model=list[OrganizationRead])
async def list_orgs(ctx: CurrentOrgContext):
    """List all organizations the caller belongs to."""
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        memberships_result = await db.exec(select(UserOrganization).where(UserOrganization.user_id == ctx.user_id))
        memberships = memberships_result.all()

        result = []
        for m in memberships:
            org_result = await db.exec(
                select(Organization).where(Organization.id == m.org_id, Organization.is_active == True)  # noqa: E712
            )
            org = org_result.first()
            if org:
                result.append(await _org_to_read(org, m.role, db))
        return result


@router.get("/{org_id}", response_model=OrganizationRead)
async def get_org(org_id: UUID, ctx: CurrentOrgContext):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        org_result = await db.exec(select(Organization).where(Organization.id == org_id))
        org = org_result.first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found.")
        return await _org_to_read(org, ctx.role, db)


@router.patch("/{org_id}", response_model=OrganizationRead)
async def update_org(org_id: UUID, body: OrganizationUpdate, ctx: RequireAdmin, request: Request):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        org_result = await db.exec(select(Organization).where(Organization.id == org_id))
        org = org_result.first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found.")
        if org.is_personal:
            raise HTTPException(status_code=400, detail="Personal organizations cannot be renamed.")

        if body.name:
            org.name = body.name
        if body.slug:
            _validate_slug(body.slug)
            existing = await db.exec(
                select(Organization).where(Organization.slug == body.slug, Organization.id != org_id)
            )
            if existing.first():
                raise HTTPException(409, detail=f"Slug '{body.slug}' is already taken.")
            org.slug = body.slug

        org.updated_at = datetime.now(timezone.utc)
        db.add(org)
        await db.commit()
        await db.refresh(org)

    await get_audit_service().log(
        action="org.updated",
        org_id=org_id,
        user_id=ctx.user_id,
        resource_type="organization",
        resource_id=str(org_id),
        log_metadata=body.model_dump(exclude_none=True),
        ip_address=request.client.host if request.client else None,
    )

    async with session_scope() as db:
        return await _org_to_read(org, ctx.role, db)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(org_id: UUID, ctx: RequireOwner, request: Request):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        org_result = await db.exec(select(Organization).where(Organization.id == org_id))
        org = org_result.first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found.")
        if org.is_personal:
            raise HTTPException(status_code=400, detail="Personal organizations cannot be deleted.")

        await db.delete(org)
        await db.commit()

    await get_audit_service().log(
        action="org.deleted",
        org_id=org_id,
        user_id=ctx.user_id,
        resource_type="organization",
        resource_id=str(org_id),
        ip_address=request.client.host if request.client else None,
    )
