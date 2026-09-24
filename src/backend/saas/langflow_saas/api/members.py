"""Membership and invitation management endpoints.

Routes:
  GET    /api/saas/v1/orgs/{org_id}/members                  — list members
  PATCH  /api/saas/v1/orgs/{org_id}/members/{user_id}        — change role (admin+)
  DELETE /api/saas/v1/orgs/{org_id}/members/{user_id}        — remove member (admin+)
  POST   /api/saas/v1/orgs/{org_id}/invitations              — invite by email (admin+)
  GET    /api/saas/v1/orgs/{org_id}/invitations              — list pending invitations
  DELETE /api/saas/v1/orgs/{org_id}/invitations/{invite_id}  — revoke invitation
  GET    /api/saas/v1/invitations/{token}                     — get invitation info (public)
  POST   /api/saas/v1/invitations/{token}/accept              — accept invitation (authenticated)
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from langflow_saas.dependencies import CurrentOrgContext, RequireAdmin, assert_org_match
from langflow_saas.models import (
    Invitation,
    InvitationCreate,
    InvitationRead,
    InvitationStatus,
    MemberRead,
    OrgRole,
    UserOrganization,
)
from langflow_saas.services import get_audit_service, get_email_service
from langflow_saas.settings import get_saas_settings

router = APIRouter(tags=["Members & Invitations"])


def _make_token(invitation_id: UUID, secret: str) -> str:
    """Produce a URL-safe HMAC token from the invitation ID."""
    sig = hmac.new(secret.encode(), str(invitation_id).encode(), hashlib.sha256).hexdigest()
    return f"{invitation_id.hex}_{sig}"


def _verify_token(token: str, secret: str) -> UUID | None:
    """Return the invitation UUID if the token is valid, else None."""
    try:
        id_part, sig_part = token.split("_", 1)
        inv_id = UUID(id_part)
        expected = hmac.new(secret.encode(), str(inv_id).encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, sig_part):
            return inv_id
    except Exception:  # noqa: BLE001
        pass
    return None


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/orgs/{org_id}/members", response_model=list[MemberRead])
async def list_members(org_id: UUID, ctx: CurrentOrgContext):
    assert_org_match(org_id, ctx)
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(
            select(UserOrganization, User)
            .join(User, User.id == UserOrganization.user_id)  # type: ignore[arg-type]
            .where(UserOrganization.org_id == org_id)
        )
        rows = result.all()
        return [
            MemberRead(
                user_id=UUID(str(uo.user_id)),
                username=user.username,
                role=uo.role,
                joined_at=uo.created_at,
            )
            for uo, user in rows
        ]


@router.patch("/orgs/{org_id}/members/{target_user_id}", status_code=status.HTTP_200_OK)
async def update_member_role(
    org_id: UUID,
    target_user_id: UUID,
    role: OrgRole,
    ctx: RequireAdmin,
    request: Request,
):
    assert_org_match(org_id, ctx)

    if role == OrgRole.OWNER:
        raise HTTPException(400, "Transfer ownership via the dedicated transfer-ownership endpoint.")

    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(
            select(UserOrganization).where(
                UserOrganization.org_id == org_id, UserOrganization.user_id == target_user_id
            )
        )
        membership = result.first()
        if not membership:
            raise HTTPException(404, "Member not found in this organization.")
        if membership.role == OrgRole.OWNER and ctx.role != OrgRole.OWNER:
            raise HTTPException(403, "Only the owner can change the owner's role.")

        membership.role = role
        db.add(membership)
        await db.commit()

    await get_audit_service().log(
        action="member.role_changed",
        org_id=org_id,
        user_id=ctx.user_id,
        resource_type="user",
        resource_id=str(target_user_id),
        log_metadata={"new_role": role.value},
        ip_address=request.client.host if request.client else None,
    )
    return {"ok": True}


@router.delete("/orgs/{org_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(org_id: UUID, target_user_id: UUID, ctx: RequireAdmin, request: Request):
    assert_org_match(org_id, ctx)

    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(
            select(UserOrganization).where(
                UserOrganization.org_id == org_id, UserOrganization.user_id == target_user_id
            )
        )
        membership = result.first()
        if not membership:
            raise HTTPException(404, "Member not found.")
        if membership.role == OrgRole.OWNER:
            raise HTTPException(400, "Cannot remove the owner. Transfer ownership first.")

        await db.delete(membership)
        await db.commit()

    await get_audit_service().log(
        action="member.removed",
        org_id=org_id,
        user_id=ctx.user_id,
        resource_type="user",
        resource_id=str(target_user_id),
        ip_address=request.client.host if request.client else None,
    )


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------


@router.post(
    "/orgs/{org_id}/invitations",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(org_id: UUID, body: InvitationCreate, ctx: RequireAdmin, request: Request):
    assert_org_match(org_id, ctx)
    settings = get_saas_settings()
    from langflow.services.deps import session_scope

    from langflow_saas.models import Organization

    async with session_scope() as db:
        # Check member cap.
        org_result = await db.exec(select(Organization).where(Organization.id == org_id))
        org = org_result.first()

        count_result = await db.exec(select(UserOrganization).where(UserOrganization.org_id == org_id))
        member_count = len(count_result.all())
        if org and member_count >= settings.default_max_members:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Member limit ({settings.default_max_members}) reached. "
                "Upgrade your plan to invite more members.",
            )

        # Revoke any open invitation for same email+org.
        existing_inv = await db.exec(
            select(Invitation).where(
                Invitation.org_id == org_id,
                Invitation.email == body.email,
                Invitation.status == InvitationStatus.PENDING,
            )
        )
        for old in existing_inv.all():
            old.status = InvitationStatus.REVOKED
            db.add(old)

        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.invitation_expire_hours)
        invitation = Invitation(
            org_id=org_id,
            email=body.email,
            role=body.role,
            invited_by=ctx.user_id,
            expires_at=expires_at,
            token_hash="",  # filled below after we have the id
        )
        db.add(invitation)
        await db.flush()

        token = _make_token(invitation.id, settings.invitation_secret.get_secret_value())
        invitation.token_hash = hashlib.sha256(token.encode()).hexdigest()
        db.add(invitation)
        await db.commit()
        await db.refresh(invitation)

    accept_url = f"{settings.app_base_url}/invitations/{token}/accept"
    org_name = org.name if org else str(org_id)
    await get_email_service().send_invitation(
        to_email=body.email,
        org_name=org_name,
        inviter_name=ctx.username,
        role=body.role.value,
        accept_url=accept_url,
        expire_hours=settings.invitation_expire_hours,
    )

    await get_audit_service().log(
        action="member.invited",
        org_id=org_id,
        user_id=ctx.user_id,
        resource_type="invitation",
        resource_id=str(invitation.id),
        log_metadata={"email": body.email, "role": body.role.value},
        ip_address=request.client.host if request.client else None,
    )

    return InvitationRead(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.get("/orgs/{org_id}/invitations", response_model=list[InvitationRead])
async def list_invitations(org_id: UUID, ctx: RequireAdmin):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(
            select(Invitation).where(Invitation.org_id == org_id, Invitation.status == InvitationStatus.PENDING)
        )
        return [
            InvitationRead(
                id=inv.id,
                email=inv.email,
                role=inv.role,
                status=inv.status,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
            )
            for inv in result.all()
        ]


@router.delete("/orgs/{org_id}/invitations/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(org_id: UUID, invite_id: UUID, ctx: RequireAdmin):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(select(Invitation).where(Invitation.id == invite_id, Invitation.org_id == org_id))
        inv = result.first()
        if not inv:
            raise HTTPException(404, "Invitation not found.")
        inv.status = InvitationStatus.REVOKED
        db.add(inv)
        await db.commit()


# ---------------------------------------------------------------------------
# Public invitation acceptance (no org context — user may not be in the org yet)
# ---------------------------------------------------------------------------


@router.get("/invitations/{token}")
async def get_invitation_info(token: str):
    """Return public invitation details (org name, role, expiry) — no auth required."""
    settings = get_saas_settings()
    inv_id = _verify_token(token, settings.invitation_secret.get_secret_value())
    if not inv_id:
        raise HTTPException(400, "Invalid invitation token.")

    from langflow.services.deps import session_scope

    from langflow_saas.models import Organization

    async with session_scope() as db:
        result = await db.exec(select(Invitation).where(Invitation.id == inv_id))
        inv = result.first()
        if not inv:
            raise HTTPException(404, "Invitation not found.")

        if inv.status != InvitationStatus.PENDING:
            raise HTTPException(410, f"Invitation is {inv.status.value}.")
        if inv.expires_at < datetime.now(timezone.utc):
            raise HTTPException(410, "Invitation has expired.")

        org_result = await db.exec(select(Organization).where(Organization.id == inv.org_id))
        org = org_result.first()
        org_name = org.name if org else str(inv.org_id)

    return {
        "id": str(inv.id),
        "org_name": org_name,
        "email": inv.email,
        "role": inv.role.value,
        "expires_at": inv.expires_at.isoformat(),
    }


@router.post("/invitations/{token}/accept", status_code=status.HTTP_200_OK)
async def accept_invitation(token: str, ctx: CurrentOrgContext, request: Request):
    """Accept a pending invitation.  Caller must be authenticated as the invited email
    OR an admin can accept on behalf.  For simplicity we trust the authenticated user.
    """
    settings = get_saas_settings()
    inv_id = _verify_token(token, settings.invitation_secret.get_secret_value())
    if not inv_id:
        raise HTTPException(400, "Invalid invitation token.")

    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(select(Invitation).where(Invitation.id == inv_id))
        inv = result.first()
        if not inv:
            raise HTTPException(404, "Invitation not found.")
        if inv.status != InvitationStatus.PENDING:
            raise HTTPException(410, f"Invitation is {inv.status.value}.")
        if inv.expires_at < datetime.now(timezone.utc):
            raise HTTPException(410, "Invitation has expired.")

        # Check already a member.
        existing_m = await db.exec(
            select(UserOrganization).where(
                UserOrganization.user_id == ctx.user_id,
                UserOrganization.org_id == inv.org_id,
            )
        )
        if existing_m.first():
            raise HTTPException(409, "You are already a member of this organization.")

        # Create membership.
        membership = UserOrganization(
            user_id=ctx.user_id,
            org_id=inv.org_id,
            role=inv.role,
            invitation_id=inv.id,
        )
        db.add(membership)

        inv.status = InvitationStatus.ACCEPTED
        inv.accepted_at = datetime.now(timezone.utc)
        inv.accepted_by = ctx.user_id
        db.add(inv)
        await db.commit()

    await get_audit_service().log(
        action="member.joined",
        org_id=inv.org_id,
        user_id=ctx.user_id,
        resource_type="invitation",
        resource_id=str(inv.id),
        ip_address=request.client.host if request.client else None,
    )
    return {"ok": True, "org_id": str(inv.org_id)}
