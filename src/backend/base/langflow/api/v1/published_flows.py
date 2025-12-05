"""Published Flows API endpoints for marketplace functionality."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import cast, func, or_, Text, update
from sqlalchemy.orm import joinedload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
# from langflow.interface.components import get_and_cache_all_types_dict  # Disabled - used by vector DB storage
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.published_flow.model import (
    PublishedFlow,
    PublishedFlowCreate,
    PublishedFlowRead,
    PublishStatusEnum,
)
# Note: PublishedFlowInputSample is deprecated - using VersionFlowInputSample instead
from langflow.services.database.models.published_flow_version.model import (
    PublishedFlowVersion,
    PublishedFlowVersionRead,
    RevertToVersionResponse,
)
from langflow.services.database.models.user.model import User
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_status.model import FlowStatus, FlowStatusEnum
from langflow.services.auth.permissions import can_edit_flow, get_user_roles_from_request, has_marketplace_admin_role
from langflow.services.database.models.version_flow_input_sample.model import VersionFlowInputSample
from langflow.services.auth.utils import get_user_info_from_auth_token, require_marketplace_admin
from langflow.services.deps import get_settings_service
# from langflow.services.vector_database import VectorDatabaseService  # Disabled - may use in future
# from langflow.spec_flow_builder.yaml_exporter import FlowToYamlConverter  # Disabled - used by vector DB storage
from langflow.logging import logger
from langflow.api.v1.flows import clone_flow_for_marketplace
from langflow.initial_setup.setup import get_or_create_marketplace_agent_folder

router = APIRouter(prefix="/published-flows", tags=["Published Flows"])


# ============================================================================
# Helper Functions for Publishing Flow Operations
# ============================================================================


async def _validate_marketplace_name(
    session: AsyncSession,
    marketplace_name: str,
    exclude_flow_id: UUID,
) -> None:
    """
    Validate marketplace name is not empty and not a duplicate.

    Args:
        session: Database session
        marketplace_name: The marketplace name to validate
        exclude_flow_id: Flow ID to exclude from duplicate check (for re-publishing)

    Raises:
        HTTPException: If name is empty or duplicate exists
    """
    if not marketplace_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marketplace flow name is required",
        )

    duplicate_query = select(PublishedFlow).where(
        PublishedFlow.flow_name == marketplace_name,
        PublishedFlow.status == PublishStatusEnum.PUBLISHED,
        PublishedFlow.flow_cloned_from != exclude_flow_id,
    )
    duplicate_result = await session.exec(duplicate_query)
    if duplicate_result.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A flow with the name '{marketplace_name}' already exists in the marketplace",
        )


async def _get_flow_statuses(session: AsyncSession) -> dict[str, FlowStatus]:
    """
    Fetch all flow statuses from database.

    Args:
        session: Database session

    Returns:
        Dict mapping status_name to FlowStatus object

    Raises:
        HTTPException: If Published status not found
    """
    status_query = select(FlowStatus)
    status_results = await session.exec(status_query)
    all_statuses = {s.status_name: s for s in status_results.all()}

    if FlowStatusEnum.PUBLISHED.value not in all_statuses:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Published status not found in database",
        )

    return all_statuses


async def _get_flow_versions(
    session: AsyncSession,
    flow_id: UUID,
) -> tuple[list, FlowVersion | None]:
    """
    Get all versions for a flow.

    Args:
        session: Database session
        flow_id: Original flow ID

    Returns:
        Tuple of (all_versions, latest_version)
    """
    flow_version_query = (
        select(FlowVersion)
        .where(FlowVersion.original_flow_id == flow_id)
        .options(joinedload(FlowVersion.status))
        .order_by(FlowVersion.created_at.desc())
    )
    flow_version_results = await session.exec(flow_version_query)
    all_versions = flow_version_results.all()
    latest_version = all_versions[0] if all_versions else None

    return all_versions, latest_version


async def _unpublish_existing_versions(
    session: AsyncSession,
    versions: list[FlowVersion],
    published_status: FlowStatus,
    unpublished_status: FlowStatus | None,
    flow_id: UUID,
) -> None:
    """
    Mark all currently published versions as unpublished.

    Args:
        session: Database session
        versions: List of FlowVersion objects
        published_status: The Published FlowStatus
        unpublished_status: The Unpublished FlowStatus (can be None)
        flow_id: Flow ID for logging
    """
    if not unpublished_status or not versions:
        return

    for version in versions:
        if version.status_id == published_status.id:
            logger.info(f"Unpublishing old version {version.version} for flow {flow_id}")
            version.status_id = unpublished_status.id
            version.updated_at = datetime.now(timezone.utc)
            session.add(version)


def _create_new_flow_version(
    flow_id: UUID,
    cloned_flow_id: UUID,
    payload: PublishedFlowCreate,
    published_status_id: UUID,
    user_id: UUID,
    user_info: dict,
) -> FlowVersion:
    """
    Create a new FlowVersion record with Published status.

    Args:
        flow_id: Original flow ID
        cloned_flow_id: Cloned flow ID
        payload: Publish payload
        published_status_id: Published status ID
        user_id: Current user ID
        user_info: User info dict with name/email

    Returns:
        New FlowVersion object (not yet added to session)
    """
    return FlowVersion(
        original_flow_id=flow_id,
        version_flow_id=cloned_flow_id,
        version=payload.version,
        title=payload.marketplace_flow_name,
        description=payload.description,
        tags=payload.tags,
        agent_logo=payload.flow_icon,
        status_id=published_status_id,
        published_by=user_id,
        published_by_name=user_info.get("name"),
        published_by_email=user_info.get("email"),
        published_at=datetime.now(timezone.utc),
        submitted_by=user_id,
        submitted_by_name=user_info.get("name"),
        submitted_by_email=user_info.get("email"),
        submitted_at=datetime.now(timezone.utc),
    )


def _update_flow_version_to_published(
    flow_version: FlowVersion,
    payload: PublishedFlowCreate,
    published_status_id: UUID,
    user_id: UUID,
    user_info: dict,
) -> FlowVersion:
    """
    Update an existing FlowVersion to Published status.

    Args:
        flow_version: Existing FlowVersion to update
        payload: Publish payload
        published_status_id: Published status ID
        user_id: Current user ID
        user_info: User info dict with name/email

    Returns:
        Updated FlowVersion object
    """
    flow_version.status_id = published_status_id
    flow_version.version = payload.version
    flow_version.title = payload.marketplace_flow_name
    flow_version.description = payload.description
    flow_version.tags = payload.tags
    flow_version.agent_logo = payload.flow_icon
    flow_version.published_by = user_id
    flow_version.published_by_name = user_info.get("name")
    flow_version.published_by_email = user_info.get("email")
    flow_version.published_at = datetime.now(timezone.utc)
    flow_version.updated_at = datetime.now(timezone.utc)

    return flow_version


async def _update_or_create_published_flow(
    session: AsyncSession,
    flow_id: UUID,
    cloned_flow_id: UUID,
    payload: PublishedFlowCreate,
    original_flow: Flow,
    current_user: User,
) -> PublishedFlow:
    """
    Create or update the PublishedFlow record.

    Args:
        session: Database session
        flow_id: Original flow ID
        cloned_flow_id: Cloned flow ID
        payload: Publish payload
        original_flow: Original Flow object
        current_user: Current user

    Returns:
        PublishedFlow object
    """
    existing_published_query = select(PublishedFlow).where(PublishedFlow.flow_cloned_from == flow_id)
    existing_published_result = await session.exec(existing_published_query)
    existing_published = existing_published_result.first()

    marketplace_name = payload.marketplace_flow_name.strip()

    if existing_published:
        # Update existing PublishedFlow record using explicit UPDATE
        stmt = (
            update(PublishedFlow)
            .where(PublishedFlow.id == existing_published.id)
            .values(
                flow_id=cloned_flow_id,
                version=payload.version,
                tags=payload.tags,
                description=payload.description or original_flow.description,
                flow_name=marketplace_name,
                flow_icon=payload.flow_icon or existing_published.flow_icon,
                flow_icon_updated_at=datetime.now(timezone.utc) if payload.flow_icon and payload.flow_icon != existing_published.flow_icon else existing_published.flow_icon_updated_at,
                published_by=current_user.id,
                published_by_username=current_user.username,
                published_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                status=PublishStatusEnum.PUBLISHED,
            )
        )
        await session.exec(stmt)
        return existing_published
    else:
        # Create new PublishedFlow record
        published_flow = PublishedFlow(
            flow_id=cloned_flow_id,
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
        return published_flow


async def _handle_input_sample(
    session: AsyncSession,
    flow_id: UUID,
    flow_version: FlowVersion,
    payload: PublishedFlowCreate,
) -> None:
    """
    Create or update the VersionFlowInputSample.

    Args:
        session: Database session
        flow_id: Original flow ID
        flow_version: FlowVersion object
        payload: Publish payload
    """
    if not any([payload.storage_account, payload.container_name, payload.file_names, payload.sample_text, payload.sample_output]):
        return

    # Check if sample exists for this version
    existing_sample_query = select(VersionFlowInputSample).where(
        VersionFlowInputSample.original_flow_id == flow_id,
        VersionFlowInputSample.version == payload.version,
    )
    existing_sample_result = await session.exec(existing_sample_query)
    existing_sample = existing_sample_result.first()

    if existing_sample:
        # Update existing sample
        existing_sample.storage_account = payload.storage_account
        existing_sample.container_name = payload.container_name
        existing_sample.file_names = payload.file_names
        existing_sample.sample_text = payload.sample_text
        existing_sample.sample_output = payload.sample_output
        existing_sample.updated_at = datetime.now(timezone.utc)
        session.add(existing_sample)
    else:
        # Create new sample
        input_sample = VersionFlowInputSample(
            flow_version_id=flow_version.id,
            original_flow_id=flow_id,
            version=payload.version,
            storage_account=payload.storage_account,
            container_name=payload.container_name,
            file_names=payload.file_names,
            sample_text=payload.sample_text,
            sample_output=payload.sample_output,
        )
        session.add(input_sample)
        await session.flush()
        # Update flow_version with sample_id
        flow_version.sample_id = input_sample.id
        session.add(flow_version)


def _update_original_flow_metadata(
    original_flow: Flow,
    payload: PublishedFlowCreate,
) -> None:
    """
    Update the original flow's metadata.

    Args:
        original_flow: Original Flow object
        payload: Publish payload
    """
    marketplace_name = payload.marketplace_flow_name.strip()
    original_flow.name = marketplace_name
    original_flow.tags = payload.tags
    original_flow.description = payload.description or original_flow.description
    original_flow.locked = False


async def _get_or_validate_cloned_flow(
    session: AsyncSession,
    version_flow_id: UUID | None,
    status_name: str,
) -> Flow:
    """
    Get and validate the cloned flow from a flow version.

    Args:
        session: Database session
        version_flow_id: The version_flow_id from FlowVersion
        status_name: Status name for error messages

    Returns:
        The cloned Flow object

    Raises:
        HTTPException: If version_flow_id is None or flow not found
    """
    if not version_flow_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{status_name} flow version does not have a cloned flow",
        )

    cloned_flow = await session.get(Flow, version_flow_id)
    if not cloned_flow:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cloned flow not found",
        )

    return cloned_flow


async def _handle_version_by_status(
    session: AsyncSession,
    original_flow: Flow,
    latest_version: FlowVersion | None,
    statuses: dict[str, FlowStatus],
    marketplace_folder,
    payload: PublishedFlowCreate,
    current_user: User,
    user_info: dict,
    all_versions: list[FlowVersion],
) -> tuple[Flow, FlowVersion]:
    """
    Handle flow version creation/update based on current status.

    Args:
        session: Database session
        original_flow: Original flow
        latest_version: Latest FlowVersion or None
        statuses: Dict of status_name to FlowStatus
        marketplace_folder: Marketplace folder for cloned flows
        payload: Publish payload
        current_user: Current user
        user_info: User info dict
        all_versions: All existing versions

    Returns:
        Tuple of (cloned_flow, flow_version)
    """
    flow_id = original_flow.id
    published_status = statuses[FlowStatusEnum.PUBLISHED.value]
    unpublished_status = statuses.get(FlowStatusEnum.UNPUBLISHED.value)

    current_status_name = latest_version.status.status_name if latest_version and latest_version.status else None
    logger.info(f"Publishing flow {flow_id} with current status: {current_status_name}")

    if not latest_version:
        # Scenario: No version exists - create new clone and flow_version
        logger.info(f"No version exists for flow {flow_id}, creating new clone")

        cloned_flow = await clone_flow_for_marketplace(
            session=session,
            original_flow=original_flow,
            target_folder_id=marketplace_folder.id,
            user_id=current_user.id,
            marketplace_flow_name=payload.marketplace_flow_name.strip(),
            version=payload.version,
            tags=payload.tags,
            description=payload.description,
            locked=False,
        )
        session.add(cloned_flow)
        await session.flush()

        flow_version = _create_new_flow_version(
            flow_id=flow_id,
            cloned_flow_id=cloned_flow.id,
            payload=payload,
            published_status_id=published_status.id,
            user_id=current_user.id,
            user_info=user_info,
        )
        session.add(flow_version)

        return cloned_flow, flow_version

    elif current_status_name in (FlowStatusEnum.SUBMITTED.value, FlowStatusEnum.REJECTED.value):
        # Scenario: Status=Submitted or Rejected - update existing flow_version to Published (reuse clone)
        logger.info(f"Flow {flow_id} is {current_status_name}, updating to Published")

        cloned_flow = await _get_or_validate_cloned_flow(
            session, latest_version.version_flow_id, current_status_name
        )

        flow_version = _update_flow_version_to_published(
            flow_version=latest_version,
            payload=payload,
            published_status_id=published_status.id,
            user_id=current_user.id,
            user_info=user_info,
        )
        session.add(flow_version)

        return cloned_flow, flow_version

    elif current_status_name == FlowStatusEnum.PUBLISHED.value:
        # Scenario: Status=Published - clone new version, set old to Unpublished
        logger.info(f"Flow {flow_id} is Published, creating new version")

        if not unpublished_status:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unpublished status not found in database",
            )

        # Mark old version as Unpublished
        latest_version.status_id = unpublished_status.id
        latest_version.updated_at = datetime.now(timezone.utc)
        session.add(latest_version)

        # Clone the flow for new version
        cloned_flow = await clone_flow_for_marketplace(
            session=session,
            original_flow=original_flow,
            target_folder_id=marketplace_folder.id,
            user_id=current_user.id,
            marketplace_flow_name=payload.marketplace_flow_name.strip(),
            version=payload.version,
            tags=payload.tags,
            description=payload.description,
            locked=False,
        )
        session.add(cloned_flow)
        await session.flush()

        flow_version = _create_new_flow_version(
            flow_id=flow_id,
            cloned_flow_id=cloned_flow.id,
            payload=payload,
            published_status_id=published_status.id,
            user_id=current_user.id,
            user_info=user_info,
        )
        session.add(flow_version)

        return cloned_flow, flow_version

    else:
        # Scenario: Status=Unpublished/Draft or any other status - create new clone
        logger.info(f"Flow {flow_id} has status {current_status_name}, creating new clone")

        # Unpublish any existing Published versions for this flow
        if unpublished_status:
            for version in all_versions:
                if version.status_id == published_status.id:
                    logger.info(f"Unpublishing old version {version.version} for flow {flow_id}")
                    version.status_id = unpublished_status.id
                    version.updated_at = datetime.now(timezone.utc)
                    session.add(version)

        # Clone the flow
        cloned_flow = await clone_flow_for_marketplace(
            session=session,
            original_flow=original_flow,
            target_folder_id=marketplace_folder.id,
            user_id=current_user.id,
            marketplace_flow_name=payload.marketplace_flow_name.strip(),
            version=payload.version,
            tags=payload.tags,
            description=payload.description,
            locked=False,
        )
        session.add(cloned_flow)
        await session.flush()

        # Check if FlowVersion with same (original_flow_id, version) already exists
        existing_version_query = select(FlowVersion).where(
            FlowVersion.original_flow_id == flow_id,
            FlowVersion.version == payload.version
        )
        existing_version_result = await session.exec(existing_version_query)
        existing_flow_version = existing_version_result.first()

        if existing_flow_version:
            # Update existing flow_version record
            existing_flow_version.version_flow_id = cloned_flow.id
            existing_flow_version.title = payload.marketplace_flow_name
            existing_flow_version.description = payload.description
            existing_flow_version.tags = payload.tags
            existing_flow_version.agent_logo = payload.flow_icon
            existing_flow_version.status_id = published_status.id
            existing_flow_version.published_by = current_user.id
            existing_flow_version.published_by_name = user_info.get("name")
            existing_flow_version.published_by_email = user_info.get("email")
            existing_flow_version.published_at = datetime.now(timezone.utc)
            flow_version = existing_flow_version
        else:
            flow_version = _create_new_flow_version(
                flow_id=flow_id,
                cloned_flow_id=cloned_flow.id,
                payload=payload,
                published_status_id=published_status.id,
                user_id=current_user.id,
                user_info=user_info,
            )
            session.add(flow_version)

        return cloned_flow, flow_version


# Vector DB storage disabled - may use in future
# async def _store_flow_in_vector_db(
#     flow: Flow,
#     marketplace_name: str,
#     description: str,
#     tags: list[str],
# ) -> None:
#     """
#     Store flow YAML in vector database for semantic search.
#
#     This is a non-blocking operation - failures are logged but don't affect publishing.
#
#     Args:
#         flow: The cloned flow to store
#         marketplace_name: Name used in marketplace
#         description: Flow description
#         tags: Tags for categorization
#     """
#     try:
#         logger.info(f"Storing flow {flow.id} in vector database")
#
#         # Step 1: Get component catalog
#         settings_service = get_settings_service()
#         all_components = await get_and_cache_all_types_dict(settings_service)
#
#         # Step 2: Convert flow to YAML
#         converter = FlowToYamlConverter(all_components)
#         flow_data = {
#             "id": str(flow.id),
#             "name": marketplace_name,
#             "description": description or "",
#             "data": flow.data,
#         }
#         yaml_content = await converter.convert_flow_to_yaml(flow_data)
#
#         # Step 3: Extract component types from flow data
#         component_types = []
#         if flow.data and "nodes" in flow.data:
#             for node in flow.data["nodes"]:
#                 node_data = node.get("data", {})
#                 node_info = node_data.get("node", {})
#                 display_name = node_info.get("display_name", "")
#                 if display_name:
#                     component_types.append(display_name)
#
#         # Remove duplicates
#         component_types = list(set(component_types))
#
#         # Step 4: Store in vector DB
#         vector_service = VectorDatabaseService()
#         success = vector_service.store_flow(
#             flow_id=str(flow.id),
#             flow_name=marketplace_name,
#             yaml_content=yaml_content,
#             description=description or "",
#             components=component_types,
#             tags=tags or []
#         )
#
#         if success:
#             logger.info(f"Successfully stored flow {flow.id} in vector database")
#         else:
#             logger.warning(f"Vector DB storage returned False for flow {flow.id}")
#
#     except Exception as e:
#         # Log error but don't fail the publish operation
#         logger.error(f"Failed to store flow {flow.id} in vector database: {e}", exc_info=True)


