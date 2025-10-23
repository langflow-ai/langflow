"""Published Flows API endpoints for marketplace functionality."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.flows import clone_flow_for_marketplace
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.published_flow.model import (
    PublishedFlow,
    PublishedFlowCreate,
    PublishedFlowRead,
    PublishStatusEnum,
)
from langflow.services.database.models.user.model import User
from langflow.services.auth.permissions import can_edit_flow, get_user_roles_from_request
from langflow.logging import logger

router = APIRouter(prefix="/published-flows", tags=["Published Flows"])


@router.post("/publish/{flow_id}", response_model=PublishedFlowRead, status_code=status.HTTP_201_CREATED)
async def publish_flow(
    flow_id: UUID,
    payload: PublishedFlowCreate,
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Publish a flow to marketplace by cloning it.

    - First publish: Creates clone in target folder + published_flow record
    - Re-publish: Updates existing clone with new data from original
    """
    # 1. Fetch original flow
    original_flow = await session.get(Flow, flow_id)
    if not original_flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    # 2. Check permissions
    user_roles = get_user_roles_from_request(request)
    if not can_edit_flow(current_user, original_flow, user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to publish this flow",
        )

    # 3. Determine target folder (use payload if provided, otherwise use original flow's folder)
    target_folder_id = payload.target_folder_id if payload.target_folder_id else original_flow.folder_id

    if not target_folder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Flow must belong to a folder to be published"
        )

    target_folder = await session.get(Folder, target_folder_id)
    if not target_folder or target_folder.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target folder")

    # 4. Check if already published (by flow_cloned_from)
    existing_result = await session.exec(
        select(PublishedFlow).where(PublishedFlow.flow_cloned_from == flow_id)
    )
    existing = existing_result.first()

    if existing:
        # RE-PUBLISH: Update existing clone
        cloned_flow = await session.get(Flow, existing.flow_id)

        if not cloned_flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cloned flow not found"
            )

        # Update clone's data from original
        import copy

        cloned_flow.data = copy.deepcopy(original_flow.data) if original_flow.data else {}
        cloned_flow.description = original_flow.description
        cloned_flow.tags = original_flow.tags
        cloned_flow.icon = original_flow.icon

        # Update published_flow record (copy description/tags for pagination)
        existing.version = payload.version
        existing.category = payload.category
        existing.description = original_flow.description  # Denormalized
        existing.tags = original_flow.tags  # Denormalized
        existing.published_at = datetime.now(timezone.utc)
        existing.updated_at = datetime.now(timezone.utc)
        existing.status = PublishStatusEnum.PUBLISHED

        session.add(cloned_flow)
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        await session.refresh(cloned_flow)

        logger.info(f"Re-published flow '{original_flow.name}' (ID: {flow_id}) to marketplace")

        # Return response
        result_data = PublishedFlowRead.model_validate(existing, from_attributes=True)
        result_data.flow_name = cloned_flow.name
        result_data.flow_icon = cloned_flow.icon
        result_data.published_by_username = current_user.username

        return result_data

    # NEW PUBLISH: Clone flow and create published_flow record
    cloned_flow = await clone_flow_for_marketplace(
        session=session,
        original_flow=original_flow,
        target_folder_id=target_folder_id,
        user_id=current_user.id,
        marketplace_flow_name=payload.marketplace_flow_name,
    )

    # Create published_flow record (with denormalized description/tags)
    published_flow = PublishedFlow(
        flow_id=cloned_flow.id,  # Points to clone
        flow_cloned_from=flow_id,  # Points to original
        user_id=current_user.id,
        published_by=current_user.id,
        status=PublishStatusEnum.PUBLISHED,
        version=payload.version,
        category=payload.category,
        description=original_flow.description,  # Denormalized for pagination
        tags=original_flow.tags,  # Denormalized for pagination
        published_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    session.add(published_flow)
    await session.commit()
    await session.refresh(published_flow)

    logger.info(f"Published flow '{original_flow.name}' (ID: {flow_id}) to marketplace")

    # Return response
    result_data = PublishedFlowRead.model_validate(published_flow, from_attributes=True)
    result_data.flow_name = cloned_flow.name
    result_data.flow_icon = cloned_flow.icon
    result_data.published_by_username = current_user.username

    return result_data


@router.post("/unpublish/{flow_id}", status_code=status.HTTP_200_OK)
async def unpublish_flow(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Unpublish a flow (soft delete - changes status to UNPUBLISHED)."""
    # Query by flow_cloned_from instead of flow_id
    query = select(PublishedFlow).where(
        PublishedFlow.flow_cloned_from == flow_id, PublishedFlow.user_id == current_user.id
    )
    result = await session.exec(query)
    published_flow = result.first()

    if not published_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published flow not found or you don't have permission to unpublish it",
        )

    published_flow.status = PublishStatusEnum.UNPUBLISHED
    published_flow.unpublished_at = datetime.now(timezone.utc)
    published_flow.updated_at = datetime.now(timezone.utc)

    session.add(published_flow)
    await session.commit()

    logger.info(f"Unpublished flow ID: {flow_id}")

    return {"message": "Flow unpublished successfully"}


@router.get("/all", status_code=status.HTTP_200_OK)
async def list_all_published_flows(
    session: DbSession,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search in flow name and description"),
    category: str | None = Query(None, description="Filter by category"),
    tags: str | None = Query(None, description="Filter by tags (comma-separated)"),
    sort_by: str = Query("published_at", regex="^(published_at|name)$", description="Sort by field"),
    order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
):
    """
    List ALL published flows from all users (for marketplace).
    Public endpoint - no authentication required.
    Returns paginated list with flow and publisher information.
    """
    # Base query with joins
    query = (
        select(PublishedFlow, Flow, User)
        .join(Flow, PublishedFlow.flow_id == Flow.id)
        .join(User, PublishedFlow.published_by == User.id)
        .where(PublishedFlow.status == PublishStatusEnum.PUBLISHED)
    )

    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.where(or_(Flow.name.ilike(search_pattern), PublishedFlow.description.ilike(search_pattern)))

    # Apply category filter
    if category:
        query = query.where(PublishedFlow.category == category)

    # Apply tags filter if provided
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        for tag in tag_list:
            # Use contains for JSON array - works with both PostgreSQL and SQLite
            query = query.where(PublishedFlow.tags.contains([tag]))

    # Count total before pagination
    count_query = select(func.count()).select_from(
        select(PublishedFlow.id)
        .join(Flow, PublishedFlow.flow_id == Flow.id)
        .join(User, PublishedFlow.published_by == User.id)
        .where(PublishedFlow.status == PublishStatusEnum.PUBLISHED)
    )

    # Apply same filters to count query
    if search:
        search_pattern = f"%{search}%"
        count_query = count_query.where(
            or_(Flow.name.ilike(search_pattern), PublishedFlow.description.ilike(search_pattern))
        )
    if category:
        count_query = count_query.where(PublishedFlow.category == category)
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        for tag in tag_list:
            count_query = count_query.where(PublishedFlow.tags.contains([tag]))

    total_result = await session.exec(count_query)
    total = total_result.one()

    # Apply sorting
    if sort_by == "published_at":
        order_col = PublishedFlow.published_at
    else:  # name
        order_col = Flow.name

    if order == "desc":
        query = query.order_by(order_col.desc())
    else:
        query = query.order_by(order_col.asc())

    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Execute query
    results = await session.exec(query)
    rows = results.all()

    # Format response
    items = []
    for published_flow, flow, user in rows:
        item = PublishedFlowRead.model_validate(published_flow, from_attributes=True)
        item.flow_name = flow.name
        item.flow_icon = flow.icon if flow.icon else None
        item.published_by_username = user.username
        items.append(item)

    pages = (total + limit - 1) // limit if limit > 0 else 0

    return {"items": items, "total": total, "page": page, "pages": pages}


@router.get("/check/{flow_id}", status_code=status.HTTP_200_OK)
async def check_flow_published(
    flow_id: UUID,
    session: DbSession,
):
    """
    Check if a flow is published (by original flow ID).
    Returns publication status, IDs, and metadata for pre-filling re-publish modal.
    """
    # Query by flow_cloned_from (original flow ID) and join with Flow to get cloned flow name
    query = (
        select(PublishedFlow, Flow)
        .join(Flow, PublishedFlow.flow_id == Flow.id)
        .where(PublishedFlow.flow_cloned_from == flow_id, PublishedFlow.status == PublishStatusEnum.PUBLISHED)
    )
    result = await session.exec(query)
    row = result.first()

    if row:
        published_flow, cloned_flow = row
        return {
            "is_published": True,
            "published_flow_id": str(published_flow.id),
            "cloned_flow_id": str(published_flow.flow_id),
            "published_at": published_flow.published_at.isoformat(),
            # Additional data for pre-filling modal on re-publish
            "marketplace_flow_name": cloned_flow.name,
            "version": published_flow.version,
            "category": published_flow.category,
        }

    return {
        "is_published": False,
        "published_flow_id": None,
        "cloned_flow_id": None,
        "published_at": None,
    }


@router.get("/{published_flow_id}", response_model=PublishedFlowRead, status_code=status.HTTP_200_OK)
async def get_published_flow(
    published_flow_id: UUID,
    session: DbSession,
):
    """
    Get single published flow details (public endpoint).
    Returns the flow snapshot and all metadata.
    """
    query = (
        select(PublishedFlow, Flow, User)
        .join(Flow, PublishedFlow.flow_id == Flow.id)
        .join(User, PublishedFlow.published_by == User.id)
        .where(PublishedFlow.id == published_flow_id)
    )
    result = await session.exec(query)
    row = result.first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published flow not found")

    published_flow, flow, user = row

    item = PublishedFlowRead.model_validate(published_flow, from_attributes=True)
    item.flow_name = flow.name
    item.flow_icon = flow.icon if flow.icon else None
    item.published_by_username = user.username
    item.flow_data = flow.data if flow.data else {}  # Include flow data from cloned flow

    return item


@router.get("/{published_flow_id}/spec", status_code=status.HTTP_200_OK)
async def get_published_flow_spec(
    published_flow_id: UUID,
    session: DbSession,
):
    """
    Get Genesis specification for a published flow (public endpoint).
    Converts the flow data from the cloned flow to Genesis specification format.
    """
    query = select(PublishedFlow, Flow).join(Flow, PublishedFlow.flow_id == Flow.id).where(
        PublishedFlow.id == published_flow_id
    )
    result = await session.exec(query)
    row = result.first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published flow not found")

    published_flow, flow = row

    if not flow or not flow.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cloned flow data not found")

    try:
        # Import FlowToSpecConverter
        from langflow.services.runtime.flow_to_spec_converter import FlowToSpecConverter

        # Initialize converter
        converter = FlowToSpecConverter()

        # Convert flow data from the cloned flow (not from published_flow.flow_data which no longer exists)
        spec = converter.convert_flow_to_spec(
            flow_data=flow.data,  # Use flow table data instead
            preserve_variables=True,
            include_metadata=False,
            name_override=flow.name,
            description_override=published_flow.description or flow.description,
        )

        return spec

    except Exception as e:
        msg = f"Failed to generate specification: {e}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg) from e


@router.delete("/{published_flow_id}", status_code=status.HTTP_200_OK)
async def delete_published_flow(
    published_flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Delete published flow (hard delete) - only owner can delete.
    Permanently removes the published flow from the marketplace.
    """
    query = select(PublishedFlow).where(
        PublishedFlow.id == published_flow_id, PublishedFlow.user_id == current_user.id
    )
    result = await session.exec(query)
    published_flow = result.first()

    if not published_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published flow not found or you don't have permission to delete it",
        )

    await session.delete(published_flow)
    await session.commit()

    return {"message": "Published flow deleted successfully"}
