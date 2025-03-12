from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import and_, col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.actor.model import Actor, EntityType
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


async def ensure_actors_for_all_entities(session: AsyncSession) -> dict[str, Any]:
    """Scans all users and flows in the database and creates Actor records for any that don't have them.

    This function is useful for:
    - Migrating existing database data after adding the Actor model
    - Ensuring data consistency by creating any missing Actor records

    Args:
        session: The database session

    Returns:
        A dictionary with statistics about how many Actor records were created
    """
    stats: dict[str, Any] = {
        "users_processed": 0,
        "flows_processed": 0,
        "user_actors_created": 0,
        "flow_actors_created": 0,
        "errors": [],
    }

    # Process all users
    users_query = select(User)
    users_result = await session.exec(users_query)
    users = users_result.all()
    stats["users_processed"] = len(users)

    for user in users:
        try:
            # Check if an Actor already exists for this user
            actor_check_query = select(Actor).where(
                (Actor.entity_type == EntityType.USER) & (Actor.entity_id == user.id)
            )
            actor_result = await session.exec(actor_check_query)
            existing_actor = actor_result.first()

            if not existing_actor:
                # Create a new Actor for this user
                actor = Actor(entity_type=EntityType.USER, entity_id=user.id)
                session.add(actor)
                stats["user_actors_created"] += 1
        except SQLAlchemyError as e:
            # Get the errors list without redefining it
            stats["errors"].append(f"Database error processing user {user.id}: {e!s}")

    # Process all flows
    flows_query = select(Flow)
    flows_result = await session.exec(flows_query)
    flows = flows_result.all()
    stats["flows_processed"] = len(flows)

    for flow in flows:
        try:
            # Check if an Actor already exists for this flow
            actor_check_query = select(Actor).where(
                (Actor.entity_type == EntityType.FLOW) & (Actor.entity_id == flow.id)
            )
            actor_result = await session.exec(actor_check_query)
            existing_actor = actor_result.first()

            if not existing_actor:
                # Create a new Actor for this flow
                actor = Actor(entity_type=EntityType.FLOW, entity_id=flow.id)
                session.add(actor)
                stats["flow_actors_created"] += 1
        except SQLAlchemyError as e:
            # Get the errors list without redefining it
            stats["errors"].append(f"Database error processing flow {flow.id}: {e!s}")

    # Commit all the new Actor records
    if stats["user_actors_created"] > 0 or stats["flow_actors_created"] > 0:
        await session.commit()

    return stats


async def get_or_create_actor(session: AsyncSession, entity_type: EntityType, entity_id: UUID) -> tuple[Actor, bool]:
    """Gets an existing Actor for the given entity, or creates one if it doesn't exist.

    Args:
        session: The database session
        entity_type: The type of entity (EntityType.USER or EntityType.FLOW)
        entity_id: The ID of the entity

    Returns:
        A tuple containing (actor, created) where created is a boolean indicating
        whether a new Actor was created
    """
    # Check if an Actor already exists
    query = select(Actor).where((Actor.entity_type == entity_type) & (Actor.entity_id == entity_id))
    result = await session.exec(query)
    existing_actor = result.first()

    if existing_actor:
        return existing_actor, False

    # Create a new Actor
    actor = Actor(entity_type=entity_type, entity_id=entity_id)
    session.add(actor)
    await session.commit()
    await session.refresh(actor)

    return actor, True


async def delete_orphaned_actors(session: AsyncSession) -> dict[str, Any]:
    """Deletes any Actor records that reference non-existent users or flows.

    This is useful for cleaning up the database after users or flows have been deleted.

    Args:
        session: The database session

    Returns:
        A dictionary with statistics about how many orphaned Actor records were deleted
    """
    stats: dict[str, Any] = {
        "user_actors_checked": 0,
        "flow_actors_checked": 0,
        "user_actors_deleted": 0,
        "flow_actors_deleted": 0,
        "errors": [],
    }

    # Check user actors
    user_actors_query = select(Actor).where(Actor.entity_type == EntityType.USER)
    user_actors_result = await session.exec(user_actors_query)
    user_actors = user_actors_result.all()
    stats["user_actors_checked"] = len(user_actors)

    for actor in user_actors:
        try:
            # Check if the user exists
            user_query = select(User).where(User.id == actor.entity_id)
            user_result = await session.exec(user_query)
            user = user_result.first()

            if not user:
                # Delete the orphaned actor
                await session.delete(actor)
                stats["user_actors_deleted"] += 1
        except SQLAlchemyError as e:
            # Get the errors list without redefining it
            stats["errors"].append(f"Database error checking user actor {actor.id}: {e!s}")

    # Check flow actors
    flow_actors_query = select(Actor).where(Actor.entity_type == EntityType.FLOW)
    flow_actors_result = await session.exec(flow_actors_query)
    flow_actors = flow_actors_result.all()
    stats["flow_actors_checked"] = len(flow_actors)

    for actor in flow_actors:
        try:
            # Check if the flow exists
            flow_query = select(Flow).where(Flow.id == actor.entity_id)
            flow_result = await session.exec(flow_query)
            flow = flow_result.first()

            if not flow:
                # Delete the orphaned actor
                await session.delete(actor)
                stats["flow_actors_deleted"] += 1
        except SQLAlchemyError as e:
            # Get the errors list without redefining it
            stats["errors"].append(f"Database error checking flow actor {actor.id}: {e!s}")

    # Commit all the deletions
    if stats["user_actors_deleted"] > 0 or stats["flow_actors_deleted"] > 0:
        await session.commit()

    return stats


async def list_actors_for_user(
    user_id: UUID,
    project_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """List all actors for a specific user, with optional project filtering.

    This function returns:
    1. Actors that directly represent the specified user
    2. Actors that represent flows owned by the specified user

    Args:
        user_id: The ID of the user to list actors for
        project_id: Optional project ID to filter flow actors by

    Returns:
        A list of dictionaries containing basic actor information
    """
    async with session_scope() as session:
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
        result = []

        for actor in actors:
            # Get the name of the entity
            name = await actor.get_name(session)

            # Create the base actor info
            actor_info = {
                "id": str(actor.id),
                "entity_type": actor.entity_type,
                "entity_id": str(actor.entity_id),
                "name": name or ("User" if actor.entity_type == EntityType.USER else "Flow"),
            }

            result.append(actor_info)

        return result


async def list_actors_with_details_for_user(
    user_id: UUID,
    project_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """List all actors for a specific user with additional entity details.

    This function returns:
    1. Actors that directly represent the specified user
    2. Actors that represent flows owned by the specified user

    Each actor includes additional entity details like description for flows
    and username for users.

    Args:
        user_id: The ID of the user to list actors for
        project_id: Optional project ID to filter flow actors by

    Returns:
        A list of dictionaries containing detailed actor information
    """
    async with session_scope() as session:
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
        result = []

        for actor in actors:
            # Get the name of the entity
            name = await actor.get_name(session)

            # Create the base actor info
            actor_info = {
                "id": str(actor.id),
                "entity_type": actor.entity_type,
                "entity_id": str(actor.entity_id),
                "name": name,
            }

            # Include additional entity details
            entity = await actor.get_entity(session)
            if entity and actor.entity_type == EntityType.FLOW and hasattr(entity, "description"):
                actor_info["description"] = entity.description

            result.append(actor_info)

        return result