@router.post("/publish/{flow_id}", response_model=PublishedFlowRead, status_code=status.HTTP_201_CREATED, deprecated=True)
async def publish_flow(
    flow_id: UUID,
    payload: PublishedFlowCreate,
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    DEPRECATED: Use /publish-flow/{flow_id} instead.

    Publish a flow to marketplace by cloning it.

    - First publish: Creates clone in target folder + published_flow record
    - Re-publish: Updates existing clone with new data from original

    Naming convention:
    - Original flow: "{marketplace_name}"
    - Cloned flow: "{marketplace_name}-Published-{version}-folder-{folder_id}"
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

        # 4. Check if already published (by flow_cloned_from)
        existing_result = await session.exec(
            select(PublishedFlow).where(PublishedFlow.flow_cloned_from == flow_id)
        )
        existing = existing_result.first()

        if existing:
            # RE-PUBLISH: Use existing clone from flow_version (created during submit for approval)

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

            # Step 2: Find the latest Approved flow_version for this flow (from new submission cycle)
            approved_status_result = await session.exec(
                select(FlowStatus).where(FlowStatus.status_name == FlowStatusEnum.APPROVED.value)
            )
            approved_status = approved_status_result.first()

            if not approved_status:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Approved status not found in database",
                )

            flow_version_result = await session.exec(
                select(FlowVersion)
                .where(FlowVersion.original_flow_id == flow_id)
                .where(FlowVersion.status_id == approved_status.id)
                .order_by(FlowVersion.created_at.desc())
                .limit(1)
            )
            flow_version = flow_version_result.first()

            if not flow_version:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No approved version found for this flow. Please submit for approval first.",
                )

            if not flow_version.version_flow_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Approved flow version does not have a cloned flow snapshot.",
                )

            # Get the existing cloned flow from version_flow_id
            new_cloned_flow = await session.get(Flow, flow_version.version_flow_id)
            if not new_cloned_flow:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Cloned flow snapshot not found.",
                )

            # Step 3: Update original flow name (keep consistent naming)
            original_flow.name = marketplace_name
            original_flow.tags = payload.tags
            original_flow.description = payload.description or original_flow.description
            # Unlock the flow after publishing
            original_flow.locked = False

            # Step 4: Update published_flow record using explicit UPDATE to avoid implicit deletes
            stmt = (
                update(PublishedFlow)
                .where(PublishedFlow.id == existing.id)
                .values(
                    flow_id=new_cloned_flow.id,
                    version=payload.version,
                    tags=payload.tags,
                    description=payload.description or original_flow.description,
                    flow_name=marketplace_name,
                    flow_icon=payload.flow_icon or existing.flow_icon,
                    flow_icon_updated_at=datetime.now(timezone.utc) if payload.flow_icon and payload.flow_icon != existing.flow_icon else existing.flow_icon_updated_at,
                    published_by=current_user.id,
                    published_by_username=current_user.username,
                    published_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    status=PublishStatusEnum.PUBLISHED,
                )
            )
            await session.exec(stmt)

            session.add(original_flow)

            # Handle version_flow_input_sample: Update existing or create new
            if any([payload.storage_account, payload.container_name, payload.file_names, payload.sample_text, payload.sample_output]):
                # Check if sample exists for this version
                existing_sample_query = select(VersionFlowInputSample).where(
                    VersionFlowInputSample.original_flow_id == flow_id,
                    VersionFlowInputSample.version == payload.version,
                )
                existing_sample_result = await session.exec(existing_sample_query)
                existing_sample = existing_sample_result.first()

                if existing_sample:
                    # Update existing sample
                    existing_sample.storage_account = payload.storage_account
                    existing_sample.container_name = payload.container_name
                    existing_sample.file_names = payload.file_names
                    existing_sample.sample_text = payload.sample_text
                    existing_sample.sample_output = payload.sample_output
                    existing_sample.updated_at = datetime.now(timezone.utc)
                    session.add(existing_sample)
                else:
                    # Create new sample
                    input_sample = VersionFlowInputSample(
                        flow_version_id=flow_version.id,
                        original_flow_id=flow_id,
                        version=payload.version,
                        storage_account=payload.storage_account,
                        container_name=payload.container_name,
                        file_names=payload.file_names,
                        sample_text=payload.sample_text,
                        sample_output=payload.sample_output,
                    )
                    session.add(input_sample)
                    await session.flush()
                    # Update flow_version with sample_id
                    flow_version.sample_id = input_sample.id

            await session.flush()
            await session.commit()
            await session.refresh(existing)

            # Update flow_version status to Published (for approval workflow tracking)
            published_status_result = await session.exec(
                select(FlowStatus).where(FlowStatus.status_name == FlowStatusEnum.PUBLISHED.value)
            )
            published_status = published_status_result.first()

            if published_status:
                # Mark all previous Published versions as Unpublished
                unpublished_status_result = await session.exec(
                    select(FlowStatus).where(FlowStatus.status_name == FlowStatusEnum.UNPUBLISHED.value)
                )
                unpublished_status = unpublished_status_result.first()

                if unpublished_status:
                    await session.exec(
                        update(FlowVersion)
                        .where(FlowVersion.original_flow_id == flow_id)
                        .where(FlowVersion.status_id == published_status.id)
                        .where(FlowVersion.id != flow_version.id)
                        .values(status_id=unpublished_status.id, updated_at=datetime.now(timezone.utc))
                    )
                    logger.info(f"Marked previous Published versions as Unpublished for flow {flow_id}")

                # Extract publisher name and email from request
                publisher_name = None
                publisher_email = None
                try:
                    if hasattr(request.state, "user") and request.state.user:
                        user = request.state.user
                        if hasattr(user, "_user_data"):
                            user_data = user._user_data
                            first_name = user_data.get("firstName", "")
                            last_name = user_data.get("lastName", "")
                            publisher_name = f"{first_name} {last_name}".strip() or user_data.get("username", "")
                            publisher_email = user_data.get("email", "")
                        elif hasattr(user, "email"):
                            publisher_email = user.email
                            publisher_name = getattr(user, "username", "")
                except Exception as e:
                    logger.warning(f"Could not extract publisher info from request: {e}")

                # Update flow_version to Published status
                flow_version.status_id = published_status.id
                flow_version.published_by = current_user.id
                flow_version.published_by_name = publisher_name
                flow_version.published_by_email = publisher_email
                flow_version.published_at = datetime.now(timezone.utc)
                flow_version.updated_at = datetime.now(timezone.utc)

                session.add(flow_version)
                await session.commit()
                logger.info(f"Updated flow_version {flow_version.id} to Published status")

            # Refresh published_flow record
            await session.refresh(existing)

            logger.info(f"Re-published flow '{original_flow.name}' (ID: {flow_id}) as version '{payload.version}'")

            # Vector DB storage disabled - may use in future
            # await _store_flow_in_vector_db(
            #     flow=new_cloned_flow,
            #     marketplace_name=marketplace_name,
            #     description=payload.description or original_flow.description or "",
            #     tags=payload.tags or []
            # )

            result_data = PublishedFlowRead.model_validate(existing, from_attributes=True)
            return result_data

        # NEW PUBLISH: Use existing clone from flow_version (created during submit for approval)

        # Find the latest Approved flow_version for this flow
        approved_status_result = await session.exec(
            select(FlowStatus).where(FlowStatus.status_name == FlowStatusEnum.APPROVED.value)
        )
        approved_status = approved_status_result.first()

        if not approved_status:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Approved status not found in database",
            )

        flow_version_result = await session.exec(
            select(FlowVersion)
            .where(FlowVersion.original_flow_id == flow_id)
            .where(FlowVersion.status_id == approved_status.id)
            .order_by(FlowVersion.created_at.desc())
            .limit(1)
        )
        flow_version = flow_version_result.first()

        if not flow_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No approved version found for this flow. Please submit for approval first.",
            )

        if not flow_version.version_flow_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Approved flow version does not have a cloned flow snapshot.",
            )

        # Get the existing cloned flow from version_flow_id
        cloned_flow = await session.get(Flow, flow_version.version_flow_id)
        if not cloned_flow:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cloned flow snapshot not found.",
            )

        # Update original flow name to marketplace name
        original_flow.name = marketplace_name
        original_flow.tags = payload.tags
        original_flow.description = payload.description or original_flow.description
        # Unlock the flow after publishing
        original_flow.locked = False

        # Create published_flow record using the existing clone
        published_flow = PublishedFlow(
            flow_id=cloned_flow.id,  # Use existing clone from flow_version
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

        # Handle version_flow_input_sample: Update existing or create new
        if any([payload.storage_account, payload.container_name, payload.file_names, payload.sample_text, payload.sample_output]):
            # Check if sample exists for this version
            existing_sample_query = select(VersionFlowInputSample).where(
                VersionFlowInputSample.original_flow_id == flow_id,
                VersionFlowInputSample.version == payload.version,
            )
            existing_sample_result = await session.exec(existing_sample_query)
            existing_sample = existing_sample_result.first()

            if existing_sample:
                # Update existing sample
                existing_sample.storage_account = payload.storage_account
                existing_sample.container_name = payload.container_name
                existing_sample.file_names = payload.file_names
                existing_sample.sample_text = payload.sample_text
                existing_sample.sample_output = payload.sample_output
                existing_sample.updated_at = datetime.now(timezone.utc)
                session.add(existing_sample)
            else:
                # Create new sample
                input_sample = VersionFlowInputSample(
                    flow_version_id=flow_version.id,
                    original_flow_id=flow_id,
                    version=payload.version,
                    storage_account=payload.storage_account,
                    container_name=payload.container_name,
                    file_names=payload.file_names,
                    sample_text=payload.sample_text,
                    sample_output=payload.sample_output,
                )
                session.add(input_sample)
                await session.flush()
                # Update flow_version with sample_id
                flow_version.sample_id = input_sample.id

        await session.flush()
        await session.commit()

        # Update flow_version status to Published (for approval workflow tracking)
        published_status_result = await session.exec(
            select(FlowStatus).where(FlowStatus.status_name == FlowStatusEnum.PUBLISHED.value)
        )
        published_status = published_status_result.first()

        if published_status:
            # Mark all previous Published versions as Unpublished
            unpublished_status_result = await session.exec(
                select(FlowStatus).where(FlowStatus.status_name == FlowStatusEnum.UNPUBLISHED.value)
            )
            unpublished_status = unpublished_status_result.first()

            if unpublished_status:
                await session.exec(
                    update(FlowVersion)
                    .where(FlowVersion.original_flow_id == flow_id)
                    .where(FlowVersion.status_id == published_status.id)
                    .where(FlowVersion.id != flow_version.id)
                    .values(status_id=unpublished_status.id, updated_at=datetime.now(timezone.utc))
                )
                logger.info(f"Marked previous Published versions as Unpublished for flow {flow_id}")

            # Extract publisher name and email from request
            publisher_name = None
            publisher_email = None
            try:
                if hasattr(request.state, "user") and request.state.user:
                    user = request.state.user
                    if hasattr(user, "_user_data"):
                        user_data = user._user_data
                        first_name = user_data.get("firstName", "")
                        last_name = user_data.get("lastName", "")
                        publisher_name = f"{first_name} {last_name}".strip() or user_data.get("username", "")
                        publisher_email = user_data.get("email", "")
                    elif hasattr(user, "email"):
                        publisher_email = user.email
                        publisher_name = getattr(user, "username", "")
            except Exception as e:
                logger.warning(f"Could not extract publisher info from request: {e}")

            # Update flow_version to Published status
            flow_version.status_id = published_status.id
            flow_version.published_by = current_user.id
            flow_version.published_by_name = publisher_name
            flow_version.published_by_email = publisher_email
            flow_version.published_at = datetime.now(timezone.utc)
            flow_version.updated_at = datetime.now(timezone.utc)

            session.add(flow_version)
            await session.commit()
            logger.info(f"Updated flow_version {flow_version.id} to Published status")

        logger.info(f"Published flow as '{marketplace_name}' version '{payload.version}' (Original ID: {flow_id})")

        # Vector DB storage disabled - may use in future
        # await _store_flow_in_vector_db(
        #     flow=cloned_flow,
        #     marketplace_name=marketplace_name,
        #     description=payload.description or original_flow.description or "",
        #     tags=payload.tags or []
        # )

        # Refresh published_flow record
        await session.refresh(published_flow)

        result_data = PublishedFlowRead.model_validate(published_flow, from_attributes=True)
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


@router.post("/publish-flow/{flow_id}", response_model=PublishedFlowRead, status_code=status.HTTP_201_CREATED)
async def publish_flow_marketplace_admin(
    flow_id: UUID,
    payload: PublishedFlowCreate,
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Marketplace Admin endpoint to publish a flow directly to marketplace.

    This endpoint handles all flow statuses intelligently:
    - No version exists: Clone flow and create flow_version with status=Published
    - Status=Submitted: Update existing flow_version to Published (reuse clone)
    - Status=Rejected: Update existing flow_version to Published (reuse clone)
    - Status=Published: Clone new version, create new flow_version=Published, set old to Unpublished
    - Status=Unpublished/Draft: Clone flow and create new flow_version=Published

    Only Marketplace Admin can access this endpoint.
    """
    try:
        # Step 1: Verify Marketplace Admin role
        settings_service = get_settings_service()
        user_info = await get_user_info_from_auth_token(request, session, settings_service)
        require_marketplace_admin(user_info)

        # Step 2: Fetch original flow
        original_flow = await session.get(Flow, flow_id)
        if not original_flow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

        # Step 3: Validate marketplace name
        marketplace_name = payload.marketplace_flow_name.strip()
        await _validate_marketplace_name(session, marketplace_name, flow_id)

        # Step 4: Get all status records
        statuses = await _get_flow_statuses(session)

        # Step 5: Get existing flow versions
        all_versions, latest_version = await _get_flow_versions(session, flow_id)

        # Step 6: Get marketplace folder and unpublish existing versions
        marketplace_folder = await get_or_create_marketplace_agent_folder(session)
        published_status = statuses[FlowStatusEnum.PUBLISHED.value]
        unpublished_status = statuses.get(FlowStatusEnum.UNPUBLISHED.value)
        await _unpublish_existing_versions(session, all_versions, published_status, unpublished_status, flow_id)

        # Step 7: Handle version based on current status
        cloned_flow, flow_version = await _handle_version_by_status(
            session=session,
            original_flow=original_flow,
            latest_version=latest_version,
            statuses=statuses,
            marketplace_folder=marketplace_folder,
            payload=payload,
            current_user=current_user,
            user_info=user_info,
            all_versions=all_versions,
        )

        # Step 8: Update original flow metadata
        _update_original_flow_metadata(original_flow, payload)
        session.add(original_flow)

        # Step 9: Update or create PublishedFlow record
        published_flow = await _update_or_create_published_flow(
            session=session,
            flow_id=flow_id,
            cloned_flow_id=cloned_flow.id,
            payload=payload,
            original_flow=original_flow,
            current_user=current_user,
        )

        # Step 10: Handle input sample
        await _handle_input_sample(session, flow_id, flow_version, payload)

        # Step 11: Commit all changes
        await session.flush()
        await session.commit()
        await session.refresh(published_flow)

        logger.info(f"Marketplace Admin published flow {flow_id} as '{marketplace_name}' version '{payload.version}'")

        # Step 12: Return result
        result_data = PublishedFlowRead.model_validate(published_flow, from_attributes=True)
        return result_data

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error in Marketplace Admin publish flow: {str(e)}", exc_info=True)
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

    # Update flow_version status to Unpublished (status_id=6)
    original_flow_id = published_flow.flow_cloned_from

    # Get status IDs
    unpublished_status_stmt = select(FlowStatus).where(FlowStatus.status_name == FlowStatusEnum.UNPUBLISHED.value)
    unpublished_status = (await session.exec(unpublished_status_stmt)).first()

    published_status_stmt = select(FlowStatus).where(FlowStatus.status_name == FlowStatusEnum.PUBLISHED.value)
    published_status = (await session.exec(published_status_stmt)).first()

    if unpublished_status and published_status and original_flow_id:
        # Update all Published flow_version records to Unpublished
        await session.exec(
            update(FlowVersion)
            .where(FlowVersion.original_flow_id == original_flow_id)
            .where(FlowVersion.status_id == published_status.id)
            .values(status_id=unpublished_status.id, updated_at=datetime.now(timezone.utc))
        )
        logger.info(f"Updated flow_version status to Unpublished for original_flow_id: {original_flow_id}")

    await session.commit()

    logger.info(f"Unpublished flow ID: {flow_id}")

    return {"message": "Flow unpublished successfully"}


@router.get("/{flow_id}/versions", response_model=list[PublishedFlowVersionRead], status_code=status.HTTP_200_OK)
async def get_flow_versions(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Get all flow versions for a flow (for version dropdown).
    Returns versions from flow_version table ordered by created_at descending.
    Uses status_name from flow_status table to show version status.
    No permission check - any authenticated user can view versions.
    """
    # Check if flow exists
    original_flow = await session.get(Flow, flow_id)
    if not original_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found",
        )

    # Get all versions for this original flow from flow_version table
    query = (
        select(FlowVersion)
        .where(FlowVersion.original_flow_id == flow_id)
        .options(joinedload(FlowVersion.status))
        .order_by(FlowVersion.created_at.desc())  # Newest first
    )

    result = await session.exec(query)
    versions = result.all()

    if not versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No versions found for this flow",
        )

    # Convert FlowVersion to PublishedFlowVersionRead format
    return [
        PublishedFlowVersionRead(
            id=str(v.id),  # UUID to string
            version=v.version,
            flow_id_cloned_to=str(v.version_flow_id) if v.version_flow_id else None,
            flow_id_cloned_from=str(v.original_flow_id),
            published_flow_id=None,  # Not applicable for flow_version
            flow_name=v.title or "",
            flow_icon=v.agent_logo,
            description=v.description,
            tags=v.tags,
            active=(v.status.status_name == FlowStatusEnum.PUBLISHED.value if v.status else False),
            drafted=False,  # Not used with flow_version
            published_by=str(v.published_by) if v.published_by else str(v.submitted_by),
            published_at=v.published_at.isoformat() if v.published_at else v.created_at.isoformat(),
            created_at=v.created_at.isoformat(),
            status_name=v.status.status_name if v.status else None,  # Add status name
        )
        for v in versions
    ]


