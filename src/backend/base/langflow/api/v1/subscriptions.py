"""LangFlow Subscription API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from loguru import logger
from sqlmodel import and_, col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.subscription.model import (
    Subscription,
    SubscriptionCreate,
    SubscriptionRead,
)


# Create a SubscriptionUpdate class since it doesn't exist yet
class SubscriptionUpdate(SubscriptionCreate):
    """Update model for Subscription."""


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.post("/", response_model=SubscriptionRead, status_code=201)
async def create_subscription(
    *,
    session: DbSession,
    subscription: SubscriptionCreate,
    current_user: CurrentActiveUser,
):
    """Create a new subscription.

    Subscriptions link flows to specific event types, allowing flows to be triggered
    when those events occur.
    """
    try:
        # Verify that the flow belongs to the current user
        query = select(Flow).where(and_(Flow.id == subscription.flow_id, Flow.user_id == current_user.id))
        result = await session.exec(query)
        flow = result.first()

        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found or you don't have permission to access it")

        db_subscription = Subscription.model_validate(subscription, from_attributes=True)
        session.add(db_subscription)
        await session.commit()
        await session.refresh(db_subscription)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription: {e!s}")
        raise HTTPException(status_code=400, detail=f"Error creating subscription: {e!s}") from e
    return db_subscription


@router.get("/", response_model=list[SubscriptionRead])
async def read_subscriptions(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
):
    """Get all subscriptions with pagination."""
    try:
        # Get subscriptions associated with flows that belong to the current user
        query = (
            select(Subscription)
            .join(Subscription.flow)
            .where(col(Subscription.flow).has(user_id=current_user.id))
            .offset(skip)
            .limit(limit)
        )
        result = await session.exec(query)
        subscriptions = result.all()
    except Exception as e:
        logger.error(f"Error reading subscriptions: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error reading subscriptions: {e!s}") from e
    return subscriptions


@router.get("/{subscription_id}", response_model=SubscriptionRead)
async def read_subscription(
    *,
    session: DbSession,
    subscription_id: UUID,
    current_user: CurrentActiveUser,
):
    """Get a specific subscription by ID."""
    try:
        # Get subscription by ID and ensure it belongs to a flow owned by the current user
        query = (
            select(Subscription)
            .join(Subscription.flow)
            .where(and_(Subscription.id == subscription_id, Subscription.flow.has(user_id=current_user.id)))
        )
        result = await session.exec(query)
        subscription = result.first()

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading subscription: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error reading subscription: {e!s}") from e
    return subscription


@router.put("/{subscription_id}", response_model=SubscriptionRead)
async def update_subscription(
    *,
    session: DbSession,
    subscription_id: UUID,
    subscription_update: SubscriptionUpdate,
    current_user: CurrentActiveUser,
):
    """Update a specific subscription by ID."""
    try:
        # Get subscription by ID and ensure it belongs to a flow owned by the current user
        query = (
            select(Subscription)
            .join(Subscription.flow)
            .where(and_(Subscription.id == subscription_id, Subscription.flow.has(user_id=current_user.id)))
        )
        result = await session.exec(query)
        db_subscription = result.first()

        if not db_subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Update subscription attributes
        subscription_data = subscription_update.dict(exclude_unset=True)
        for key, value in subscription_data.items():
            setattr(db_subscription, key, value)

        session.add(db_subscription)
        await session.commit()
        await session.refresh(db_subscription)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating subscription: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error updating subscription: {e!s}") from e
    return db_subscription


@router.delete("/{subscription_id}", response_model=SubscriptionRead)
async def delete_subscription(
    *,
    session: DbSession,
    subscription_id: UUID,
    current_user: CurrentActiveUser,
):
    """Delete a specific subscription by ID."""
    try:
        # Get subscription by ID and ensure it belongs to a flow owned by the current user
        query = (
            select(Subscription)
            .join(Subscription.flow)
            .where(and_(Subscription.id == subscription_id, Subscription.flow.has(user_id=current_user.id)))
        )
        result = await session.exec(query)
        subscription = result.first()

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        await session.delete(subscription)
        await session.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting subscription: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error deleting subscription: {e!s}") from e
    return subscription
