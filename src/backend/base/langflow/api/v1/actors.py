"""LangFlow Actor API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi_pagination import Page
from sqlmodel import and_, col, or_, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.actor.model import Actor, ActorRead, EntityType
from langflow.services.database.models.flow.model import Flow

# build router
router = APIRouter(prefix="/actors", tags=["Actors"])


@router.get("/", response_model=list[ActorRead] | Page[ActorRead], status_code=200)
async def read_actors(
    *,
    session: DbSession,
    entity_type: EntityType | None = None,
    entity_id: UUID | None = None,
    project_id: UUID | None = None,
    current_user: CurrentActiveUser,
):
    """Retrieve a list of actors with optional filtering and pagination support."""
    try:
        # Create base conditions for filtering
        conditions = []

        # Apply entity filters if provided
        if entity_type:
            conditions.append(Actor.entity_type == entity_type)
        if entity_id:
            conditions.append(Actor.entity_id == entity_id)

        # Create a query for flows that belong to the current user
        flow_query = select(Flow.id).where(Flow.user_id == current_user.id)
        if project_id:
            flow_query = flow_query.where(Flow.folder_id == project_id)

        # Create the combined query with OR conditions
        # Either: Actor is for the current user
        # Or: Actor is for a flow owned by the current user
        stmt = select(Actor).where(
            or_(
                # Case 1: Actor directly points to the current user
                and_(Actor.entity_type == EntityType.USER, Actor.entity_id == current_user.id, *conditions),
                # Case 2: Actor points to a flow that belongs to the current user
                and_(Actor.entity_type == EntityType.FLOW, col(Actor.entity_id).in_(flow_query), *conditions),
            )
        )

        actors = (await session.exec(stmt)).all()
        actor_reads = []
        for actor in actors:
            name = await actor.get_name(session)
            actor_read = ActorRead.model_validate(actor, from_attributes=True)
            actor_read.name = name
            actor_reads.append(actor_read)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e
    return actor_reads


@router.get("/{actor_id}", response_model=ActorRead, status_code=200)
async def read_actor(
    *,
    session: DbSession,
    actor_id: UUID,
):
    """Read an actor by ID."""
    actor = (await session.exec(select(Actor).where(Actor.id == actor_id))).first()
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    name = await actor.get_name(session)
    actor_read = ActorRead.model_validate(actor, from_attributes=True)
    actor_read.name = name
    return actor_read


@router.get("/{actor_id}/entity", status_code=200)
async def read_actor_entity(
    *,
    session: DbSession,
    actor_id: UUID,
):
    """Get the actual entity (User or Flow) that this Actor represents."""
    actor = (await session.exec(select(Actor).where(Actor.id == actor_id))).first()
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    entity = await actor.get_entity(session)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    return entity


@router.get("/user/{user_id}", response_model=list[ActorRead], status_code=200)
async def list_actors(
    *,
    session: DbSession,
    user_id: UUID,
    project_id: UUID | None = None,
    current_user: CurrentActiveUser,
):
    """List all actors for a specific user, with optional project filtering.

    This endpoint returns:
    1. Actors that directly represent the specified user
    2. Actors that represent flows owned by the specified user

    If project_id is provided, it will only return flow actors from that project.
    """
    try:
        # Check if the user has permission to view these actors
        if current_user.id != user_id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized to view actors for this user")

        # Create a query for flows that belong to the specified user
        flow_query = select(Flow.id).where(Flow.user_id == user_id)
        if project_id:
            flow_query = flow_query.where(Flow.folder_id == project_id)

        # Create the combined query with OR conditions
        # Either: Actor is for the specified user
        # Or: Actor is for a flow owned by the specified user
        stmt = select(Actor).where(
            or_(
                # Case 1: Actor directly points to the specified user
                and_(Actor.entity_type == EntityType.USER, Actor.entity_id == user_id),
                # Case 2: Actor points to a flow that belongs to the specified user
                and_(Actor.entity_type == EntityType.FLOW, col(Actor.entity_id).in_(flow_query)),
            )
        )

        actors = (await session.exec(stmt)).all()
        actor_reads = []
        for actor in actors:
            name = await actor.get_name(session)
            actor_read = ActorRead.model_validate(actor, from_attributes=True)
            actor_read.name = name
            actor_reads.append(actor_read)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e
    return actor_reads