@router.post("/revert/{flow_id}/{version_id}", response_model=RevertToVersionResponse, status_code=status.HTTP_200_OK)
async def revert_to_version(
    flow_id: UUID,
    version_id: str,  # Changed from int to str (UUID)
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Revert original flow to a specific version by cloning version's data.
    This REPLACES the original flow's data with the selected version's data.
    User can then edit and publish as a new version.
    Uses flow_version table instead of published_flow_version.
    No permission check - any authenticated user can revert.
    """
    # Convert version_id string to UUID
    try:
        version_uuid = UUID(version_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid version ID format",
        )

    # Get the version record from flow_version table
    version = await session.get(FlowVersion, version_uuid)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    # Validate version belongs to this flow
    if version.original_flow_id != flow_id:
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
    if not version.version_flow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Versioned flow data not found",
        )

    versioned_flow = await session.get(Flow, version.version_flow_id)
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

    await session.commit()
    await session.refresh(original_flow)

    logger.info(f"Reverted flow {flow_id} to version {version.version} (version_id: {version_id})")

    return RevertToVersionResponse(
        message=f"Successfully reverted to version {version.version}",
        version=version.version,
        flow_id=flow_id,
        cloned_flow_id=version.version_flow_id,
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
    return await _list_all_published_flows(
        session=session,
        page=page,
        limit=limit,
        search=search,
        category=category,
        tags=tags,  # This is now a string, not a Query object
        status_filter=status_filter,
        sort_by=sort_by,
        order=order,
    )


async def _list_all_published_flows(
    session: AsyncSession,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    category: str | None = None,
    tags: str | None = None,
    status_filter: str | None = None,
    sort_by: str = "published_at",
    order: str = "desc",
):
    # Base query - apply status filter
    # Note: input_samples relationship removed - using version_flow_input_sample instead
    if status_filter == "published":
        query = select(PublishedFlow).where(PublishedFlow.status == PublishStatusEnum.PUBLISHED)
    elif status_filter == "unpublished":
        query = select(PublishedFlow).where(PublishedFlow.status == PublishStatusEnum.UNPUBLISHED)
    else:  # "all" or None - show all flows (default)
        query = select(PublishedFlow)

    # Apply search filter on denormalized flow_name and description
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                PublishedFlow.flow_name.ilike(search_pattern),
                PublishedFlow.description.ilike(search_pattern),
            )
        )

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
        count_query = select(func.count(PublishedFlow.id)).where(
            PublishedFlow.status == PublishStatusEnum.PUBLISHED
        )
    elif status_filter == "unpublished":
        count_query = select(func.count(PublishedFlow.id)).where(
            PublishedFlow.status == PublishStatusEnum.UNPUBLISHED
        )
    else:  # "all" or None - count all flows (default)
        count_query = select(func.count(PublishedFlow.id))

    # Apply same filters to count query
    if search:
        search_pattern = f"%{search}%"
        count_query = count_query.where(
            or_(
                PublishedFlow.flow_name.ilike(search_pattern),
                PublishedFlow.description.ilike(search_pattern),
            )
        )
    if category:
        count_query = count_query.where(PublishedFlow.category == category)
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        for tag in tag_list:
            # Cast JSON to text and check if tag is in the stringified array
            count_query = count_query.where(
                cast(PublishedFlow.tags, Text).contains(f'"{tag}"')
            )

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
    items = [
        PublishedFlowRead.model_validate(published_flow, from_attributes=True)
        for published_flow in rows
    ]

    pages = (total + limit - 1) // limit if limit > 0 else 0

    return {"items": items, "total": total, "page": page, "pages": pages}


@router.post("/validate-name", status_code=status.HTTP_200_OK)
async def validate_marketplace_name(
    payload: dict,
    session: DbSession,
):
    """
    Validate if a marketplace flow name already exists.
    Checks both published_flow table (marketplace globally) and flow table (within folder).
    Returns whether the name is available for use.

    Check 1: Global marketplace name uniqueness in published_flow table
    Check 2: Folder-scoped flow name uniqueness in flow table
    """
    marketplace_name = payload.get("marketplace_flow_name", "").strip()
    exclude_flow_id = payload.get("exclude_flow_id")  # Flow ID to exclude (for re-publishing)
    folder_id = payload.get("folder_id")  # Folder ID for folder-scoped validation

    if not marketplace_name:
        return {"exists": False, "available": True}

    # Step 1: Check if name exists in published flows (marketplace) - case insensitive
    published_query = select(PublishedFlow).where(
        func.lower(PublishedFlow.flow_name) == func.lower(marketplace_name),
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

    # Step 2: Check if name exists in flow table within the same folder
    if folder_id:
        try:
            folder_uuid = UUID(folder_id)
            # Case insensitive comparison for folder-scoped check
            flow_query = select(Flow).where(
                func.lower(Flow.name) == func.lower(marketplace_name),
                Flow.folder_id == folder_uuid,  # Folder-scoped check
            )

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
                    "message": f"A flow with the name '{marketplace_name}' already exists in the folder",
                }
        except (ValueError, TypeError):
            pass  # Invalid folder_id UUID, skip folder check

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
    # Note: input_samples selectinload removed - using version_flow_input_sample instead
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

    # Fetch original flow to get its creator
    original_flow = None
    if published_flow.flow_cloned_from:
        original_flow_query = select(Flow).where(Flow.id == published_flow.flow_cloned_from)
        original_flow_result = await session.exec(original_flow_query)
        original_flow = original_flow_result.first()

    # Load input sample from version_flow_input_sample
    # First try to find sample matching the published version, then fallback to latest
    input_sample = None
    if published_flow.flow_cloned_from:
        # Try to find sample for this specific version first
        if published_flow.version:
            version_sample_query = (
                select(VersionFlowInputSample)
                .where(
                    VersionFlowInputSample.original_flow_id == published_flow.flow_cloned_from,
                    VersionFlowInputSample.version == published_flow.version
                )
                .order_by(VersionFlowInputSample.updated_at.desc())
                .limit(1)
            )
            version_sample_result = await session.exec(version_sample_query)
            input_sample = version_sample_result.first()

        # Fallback to latest sample if no version-specific sample found
        if not input_sample:
            input_sample_query = (
                select(VersionFlowInputSample)
                .where(VersionFlowInputSample.original_flow_id == published_flow.flow_cloned_from)
                .order_by(VersionFlowInputSample.updated_at.desc())
                .limit(1)
            )
            input_sample_result = await session.exec(input_sample_query)
            input_sample = input_sample_result.first()

    item = PublishedFlowRead.model_validate(published_flow, from_attributes=True)
    item.flow_name = published_flow.flow_name
    item.flow_icon = published_flow.flow_icon or (flow.icon if flow.icon else None)
    item.published_by_username = user.username
    item.flow_data = flow.data if flow.data else {}  # Include flow data from cloned flow
    # Convert VersionFlowInputSample to the expected format
    if input_sample:
        item.input_samples = [{
            "id": str(input_sample.id),
            "storage_account": input_sample.storage_account,
            "container_name": input_sample.container_name,
            "file_names": input_sample.file_names,
            "sample_text": input_sample.sample_text,
            "sample_output": input_sample.sample_output,
        }]
    else:
        item.input_samples = []
    item.original_flow_user_id = original_flow.user_id if original_flow else None

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
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Delete published flow and ALL related data (hard delete).
    Owner or Marketplace Admin can delete.

    Deletes:
    - published_flow record
    - published_flow_version records (cascade)
    - published_flow_input_sample records (cascade)
    - flow_version records (for original flow)
    - version_flow_input_sample records
    - Cloned flow records
    """
    # Get user info using same method as publish_flow_marketplace_admin
    # This calls the external auth service API to get roles correctly
    settings_service = get_settings_service()
    user_info = await get_user_info_from_auth_token(request, session, settings_service)
    is_marketplace_admin = user_info.get("is_marketplace_admin", False)

    logger.info(f"Delete published flow: is_marketplace_admin={is_marketplace_admin}, current_user.id={current_user.id}")

    # Fetch published flow - allow owner OR marketplace admin
    if is_marketplace_admin:
        logger.info(f"Marketplace admin: querying by published_flow_id only: {published_flow_id}")
        query = select(PublishedFlow).where(PublishedFlow.id == published_flow_id)
    else:
        logger.info(f"Non-admin: querying by published_flow_id={published_flow_id} AND user_id={current_user.id}")
        query = select(PublishedFlow).where(
            PublishedFlow.id == published_flow_id,
            PublishedFlow.user_id == current_user.id
        )

    result = await session.exec(query)
    published_flow = result.first()

    if not published_flow:
        # Debug: Check if the flow exists at all
        debug_query = select(PublishedFlow).where(PublishedFlow.id == published_flow_id)
        debug_result = await session.exec(debug_query)
        debug_flow = debug_result.first()
        if debug_flow:
            logger.error(f"Flow exists but permission denied. Flow user_id={debug_flow.user_id}, current_user.id={current_user.id}")
        else:
            logger.error(f"Flow with id={published_flow_id} does not exist in database")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published flow not found or you don't have permission to delete it",
        )

    original_flow_id = published_flow.flow_cloned_from
    cloned_flow_id = published_flow.flow_id

    # 1. Get all flow_version records for the original flow
    flow_versions_stmt = select(FlowVersion).where(
        FlowVersion.original_flow_id == original_flow_id
    )
    flow_versions_result = await session.exec(flow_versions_stmt)
    flow_versions = flow_versions_result.all()

    # Collect all cloned flow IDs from flow_version
    cloned_flow_ids = set()
    if cloned_flow_id:
        cloned_flow_ids.add(cloned_flow_id)
    for fv in flow_versions:
        if fv.version_flow_id:
            cloned_flow_ids.add(fv.version_flow_id)

    # 2. Delete version_flow_input_sample for each flow_version
    for fv in flow_versions:
        if fv.sample_id:
            sample = await session.get(VersionFlowInputSample, fv.sample_id)
            if sample:
                await session.delete(sample)

    # 3. Delete all flow_version records
    for fv in flow_versions:
        await session.delete(fv)

    # 4. Delete published_flow (cascades to published_flow_version, published_flow_input_sample)
    await session.delete(published_flow)

    # 5. Delete all cloned flows
    for flow_id in cloned_flow_ids:
        cloned_flow = await session.get(Flow, flow_id)
        if cloned_flow:
            await session.delete(cloned_flow)

    await session.commit()

    logger.info(f"Deleted published flow {published_flow_id} and all related data")

    return {"message": "Published flow and all related data deleted successfully"}


