"""Team management endpoints.

Routes:
  GET    /api/saas/v1/orgs/{org_id}/teams                              — list teams
  POST   /api/saas/v1/orgs/{org_id}/teams                              — create team (admin+)
  DELETE /api/saas/v1/orgs/{org_id}/teams/{team_id}                    — delete team (admin+)
  POST   /api/saas/v1/orgs/{org_id}/teams/{team_id}/members            — add member (admin+)
  DELETE /api/saas/v1/orgs/{org_id}/teams/{team_id}/members/{user_id}  — remove member
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from langflow_saas.dependencies import CurrentOrgContext, RequireAdmin, assert_org_match
from langflow_saas.models import Team, TeamCreate, TeamMember, TeamRead, UserOrganization
from langflow_saas.services import get_audit_service

router = APIRouter(tags=["Teams"])


@router.get("/orgs/{org_id}/teams", response_model=list[TeamRead])
async def list_teams(org_id: UUID, ctx: CurrentOrgContext):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(select(Team).where(Team.org_id == org_id))
        return [TeamRead(id=t.id, org_id=t.org_id, name=t.name, description=t.description) for t in result.all()]


@router.post("/orgs/{org_id}/teams", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(org_id: UUID, body: TeamCreate, ctx: RequireAdmin, request: Request):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        # Name uniqueness within org.
        existing = await db.exec(select(Team).where(Team.org_id == org_id, Team.name == body.name))
        if existing.first():
            raise HTTPException(409, f"A team named '{body.name}' already exists in this org.")

        team = Team(org_id=org_id, name=body.name, description=body.description)
        db.add(team)
        await db.commit()
        await db.refresh(team)

    await get_audit_service().log(
        action="team.created",
        org_id=org_id,
        user_id=ctx.user_id,
        resource_type="team",
        resource_id=str(team.id),
        ip_address=request.client.host if request.client else None,
    )
    return TeamRead(id=team.id, org_id=team.org_id, name=team.name, description=team.description)


@router.delete("/orgs/{org_id}/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(org_id: UUID, team_id: UUID, ctx: RequireAdmin, request: Request):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(select(Team).where(Team.id == team_id, Team.org_id == org_id))
        team = result.first()
        if not team:
            raise HTTPException(404, "Team not found.")
        await db.delete(team)
        await db.commit()

    await get_audit_service().log(
        action="team.deleted",
        org_id=org_id,
        user_id=ctx.user_id,
        resource_type="team",
        resource_id=str(team_id),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/orgs/{org_id}/teams/{team_id}/members", status_code=status.HTTP_201_CREATED)
async def add_team_member(org_id: UUID, team_id: UUID, target_user_id: UUID, ctx: RequireAdmin):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        # Verify user is an org member.
        mem_result = await db.exec(
            select(UserOrganization).where(
                UserOrganization.org_id == org_id, UserOrganization.user_id == target_user_id
            )
        )
        if not mem_result.first():
            raise HTTPException(400, "User is not a member of this organization.")

        # Check already on team.
        existing = await db.exec(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == target_user_id)
        )
        if existing.first():
            raise HTTPException(409, "User is already on this team.")

        db.add(TeamMember(team_id=team_id, user_id=target_user_id))
        await db.commit()

    return {"ok": True}


@router.delete(
    "/orgs/{org_id}/teams/{team_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_team_member(org_id: UUID, team_id: UUID, target_user_id: UUID, ctx: RequireAdmin):
    assert_org_match(org_id, ctx)
    from langflow.services.deps import session_scope

    async with session_scope() as db:
        result = await db.exec(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == target_user_id)
        )
        member = result.first()
        if not member:
            raise HTTPException(404, "Team member not found.")
        await db.delete(member)
        await db.commit()
