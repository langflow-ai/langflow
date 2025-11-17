"""Published Flows API endpoints for marketplace functionality."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import cast, func, or_, Text, update
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.flows import clone_flow_for_marketplace
from langflow.initial_setup.setup import get_or_create_marketplace_agent_folder
from langflow.interface.components import get_and_cache_all_types_dict
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.published_flow.model import (
    PublishedFlow,
    PublishedFlowCreate,
    PublishedFlowRead,
    PublishStatusEnum,
)
from langflow.services.database.models.published_flow_input_sample.model import (
    PublishedFlowInputSample,
    PublishedFlowInputSampleRead,
)
from langflow.services.database.models.published_flow_version.model import (
    PublishedFlowVersion,
    PublishedFlowVersionRead,
    RevertToVersionResponse,
)
from langflow.services.database.models.user.model import User
from langflow.services.auth.permissions import can_edit_flow, get_user_roles_from_request
from langflow.services.deps import get_settings_service
from langflow.services.vector_database import VectorDatabaseService
from langflow.spec_flow_builder.yaml_exporter import FlowToYamlConverter
from langflow.logging import logger

router = APIRouter(prefix="/published-flows", tags=["Published Flows"])


async def _store_flow_in_vector_db(
    flow: Flow,
    marketplace_name: str,
    description: str,
    tags: list[str],
) -> None:
    """
    Store flow YAML in vector database for semantic search.

    This is a non-blocking operation - failures are logged but don't affect publishing.

    Args:
        flow: The cloned flow to store
        marketplace_name: Name used in marketplace
        description: Flow description
        tags: Tags for categorization
    """
    try:
        logger.info(f"Storing flow {flow.id} in vector database")

        # Step 1: Get component catalog
        settings_service = get_settings_service()
        all_components = await get_and_cache_all_types_dict(settings_service)

        # Step 2: Convert flow to YAML
        converter = FlowToYamlConverter(all_components)
        flow_data = {
            "id": str(flow.id),
            "name": marketplace_name,
            "description": description or "",
            "data": flow.data,
        }
        yaml_content = await converter.convert_flow_to_yaml(flow_data)

        # Step 3: Extract component types from flow data
        component_types = []
        if flow.data and "nodes" in flow.data:
            for node in flow.data["nodes"]:
                node_data = node.get("data", {})
                node_info = node_data.get("node", {})
                display_name = node_info.get("display_name", "")
                if display_name:
                    component_types.append(display_name)

        # Remove duplicates
        component_types = list(set(component_types))

        # Step 4: Store in vector DB
        vector_service = VectorDatabaseService()
        success = vector_service.store_flow(
            flow_id=str(flow.id),
            flow_name=marketplace_name,
            yaml_content=yaml_content,
            description=description or "",
            components=component_types,
            tags=tags or []
        )

        if success:
            logger.info(f"Successfully stored flow {flow.id} in vector database")
        else:
            logger.warning(f"Vector DB storage returned False for flow {flow.id}")

    except Exception as e:
        # Log error but don't fail the publish operation
        logger.error(f"Failed to store flow {flow.id} in vector database: {e}", exc_info=True)


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

    Naming convention:
    - Original flow: "{marketplace_name}"
    - Cloned flow: "{marketplace_name}-Published-{version}"
    - Published table: "{marketplace_name}" (base name only)
    """
    try:
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

        # 3. Validate marketplace name doesn't already exist
        marketplace_name = payload.marketplace_flow_name.strip()
        if not marketplace_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Marketplace flow name is required",
            )

        # Check for duplicate names (exclude current flow if re-publishing)
        duplicate_query = select(PublishedFlow).where(
            PublishedFlow.flow_name == marketplace_name,
            PublishedFlow.status == PublishStatusEnum.PUBLISHED,
            PublishedFlow.flow_cloned_from != flow_id,  # Exclude current flow
        )
        duplicate_result = await session.exec(duplicate_query)
        if duplicate_result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A flow with the name '{marketplace_name}' already exists in the marketplace",
            )

        # 4. Use Marketplace Agent folder for the cloned flow
        marketplace_folder = await get_or_create_marketplace_agent_folder(session)
        target_folder_id = marketplace_folder.id

        # 5. Check if already published (by flow_cloned_from)
        existing_result = await session.exec(
            select(PublishedFlow).where(PublishedFlow.flow_cloned_from == flow_id)
        )
        existing = existing_result.first()

        if existing:
            # RE-PUBLISH: Create new version with versioning support

            # Step 1: Validate version uniqueness for this original flow
            version_check_query = select(PublishedFlowVersion).where(
                PublishedFlowVersion.flow_id_cloned_from == flow_id,
                PublishedFlowVersion.version == payload.version
            )
            version_check_result = await session.exec(version_check_query)
            if version_check_result.first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Version '{payload.version}' already exists for this flow. Please use a unique version."
                )

            # Step 2: Clone flow with new version (create new cloned flow for this version)
            new_cloned_flow = await clone_flow_for_marketplace(
                session=session,
                original_flow=original_flow,
                target_folder_id=target_folder_id,
                user_id=current_user.id,
                marketplace_flow_name=f"{marketplace_name}-Published-{payload.version}",  # Include version in name
                tags=payload.tags,
                description=payload.description,
            )

            # Step 3: Update original flow name (keep consistent naming)
            original_flow.name = marketplace_name
            original_flow.tags = payload.tags

            # Step 4: Deactivate all previous versions for this published_flow
            await session.exec(
                update(PublishedFlowVersion)
                .where(PublishedFlowVersion.published_flow_id == existing.id)
                .values(active=False)
            )

            # Clear all drafted flags for this flow before setting new one
            await session.exec(
                update(PublishedFlowVersion)
                .where(PublishedFlowVersion.flow_id_cloned_from == flow_id)
                .values(drafted=False)
            )

            # Step 5: Update published_flow record to point to new cloned flow
            existing.flow_id = new_cloned_flow.id  # Point to new cloned flow
            existing.version = payload.version  # Update to new version
            existing.tags = payload.tags
            existing.description = payload.description or original_flow.description
            existing.flow_name = marketplace_name
            existing.flow_icon = payload.flow_icon or existing.flow_icon
            if payload.flow_icon and payload.flow_icon != existing.flow_icon:
                existing.flow_icon_updated_at = datetime.now(timezone.utc)
            existing.published_by = current_user.id
            existing.published_by_username = current_user.username
            existing.published_at = datetime.now(timezone.utc)
            existing.updated_at = datetime.now(timezone.utc)
            existing.status = PublishStatusEnum.PUBLISHED

            # Step 6: Create new version record
            new_version = PublishedFlowVersion(
                version=payload.version,
                flow_id_cloned_to=new_cloned_flow.id,
                flow_id_cloned_from=flow_id,
                published_flow_id=existing.id,
                flow_name=marketplace_name,
                flow_icon=payload.flow_icon or existing.flow_icon,
                description=payload.description or original_flow.description,
                tags=payload.tags,
                active=True,
                drafted=True,
                published_by=current_user.id,
                published_at=datetime.now(timezone.utc),
            )

            session.add(new_cloned_flow)
            session.add(existing)
            session.add(original_flow)
            session.add(new_version)
            
            # Create PublishedFlowInputSample record if sample data is provided
            if any([payload.storage_account, payload.container_name, payload.file_names, payload.sample_text, payload.sample_output]):
                input_sample = PublishedFlowInputSample(
                    published_flow_id=existing.id,
                    storage_account=payload.storage_account,
                    container_name=payload.container_name,
                    file_names=payload.file_names,
                    sample_text=payload.sample_text,
                    sample_output=payload.sample_output,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(input_sample)
            
            await session.flush()  # Added explicit flush
            await session.commit()
            await session.refresh(existing)

            # Eager-load input_samples to avoid async lazy-load during Pydantic serialization
            existing_with_samples_result = await session.exec(
                select(PublishedFlow)
                .options(joinedload(PublishedFlow.input_samples))
                .where(PublishedFlow.id == existing.id)
            )
            existing_with_samples = existing_with_samples_result.first() or existing

            logger.info(f"Re-published flow '{original_flow.name}' (ID: {flow_id}) as version '{payload.version}'")

            # Store in vector database (non-blocking)
            await _store_flow_in_vector_db(
                flow=new_cloned_flow,
                marketplace_name=marketplace_name,
                description=payload.description or original_flow.description or "",
                tags=payload.tags or []
            )

            result_data = PublishedFlowRead.model_validate(existing_with_samples, from_attributes=True)
            return result_data

        # NEW PUBLISH: Clone flow and create published_flow record with first version
        cloned_flow = await clone_flow_for_marketplace(
            session=session,
            original_flow=original_flow,
            target_folder_id=target_folder_id,
            user_id=current_user.id,
            marketplace_flow_name=f"{marketplace_name}-Published-{payload.version}",  # Include version in name
            tags=payload.tags,
            description=payload.description,
        )

        # Update original flow name to marketplace name
        original_flow.name = marketplace_name
        original_flow.tags = payload.tags

        # Create published_flow record
        published_flow = PublishedFlow(
            flow_id=cloned_flow.id,
            flow_cloned_from=flow_id,
            user_id=current_user.id,
            published_by=current_user.id,
            status=PublishStatusEnum.PUBLISHED,
            version=payload.version,
            tags=payload.tags,
            description=payload.description or original_flow.description,
            flow_name=marketplace_name,
            flow_icon=payload.flow_icon,
            flow_icon_updated_at=datetime.now(timezone.utc) if payload.flow_icon else None,
            published_by_username=current_user.username,
            published_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        session.add(published_flow)
        session.add(original_flow)
        await session.flush()  # Added explicit flush
        await session.commit()
        await session.refresh(published_flow)

        # Clear all drafted flags for this flow (in case there are any old versions)
        await session.exec(
            update(PublishedFlowVersion)
            .where(PublishedFlowVersion.flow_id_cloned_from == flow_id)
            .values(drafted=False)
        )

        # Create first version record
        first_version = PublishedFlowVersion(
            version=payload.version,
            flow_id_cloned_to=cloned_flow.id,
            flow_id_cloned_from=flow_id,
            published_flow_id=published_flow.id,
            flow_name=marketplace_name,
            flow_icon=payload.flow_icon,
            description=payload.description or original_flow.description,
            tags=payload.tags,
            active=True,
            drafted=True,
            published_by=current_user.id,
            published_at=datetime.now(timezone.utc),
        )

        session.add(first_version)
        
        # Create PublishedFlowInputSample record if sample data is provided
        if any([payload.storage_account, payload.container_name, payload.file_names, payload.sample_text, payload.sample_output]):
            input_sample = PublishedFlowInputSample(
                published_flow_id=published_flow.id,
                storage_account=payload.storage_account,
                container_name=payload.container_name,
                file_names=payload.file_names,
                sample_text=payload.sample_text,
                sample_output=payload.sample_output,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(input_sample)
        
        await session.flush()  # Added explicit flush
        await session.commit()

        logger.info(f"Published flow as '{marketplace_name}' version '{payload.version}' (Original ID: {flow_id})")

        # Store in vector database (non-blocking)
        await _store_flow_in_vector_db(
            flow=cloned_flow,
            marketplace_name=marketplace_name,
            description=payload.description or original_flow.description or "",
            tags=payload.tags or []
        )

        # Eager-load input_samples to avoid async lazy-load during Pydantic serialization
        published_with_samples_result = await session.exec(
            select(PublishedFlow)
            .options(joinedload(PublishedFlow.input_samples))
            .where(PublishedFlow.id == published_flow.id)
        )
        published_with_samples = published_with_samples_result.first() or published_flow

        result_data = PublishedFlowRead.model_validate(published_with_samples, from_attributes=True)
        return result_data
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        await session.rollback()
        raise
    except Exception as e:
        # Roll back on any other exception
        await session.rollback()
        logger.error(f"Error publishing flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish flow: {str(e)}"
        )

@router.post("/unpublish/{flow_id}", status_code=status.HTTP_200_OK)
async def unpublish_flow(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Unpublish a flow and deactivate ALL its versions.
    Soft delete - changes status to UNPUBLISHED.
    No permission check - any authenticated user can unpublish.
    """
    # Query by flow_cloned_from instead of flow_id
    query = select(PublishedFlow).where(
        PublishedFlow.flow_cloned_from == flow_id
    )
    result = await session.exec(query)
    published_flow = result.first()

    if not published_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published flow not found",
        )

    # Update status to UNPUBLISHED
    published_flow.status = PublishStatusEnum.UNPUBLISHED
    published_flow.unpublished_at = datetime.now(timezone.utc)
    published_flow.updated_at = datetime.now(timezone.utc)

    session.add(published_flow)

    # Deactivate ALL versions for this published_flow
    await session.exec(
        update(PublishedFlowVersion)
        .where(PublishedFlowVersion.published_flow_id == published_flow.id)
        .values(active=False)
    )

    await session.commit()

    logger.info(f"Unpublished flow ID: {flow_id} and deactivated all versions")

    return {"message": "Flow unpublished successfully and all versions deactivated"}


@router.get("/{flow_id}/versions", response_model=list[PublishedFlowVersionRead], status_code=status.HTTP_200_OK)
async def get_flow_versions(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Get all published versions for a flow (for version dropdown).
    Returns versions ordered by published_at ascending (v1, v2, v3...).
    Active version is marked with active=True.
    No permission check - any authenticated user can view versions.
    """
    # Check if flow exists
    original_flow = await session.get(Flow, flow_id)
    if not original_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found",
        )

    # Get all versions for this original flow
    query = select(PublishedFlowVersion).where(
        PublishedFlowVersion.flow_id_cloned_from == flow_id
    ).order_by(PublishedFlowVersion.published_at.asc())  # Oldest first (v1, v2, v3...)

    result = await session.exec(query)
    versions = result.all()

    if not versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No published versions found for this flow",
        )

    return [PublishedFlowVersionRead.model_validate(v, from_attributes=True) for v in versions]


@router.post("/revert/{flow_id}/{version_id}", response_model=RevertToVersionResponse, status_code=status.HTTP_200_OK)
async def revert_to_version(
    flow_id: UUID,
    version_id: int,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Revert original flow to a specific version by cloning version's data.
    This REPLACES the original flow's data with the selected version's data.
    User can then edit and publish as a new version.
    No permission check - any authenticated user can revert.
    """
    # Get the version record
    version = await session.get(PublishedFlowVersion, version_id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    # Validate version belongs to this flow
    if version.flow_id_cloned_from != flow_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Version does not belong to this flow",
        )

    # Get the original flow
    original_flow = await session.get(Flow, flow_id)
    if not original_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original flow not found",
        )

    # Get the versioned flow data
    versioned_flow = await session.get(Flow, version.flow_id_cloned_to)
    if not versioned_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Versioned flow data not found",
        )

    # Replace original flow's data with versioned flow's data
    import copy
    original_flow.data = copy.deepcopy(versioned_flow.data) if versioned_flow.data else {}
    original_flow.description = versioned_flow.description
    original_flow.icon = versioned_flow.icon
    original_flow.updated_at = datetime.now(timezone.utc)

    session.add(original_flow)

    # Update drafted flags: set all versions to drafted=False for this flow
    await session.exec(
        update(PublishedFlowVersion)
        .where(PublishedFlowVersion.flow_id_cloned_from == flow_id)
        .values(drafted=False)
    )

    # Set the reverted version as drafted
    version.drafted = True
    session.add(version)

    await session.commit()
    await session.refresh(original_flow)

    logger.info(f"Reverted flow {flow_id} to version {version.version} (version_id: {version_id}), marked as drafted")

    return RevertToVersionResponse(
        message=f"Successfully reverted to version {version.version}",
        version=version.version,
        flow_id=flow_id,
        cloned_flow_id=version.flow_id_cloned_to,
    )


@router.get("/all", status_code=status.HTTP_200_OK)
async def list_all_published_flows(
    session: DbSession,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search in flow name and description"),
    category: str | None = Query(None, description="Filter by category"),
    tags: str | None = Query(None, description="Filter by tags (comma-separated)"),
    status_filter: str | None = Query(None, regex="^(published|unpublished|all)$", description="Filter by status"),
    sort_by: str = Query("published_at", regex="^(published_at|name|date|tags)$", description="Sort by field"),
    order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
):
    """
    List ALL published flows from all users (for marketplace).
    Public endpoint - no authentication required.
    Returns paginated list with denormalized flow and publisher information.
    """
    # Base query - apply status filter
    if status_filter == "published":
        query = (
            select(PublishedFlow)
            .options(selectinload(PublishedFlow.input_samples))
            .where(PublishedFlow.status == PublishStatusEnum.PUBLISHED)
        )
    elif status_filter == "unpublished":
        query = (
            select(PublishedFlow)
            .options(selectinload(PublishedFlow.input_samples))
            .where(PublishedFlow.status == PublishStatusEnum.UNPUBLISHED)
        )
    else:  # "all" or None - show all flows (default)
        query = select(PublishedFlow).options(selectinload(PublishedFlow.input_samples))

    # Apply search filter on denormalized flow_name and description
    if search:
        search_pattern = f"%{search}%"
        query = query.where(or_(PublishedFlow.flow_name.ilike(search_pattern), PublishedFlow.description.ilike(search_pattern)))

    # Apply category filter
    if category:
        query = query.where(PublishedFlow.category == category)

    # Apply tags filter if provided
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        for tag in tag_list:
            # Cast JSON to text and check if tag is in the stringified array
            # Works with both PostgreSQL and SQLite
            query = query.where(cast(PublishedFlow.tags, Text).contains(f'"{tag}"'))

    # Count total with same status filter
    if status_filter == "published":
        count_query = select(func.count(PublishedFlow.id)).where(PublishedFlow.status == PublishStatusEnum.PUBLISHED)
    elif status_filter == "unpublished":
        count_query = select(func.count(PublishedFlow.id)).where(PublishedFlow.status == PublishStatusEnum.UNPUBLISHED)
    else:  # "all" or None - count all flows (default)
        count_query = select(func.count(PublishedFlow.id))

    # Apply same filters to count query
    if search:
        search_pattern = f"%{search}%"
        count_query = count_query.where(
            or_(PublishedFlow.flow_name.ilike(search_pattern), PublishedFlow.description.ilike(search_pattern))
        )
    if category:
        count_query = count_query.where(PublishedFlow.category == category)
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        for tag in tag_list:
            # Cast JSON to text and check if tag is in the stringified array
            count_query = count_query.where(cast(PublishedFlow.tags, Text).contains(f'"{tag}"'))

    total_result = await session.exec(count_query)
    total = total_result.one()

    # Apply sorting on denormalized fields
    if sort_by == "published_at" or sort_by == "date":
        order_col = PublishedFlow.published_at
    elif sort_by == "name":
        # Case-insensitive sorting by name
        order_col = func.lower(PublishedFlow.flow_name)
    elif sort_by == "tags":
        # Sort by tags JSON textual representation for portability (SQLite/PostgreSQL)
        # Using lower() for case-insensitive comparison across databases
        order_col = func.lower(cast(PublishedFlow.tags, Text))

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

    # Format response - all fields already denormalized in PublishedFlow
    items = [PublishedFlowRead.model_validate(published_flow, from_attributes=True) for published_flow in rows]

    pages = (total + limit - 1) // limit if limit > 0 else 0

    return {"items": items, "total": total, "page": page, "pages": pages}


@router.post("/validate-name", status_code=status.HTTP_200_OK)
async def validate_marketplace_name(
    payload: dict,
    session: DbSession,
):
    """
    Validate if a marketplace flow name already exists.
    Checks both published_flow table (marketplace) and flow table (all flows).
    Returns whether the name is available for use.
    """
    marketplace_name = payload.get("marketplace_flow_name", "").strip()
    exclude_flow_id = payload.get("exclude_flow_id")  # Flow ID to exclude (for re-publishing)

    if not marketplace_name:
        return {"exists": False, "available": True}

    # Step 1: Check if name exists in published flows (marketplace)
    published_query = select(PublishedFlow).where(
        PublishedFlow.flow_name == marketplace_name,
        PublishedFlow.status == PublishStatusEnum.PUBLISHED,
    )

    # If re-publishing, exclude the current flow
    if exclude_flow_id:
        try:
            exclude_uuid = UUID(exclude_flow_id)
            published_query = published_query.where(PublishedFlow.flow_cloned_from != exclude_uuid)
        except (ValueError, TypeError):
            pass  # Invalid UUID, ignore

    published_result = await session.exec(published_query)
    published_exists = published_result.first()

    if published_exists:
        return {
            "exists": True,
            "available": False,
            "message": f"A flow with the name '{marketplace_name}' already exists in the marketplace",
        }

    # Step 2: Check if name exists in flow table (all flows)
    flow_query = select(Flow).where(Flow.name == marketplace_name)

    # Exclude the current flow
    if exclude_flow_id:
        try:
            exclude_uuid = UUID(exclude_flow_id)
            flow_query = flow_query.where(Flow.id != exclude_uuid)
        except (ValueError, TypeError):
            pass  # Invalid UUID, ignore

    flow_result = await session.exec(flow_query)
    flow_exists = flow_result.first()

    if flow_exists:
        return {
            "exists": True,
            "available": False,
            "message": f"A flow with the name '{marketplace_name}' already exists. Please choose a different name.",
        }

    return {"exists": False, "available": True}


@router.get("/check/{flow_id}", status_code=status.HTTP_200_OK)
async def check_flow_published(
    flow_id: UUID,
    session: DbSession,
):
    """
    Check if a flow is published (by original flow ID).
    Returns publication status, IDs, and metadata for pre-filling re-publish modal.
    """
    # Query by flow_cloned_from (original flow ID)
    # Include both PUBLISHED and UNPUBLISHED to allow pre-filling data for re-publishing
    query = select(PublishedFlow).where(PublishedFlow.flow_cloned_from == flow_id)
    result = await session.exec(query)
    published_flow = result.first()

    if published_flow:
        return {
            "is_published": published_flow.status == PublishStatusEnum.PUBLISHED,
            "published_flow_id": str(published_flow.id),
            "cloned_flow_id": str(published_flow.flow_id),
            "published_at": published_flow.published_at.isoformat(),
            # Additional data for pre-filling modal on re-publish (works for both published and unpublished)
            # Use flow_name from published_flow table, not the cloned flow's actual name
            "marketplace_flow_name": published_flow.flow_name,
            "version": published_flow.version,
            "tags": published_flow.tags,
            "description": published_flow.description,
            "flow_icon": published_flow.flow_icon,
            "flow_icon_updated_at": published_flow.flow_icon_updated_at.isoformat() if published_flow.flow_icon_updated_at else None,
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
        .options(selectinload(PublishedFlow.input_samples))
        .join(Flow, PublishedFlow.flow_id == Flow.id)
        .join(User, PublishedFlow.published_by == User.id)
        .where(PublishedFlow.id == published_flow_id)
    )
    result = await session.exec(query)
    row = result.first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Published flow not found")

    published_flow, flow, user = row

    # Load input samples for this published flow
    input_samples_query = select(PublishedFlowInputSample).where(
        PublishedFlowInputSample.published_flow_id == published_flow_id
    )
    input_samples_result = await session.exec(input_samples_query)
    input_samples = input_samples_result.all()

    item = PublishedFlowRead.model_validate(published_flow, from_attributes=True)
    item.flow_name = published_flow.flow_name
    item.flow_icon = published_flow.flow_icon or (flow.icon if flow.icon else None)
    # item.flow_icon = published_flow.icon if published_flow.icon else None
    item.published_by_username = user.username
    item.flow_data = flow.data if flow.data else {}  # Include flow data from cloned flow
    item.input_samples = [
        PublishedFlowInputSampleRead.model_validate(s, from_attributes=True)
        for s in input_samples
    ]  # Include input samples as Read schema

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


# ---------------------------
# Input Sample Management
# ---------------------------

@router.patch("/input-samples/{sample_id}", response_model=PublishedFlowInputSampleRead, status_code=status.HTTP_200_OK)
async def patch_input_sample(
    sample_id: UUID,
    payload: dict,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Update editable fields of a PublishedFlowInputSample.

    Allowed updates:
    - sample_text (list[str])
    - sample_output (dict)

    file_names are immutable via PATCH and must be removed via DELETE endpoints.
    """
    # Fetch sample
    sample = await session.get(PublishedFlowInputSample, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input sample not found")

    # Permission: only owner of published flow can edit
    published_flow = await session.get(PublishedFlow, sample.published_flow_id)
    if not published_flow or published_flow.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit this input sample")

    # Apply updates (only allowed keys)
    updated = False
    if "sample_text" in payload:
        val = payload.get("sample_text")
        if val is not None and not isinstance(val, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sample_text must be a list of strings or null")
        sample.sample_text = val
        updated = True
    if "sample_output" in payload:
        val = payload.get("sample_output")
        if val is not None and not isinstance(val, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sample_output must be an object or null")
        sample.sample_output = val
        updated = True

    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields to update")

    sample.updated_at = datetime.now(timezone.utc)
    session.add(sample)
    await session.commit()
    await session.refresh(sample)

    return PublishedFlowInputSampleRead.model_validate(sample, from_attributes=True)


@router.delete("/input-samples/{sample_id}", status_code=status.HTTP_200_OK)
async def delete_input_sample(
    sample_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Delete an entire PublishedFlowInputSample record. Only the owner of the published flow can delete.
    """
    sample = await session.get(PublishedFlowInputSample, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input sample not found")

    published_flow = await session.get(PublishedFlow, sample.published_flow_id)
    if not published_flow or published_flow.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this input sample")

    await session.delete(sample)
    await session.commit()

    return {"message": "Input sample deleted successfully"}


@router.delete("/input-samples/{sample_id}/file", status_code=status.HTTP_200_OK)
async def delete_input_sample_file(
    sample_id: UUID,
    name: Annotated[str, Query(min_length=1, description="Exact file path or name to remove")],
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Remove a single file entry from the input sample's file_names list.
    Matches exact string equality on the stored value.
    """
    sample = await session.get(PublishedFlowInputSample, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input sample not found")

    published_flow = await session.get(PublishedFlow, sample.published_flow_id)
    if not published_flow or published_flow.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this input sample")

    file_names = sample.file_names or []
    new_files = [f for f in file_names if f != name]
    if len(new_files) == len(file_names):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File entry not found in sample")

    sample.file_names = new_files if new_files else None
    sample.updated_at = datetime.now(timezone.utc)
    session.add(sample)
    await session.commit()
    await session.refresh(sample)

    return PublishedFlowInputSampleRead.model_validate(sample, from_attributes=True)


@router.delete("/input-samples/{sample_id}/text", status_code=status.HTTP_200_OK)
async def delete_input_sample_text(
    sample_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    index: int | None = Query(default=None, ge=0, description="Index of the text entry to remove"),
    value: str | None = Query(default=None, description="Exact text value to remove (first occurrence)"),    
):
    """
    Remove a text entry from the input sample's sample_text list.
    You can specify either an index or a value; if both are provided, index takes precedence.
    """
    sample = await session.get(PublishedFlowInputSample, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input sample not found")

    published_flow = await session.get(PublishedFlow, sample.published_flow_id)
    if not published_flow or published_flow.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this input sample")

    texts = sample.sample_text or []
    if not texts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No sample_text entries to remove")

    removed = False
    if index is not None:
        if index < 0 or index >= len(texts):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Index out of range")
        texts.pop(index)
        removed = True
    elif value is not None:
        try:
            texts.remove(value)
            removed = True
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Text value not found")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide index or value to remove")

    sample.sample_text = texts if texts else None
    sample.updated_at = datetime.now(timezone.utc)
    session.add(sample)
    await session.commit()
    await session.refresh(sample)

    return PublishedFlowInputSampleRead.model_validate(sample, from_attributes=True)