# ---------------------------
# Input Sample Management (using version_flow_input_sample)
# ---------------------------

@router.patch("/input-samples/{sample_id}", status_code=status.HTTP_200_OK)
async def patch_input_sample(
    sample_id: UUID,
    payload: dict,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Update editable fields of a VersionFlowInputSample.

    Allowed updates:
    - sample_text (list[str])
    - sample_output (dict)

    file_names are immutable via PATCH and must be removed via DELETE endpoints.
    """
    # Fetch sample from version_flow_input_sample
    sample = await session.get(VersionFlowInputSample, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input sample not found")

    # Permission check: verify user owns the original flow
    original_flow = await session.get(Flow, sample.original_flow_id)
    if not original_flow or original_flow.user_id != current_user.id:
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

    return {
        "id": str(sample.id),
        "storage_account": sample.storage_account,
        "container_name": sample.container_name,
        "file_names": sample.file_names,
        "sample_text": sample.sample_text,
        "sample_output": sample.sample_output,
    }


@router.delete("/input-samples/{sample_id}", status_code=status.HTTP_200_OK)
async def delete_input_sample(
    sample_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Delete an entire VersionFlowInputSample record. Only the owner of the original flow can delete.
    """
    sample = await session.get(VersionFlowInputSample, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input sample not found")

    # Permission check: verify user owns the original flow
    original_flow = await session.get(Flow, sample.original_flow_id)
    if not original_flow or original_flow.user_id != current_user.id:
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
    sample = await session.get(VersionFlowInputSample, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input sample not found")

    # Permission check: verify user owns the original flow
    original_flow = await session.get(Flow, sample.original_flow_id)
    if not original_flow or original_flow.user_id != current_user.id:
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

    return {
        "id": str(sample.id),
        "storage_account": sample.storage_account,
        "container_name": sample.container_name,
        "file_names": sample.file_names,
        "sample_text": sample.sample_text,
        "sample_output": sample.sample_output,
    }


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
    sample = await session.get(VersionFlowInputSample, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input sample not found")

    # Permission check: verify user owns the original flow
    original_flow = await session.get(Flow, sample.original_flow_id)
    if not original_flow or original_flow.user_id != current_user.id:
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

    return {
        "id": str(sample.id),
        "storage_account": sample.storage_account,
        "container_name": sample.container_name,
        "file_names": sample.file_names,
        "sample_text": sample.sample_text,
        "sample_output": sample.sample_output,
    }
