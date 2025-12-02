"""Flow Versions API endpoints for approval workflow functionality."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.flows import clone_flow_for_marketplace
from langflow.initial_setup.setup import get_or_create_marketplace_agent_folder
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_status.model import FlowStatus, FlowStatusEnum
from langflow.services.database.models.flow_version.model import (
    FlowVersion,
    FlowVersionCreate,
    FlowVersionRead,
    FlowVersionRejectRequest,
    FlowVersionPaginatedResponse,
)
from langflow.services.database.models.version_flow_input_sample.model import (
    VersionFlowInputSample,
    VersionFlowInputSampleRead,
)
from langflow.services.database.models.published_flow.model import PublishedFlow
from langflow.services.database.models.published_flow_input_sample.model import PublishedFlowInputSample
from langflow.services.database.models.user.model import User
from langflow.services.auth.permissions import can_edit_flow, get_user_roles_from_request
from langflow.logging import logger

router = APIRouter(prefix="/flow-versions", tags=["Flow Versions"])


def _get_user_full_name_from_request(request: Request) -> str | None:
    """
    Extract user's full name from the Keycloak token stored in request.state.user.

    The middleware stores user data with firstName and lastName from the Keycloak token.
    Returns the full name (firstName + lastName) or None if not available.
    """
    try:
        if hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            # Access the stored user data from Keycloak
            if hasattr(user, "_user_data"):
                user_data = user._user_data
                first_name = user_data.get("firstName", "")
                last_name = user_data.get("lastName", "")
                full_name = f"{first_name} {last_name}".strip()
                if full_name:
                    return full_name
            # Fallback to email/username if no name available
            if hasattr(user, "email") and user.email:
                return user.email
            if hasattr(user, "username") and user.username:
                return user.username
    except Exception as e:
        logger.warning(f"Could not extract user name from request: {e}")
    return None


def _get_user_email_from_request(request: Request) -> str | None:
    """
    Extract user's email from the Keycloak token stored in request.state.user.

    The middleware stores user data with email from the Keycloak token.
    Returns the email or None if not available.
    """
    try:
        if hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            # Try direct email attribute first
            if hasattr(user, "email") and user.email:
                return user.email
            # Fallback to _user_data
            if hasattr(user, "_user_data"):
                user_data = user._user_data
                email = user_data.get("email", "")
                if email:
                    return email
    except Exception as e:
        logger.warning(f"Could not extract user email from request: {e}")
    return None


async def _get_status_by_name(session: AsyncSession, status_name: str) -> FlowStatus:
    """Get flow status by name."""
    stmt = select(FlowStatus).where(FlowStatus.status_name == status_name)
    result = await session.exec(stmt)
    status = result.first()
    if not status:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status '{status_name}' not found in database",
        )
    return status


async def _get_status_id_by_name(session: AsyncSession, status_name: str) -> int:
    """Get flow status ID by name."""
    status = await _get_status_by_name(session, status_name)
    return status.id


@router.post("/submit/{flow_id}", response_model=FlowVersionRead, status_code=status.HTTP_201_CREATED)
async def submit_for_approval(
    flow_id: UUID,
    payload: FlowVersionCreate,
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Submit a flow for approval review.

    Creates a cloned snapshot of the flow and creates a flow_version record
    with status "Submitted". The original flow remains editable.
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
                detail="You don't have permission to submit this flow for approval",
            )

        # 3. Check if this version already exists
        existing_version_stmt = select(FlowVersion).where(
            FlowVersion.original_flow_id == flow_id,
            FlowVersion.version == payload.version,
        )
        existing_version = (await session.exec(existing_version_stmt)).first()
        if existing_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Version {payload.version} already exists for this flow",
            )

        # 4. Get or create marketplace folder for cloned flows
        marketplace_folder = await get_or_create_marketplace_agent_folder(session)

        # 5. Clone the flow for this version snapshot
        cloned_flow_name = f"{payload.title}-Submitted-{payload.version}-{str(flow_id)[:8]}"
        cloned_flow = await clone_flow_for_marketplace(
            session=session,
            original_flow=original_flow,
            target_folder_id=marketplace_folder.id,
            user_id=current_user.id,
            marketplace_flow_name=cloned_flow_name,
            tags=payload.tags,
            description=payload.description,
            version=payload.version
        )
        session.add(cloned_flow)
        await session.flush()

        # 5b. Update original flow with submitted title and description
        original_flow.name = payload.title
        if payload.description:
            original_flow.description = payload.description
        # Lock the flow while it's under review
        original_flow.locked = True
        session.add(original_flow)

        # 6. Get "Submitted" status ID
        submitted_status_id = await _get_status_id_by_name(session, FlowStatusEnum.SUBMITTED.value)

        # 7. Extract user name and email from Keycloak token
        submitter_name = _get_user_full_name_from_request(request)
        submitter_email = _get_user_email_from_request(request)

        # 8. Create flow_version record
        flow_version = FlowVersion(
            original_flow_id=flow_id,
            version_flow_id=cloned_flow.id,
            status_id=submitted_status_id,
            version=payload.version,
            title=payload.title,
            description=payload.description,
            tags=payload.tags,
            agent_logo=payload.agent_logo,
            submitted_by=current_user.id,
            submitted_by_name=submitter_name,
            submitted_by_email=submitter_email,
            submitted_at=datetime.now(timezone.utc),
        )
        session.add(flow_version)
        await session.flush()

        # 9. Create input sample if provided
        if payload.file_names or payload.sample_text or payload.sample_output:
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

        await session.commit()
        await session.refresh(flow_version)

        logger.info(f"Flow {flow_id} submitted for approval as version {payload.version}")

        return FlowVersionRead(
            id=flow_version.id,
            original_flow_id=flow_version.original_flow_id,
            version_flow_id=flow_version.version_flow_id,
            status_id=flow_version.status_id,
            version=flow_version.version,
            title=flow_version.title,
            description=flow_version.description,
            tags=flow_version.tags,
            agent_logo=flow_version.agent_logo,
            sample_id=flow_version.sample_id,
            submitted_by=flow_version.submitted_by,
            submitted_by_name=flow_version.submitted_by_name,
            submitted_by_email=flow_version.submitted_by_email,
            submitted_at=flow_version.submitted_at,
            reviewed_by=flow_version.reviewed_by,
            reviewed_at=flow_version.reviewed_at,
            rejection_reason=flow_version.rejection_reason,
            created_at=flow_version.created_at,
            updated_at=flow_version.updated_at,
            status_name=FlowStatusEnum.SUBMITTED.value,
            submitter_name=flow_version.submitted_by_name,  # Alias for backward compatibility
            submitter_email=flow_version.submitted_by_email,  # Alias for backward compatibility
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting flow for approval: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit flow for approval: {str(e)}",
        )


@router.get("/pending-reviews", response_model=FlowVersionPaginatedResponse)
async def get_pending_reviews(
    session: DbSession,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
):
    """
    Get all flow versions pending review (status = Submitted).

    This endpoint is intended for admin users to see all submissions awaiting approval.
    Returns paginated results.
    """
    try:
        # Get "Submitted" status ID
        submitted_status_id = await _get_status_id_by_name(session, FlowStatusEnum.SUBMITTED.value)

        # Count total items
        count_stmt = (
            select(func.count())
            .select_from(FlowVersion)
            .where(FlowVersion.status_id == submitted_status_id)
        )
        count_result = await session.exec(count_stmt)
        total = count_result.one()

        # Calculate pagination
        pages = (total + limit - 1) // limit  # Ceiling division
        offset = (page - 1) * limit

        # Get paginated results
        stmt = (
            select(FlowVersion)
            .where(FlowVersion.status_id == submitted_status_id)
            .options(
                joinedload(FlowVersion.submitter),
                joinedload(FlowVersion.status),
            )
            .order_by(FlowVersion.submitted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(stmt)
        versions = result.unique().all()

        items = [
            FlowVersionRead(
                id=v.id,
                original_flow_id=v.original_flow_id,
                version_flow_id=v.version_flow_id,
                status_id=v.status_id,
                version=v.version,
                title=v.title,
                description=v.description,
                tags=v.tags,
                agent_logo=v.agent_logo,
                sample_id=v.sample_id,
                submitted_by=v.submitted_by,
                submitted_by_name=v.submitted_by_name,
                submitted_by_email=v.submitted_by_email,
                submitted_at=v.submitted_at,
                reviewed_by=v.reviewed_by,
                reviewed_by_name=v.reviewed_by_name,
                reviewed_by_email=v.reviewed_by_email,
                reviewed_at=v.reviewed_at,
                rejection_reason=v.rejection_reason,
                created_at=v.created_at,
                updated_at=v.updated_at,
                status_name=v.status.status_name if v.status else None,
                # Use stored name/email, fallback to User relationship for backward compatibility
                submitter_name=v.submitted_by_name or (v.submitter.username if v.submitter else None),
                submitter_email=v.submitted_by_email,
            )
            for v in versions
        ]

        return FlowVersionPaginatedResponse(
            items=items,
            total=total,
            page=page,
            pages=pages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching pending reviews: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending reviews: {str(e)}",
        )


@router.get("/all", response_model=FlowVersionPaginatedResponse)
async def get_all_flow_versions(
    session: DbSession,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    status: str | None = Query(None),
):
    """
    Get all flow versions with optional status filtering.

    This endpoint returns all flow versions (Submitted, Published, Rejected) in a single list.
    Optionally filter by status using the status parameter.
    Returns paginated results.

    Valid status values: "Submitted", "Published", "Rejected"
    If status is not provided, returns all flow versions.
    """
    try:
        # Build base query
        query_conditions = []

        if status:
            # Validate status name
            valid_statuses = ["Submitted", "Published", "Rejected"]
            if status not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                )
            status_id = await _get_status_id_by_name(session, status)
            query_conditions.append(FlowVersion.status_id == status_id)
        else:
            # Get all relevant statuses (Submitted, Published, Rejected)
            submitted_id = await _get_status_id_by_name(session, FlowStatusEnum.SUBMITTED.value)
            published_id = await _get_status_id_by_name(session, FlowStatusEnum.PUBLISHED.value)
            rejected_id = await _get_status_id_by_name(session, FlowStatusEnum.REJECTED.value)
            query_conditions.append(
                FlowVersion.status_id.in_([submitted_id, published_id, rejected_id])
            )

        # Count total items
        count_stmt = (
            select(func.count())
            .select_from(FlowVersion)
            .where(*query_conditions)
        )
        count_result = await session.exec(count_stmt)
        total = count_result.one()

        # Calculate pagination
        pages = (total + limit - 1) // limit  # Ceiling division
        offset = (page - 1) * limit

        # Get paginated results
        stmt = (
            select(FlowVersion)
            .where(*query_conditions)
            .options(
                joinedload(FlowVersion.submitter),
                joinedload(FlowVersion.reviewer),
                joinedload(FlowVersion.status),
            )
            .order_by(FlowVersion.submitted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(stmt)
        versions = result.unique().all()

        items = [
            FlowVersionRead(
                id=v.id,
                original_flow_id=v.original_flow_id,
                version_flow_id=v.version_flow_id,
                status_id=v.status_id,
                version=v.version,
                title=v.title,
                description=v.description,
                tags=v.tags,
                agent_logo=v.agent_logo,
                sample_id=v.sample_id,
                submitted_by=v.submitted_by,
                submitted_by_name=v.submitted_by_name,
                submitted_by_email=v.submitted_by_email,
                submitted_at=v.submitted_at,
                reviewed_by=v.reviewed_by,
                reviewed_by_name=v.reviewed_by_name,
                reviewed_by_email=v.reviewed_by_email,
                reviewed_at=v.reviewed_at,
                rejection_reason=v.rejection_reason,
                published_by=v.published_by,
                published_by_name=v.published_by_name,
                published_by_email=v.published_by_email,
                published_at=v.published_at,
                created_at=v.created_at,
                updated_at=v.updated_at,
                status_name=v.status.status_name if v.status else None,
                # Use stored name/email, fallback to User relationship for backward compatibility
                submitter_name=v.submitted_by_name or (v.submitter.username if v.submitter else None),
                submitter_email=v.submitted_by_email,
                reviewer_name=v.reviewed_by_name or (v.reviewer.username if v.reviewer else None),
            )
            for v in versions
        ]

        return FlowVersionPaginatedResponse(
            items=items,
            total=total,
            page=page,
            pages=pages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching all flow versions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch flow versions: {str(e)}",
        )


@router.get("/my-submissions", response_model=list[FlowVersionRead])
async def get_my_submissions(
    session: DbSession,
    current_user: CurrentActiveUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get current user's submitted flow versions.
    """
    try:
        stmt = (
            select(FlowVersion)
            .where(FlowVersion.submitted_by == current_user.id)
            .options(joinedload(FlowVersion.status))
            .order_by(FlowVersion.submitted_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.exec(stmt)
        versions = result.unique().all()

        return [
            FlowVersionRead(
                id=v.id,
                original_flow_id=v.original_flow_id,
                version_flow_id=v.version_flow_id,
                status_id=v.status_id,
                version=v.version,
                title=v.title,
                description=v.description,
                tags=v.tags,
                agent_logo=v.agent_logo,
                sample_id=v.sample_id,
                submitted_by=v.submitted_by,
                submitted_by_name=v.submitted_by_name,
                submitted_by_email=v.submitted_by_email,
                submitted_at=v.submitted_at,
                reviewed_by=v.reviewed_by,
                reviewed_by_name=v.reviewed_by_name,
                reviewed_by_email=v.reviewed_by_email,
                reviewed_at=v.reviewed_at,
                rejection_reason=v.rejection_reason,
                created_at=v.created_at,
                updated_at=v.updated_at,
                status_name=v.status.status_name if v.status else None,
                submitter_name=v.submitted_by_name,
                submitter_email=v.submitted_by_email,
                reviewer_name=v.reviewed_by_name,
            )
            for v in versions
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user submissions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch submissions: {str(e)}",
        )


@router.get("/by-status/{status_name}", response_model=FlowVersionPaginatedResponse)
async def get_versions_by_status(
    status_name: str,
    session: DbSession,
    current_user: CurrentActiveUser,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
):
    """
    Get flow versions filtered by status name.

    Valid status names: Draft, Submitted, Approved, Rejected, Published, Unpublished, Deleted
    Returns paginated results.
    """
    try:
        # Validate status name
        valid_statuses = [s.value for s in FlowStatusEnum]
        if status_name not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )

        status_id = await _get_status_id_by_name(session, status_name)

        # Count total items
        count_stmt = (
            select(func.count())
            .select_from(FlowVersion)
            .where(FlowVersion.status_id == status_id)
        )
        count_result = await session.exec(count_stmt)
        total = count_result.one()

        # Calculate pagination
        pages = (total + limit - 1) // limit  # Ceiling division
        offset = (page - 1) * limit

        # Get paginated results
        stmt = (
            select(FlowVersion)
            .where(FlowVersion.status_id == status_id)
            .options(
                joinedload(FlowVersion.submitter),
                joinedload(FlowVersion.reviewer),
                joinedload(FlowVersion.status),
            )
            .order_by(FlowVersion.submitted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(stmt)
        versions = result.unique().all()

        items = [
            FlowVersionRead(
                id=v.id,
                original_flow_id=v.original_flow_id,
                version_flow_id=v.version_flow_id,
                status_id=v.status_id,
                version=v.version,
                title=v.title,
                description=v.description,
                tags=v.tags,
                agent_logo=v.agent_logo,
                sample_id=v.sample_id,
                submitted_by=v.submitted_by,
                submitted_by_name=v.submitted_by_name,
                submitted_by_email=v.submitted_by_email,
                submitted_at=v.submitted_at,
                reviewed_by=v.reviewed_by,
                reviewed_by_name=v.reviewed_by_name,
                reviewed_by_email=v.reviewed_by_email,
                reviewed_at=v.reviewed_at,
                rejection_reason=v.rejection_reason,
                created_at=v.created_at,
                updated_at=v.updated_at,
                status_name=v.status.status_name if v.status else None,
                # Use stored name/email, fallback to User relationship for backward compatibility
                submitter_name=v.submitted_by_name or (v.submitter.username if v.submitter else None),
                submitter_email=v.submitted_by_email,
                reviewer_name=v.reviewed_by_name or (v.reviewer.username if v.reviewer else None),
            )
            for v in versions
        ]

        return FlowVersionPaginatedResponse(
            items=items,
            total=total,
            page=page,
            pages=pages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching versions by status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch versions: {str(e)}",
        )


@router.post("/approve/{version_id}", response_model=FlowVersionRead)
async def approve_version(
    version_id: UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Approve a submitted flow version.

    Changes status from "Submitted" to "Approved".
    Only admin users should be able to approve.
    """
    try:
        # 1. Fetch the flow version
        stmt = (
            select(FlowVersion)
            .where(FlowVersion.id == version_id)
            .options(joinedload(FlowVersion.status))
        )
        result = await session.exec(stmt)
        flow_version = result.first()

        if not flow_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow version not found",
            )

        # 2. Verify current status is "Submitted"
        if flow_version.status and flow_version.status.status_name != FlowStatusEnum.SUBMITTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Can only approve flows in 'Submitted' status. Current status: {flow_version.status.status_name}",
            )

        # 3. Get "Approved" status ID
        approved_status_id = await _get_status_id_by_name(session, FlowStatusEnum.APPROVED.value)

        # 4. Extract reviewer name and email from Keycloak token
        reviewer_name = _get_user_full_name_from_request(request)
        reviewer_email = _get_user_email_from_request(request)

        # 5. Update the flow version
        flow_version.status_id = approved_status_id
        flow_version.reviewed_by = current_user.id
        flow_version.reviewed_by_name = reviewer_name
        flow_version.reviewed_by_email = reviewer_email
        flow_version.reviewed_at = datetime.now(timezone.utc)
        flow_version.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(flow_version)

        logger.info(f"Flow version {version_id} approved by user {current_user.id} ({reviewer_name})")

        return FlowVersionRead(
            id=flow_version.id,
            original_flow_id=flow_version.original_flow_id,
            version_flow_id=flow_version.version_flow_id,
            status_id=flow_version.status_id,
            version=flow_version.version,
            title=flow_version.title,
            description=flow_version.description,
            tags=flow_version.tags,
            agent_logo=flow_version.agent_logo,
            sample_id=flow_version.sample_id,
            submitted_by=flow_version.submitted_by,
            submitted_by_name=flow_version.submitted_by_name,
            submitted_by_email=flow_version.submitted_by_email,
            submitted_at=flow_version.submitted_at,
            reviewed_by=flow_version.reviewed_by,
            reviewed_by_name=flow_version.reviewed_by_name,
            reviewed_by_email=flow_version.reviewed_by_email,
            reviewed_at=flow_version.reviewed_at,
            rejection_reason=flow_version.rejection_reason,
            created_at=flow_version.created_at,
            updated_at=flow_version.updated_at,
            status_name=FlowStatusEnum.APPROVED.value,
            submitter_name=flow_version.submitted_by_name,  # Alias
            submitter_email=flow_version.submitted_by_email,  # Alias
            reviewer_name=flow_version.reviewed_by_name,  # Alias
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving flow version: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve flow version: {str(e)}",
        )


@router.post("/reject/{version_id}", response_model=FlowVersionRead)
async def reject_version(
    version_id: UUID,
    payload: FlowVersionRejectRequest,
    request: Request,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Reject a submitted flow version.

    Changes status from "Submitted" to "Rejected".
    Optionally includes a rejection reason.
    Only admin users should be able to reject.
    """
    try:
        # 1. Fetch the flow version
        stmt = (
            select(FlowVersion)
            .where(FlowVersion.id == version_id)
            .options(joinedload(FlowVersion.status))
        )
        result = await session.exec(stmt)
        flow_version = result.first()

        if not flow_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow version not found",
            )

        # 2. Verify current status is "Submitted"
        if flow_version.status and flow_version.status.status_name != FlowStatusEnum.SUBMITTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Can only reject flows in 'Submitted' status. Current status: {flow_version.status.status_name}",
            )

        # 3. Get "Rejected" status ID
        rejected_status_id = await _get_status_id_by_name(session, FlowStatusEnum.REJECTED.value)

        # 4. Extract reviewer name and email from Keycloak token
        reviewer_name = _get_user_full_name_from_request(request)
        reviewer_email = _get_user_email_from_request(request)

        # 5. Update the flow version
        flow_version.status_id = rejected_status_id
        flow_version.reviewed_by = current_user.id
        flow_version.reviewed_by_name = reviewer_name
        flow_version.reviewed_by_email = reviewer_email
        flow_version.reviewed_at = datetime.now(timezone.utc)
        flow_version.rejection_reason = payload.rejection_reason
        flow_version.updated_at = datetime.now(timezone.utc)

        # 6. Unlock the original flow so user can edit and resubmit
        original_flow = await session.get(Flow, flow_version.original_flow_id)
        if original_flow:
            original_flow.locked = False
            session.add(original_flow)

        await session.commit()
        await session.refresh(flow_version)

        logger.info(f"Flow version {version_id} rejected by user {current_user.id} ({reviewer_name})")

        return FlowVersionRead(
            id=flow_version.id,
            original_flow_id=flow_version.original_flow_id,
            version_flow_id=flow_version.version_flow_id,
            status_id=flow_version.status_id,
            version=flow_version.version,
            title=flow_version.title,
            description=flow_version.description,
            tags=flow_version.tags,
            agent_logo=flow_version.agent_logo,
            sample_id=flow_version.sample_id,
            submitted_by=flow_version.submitted_by,
            submitted_by_name=flow_version.submitted_by_name,
            submitted_by_email=flow_version.submitted_by_email,
            submitted_at=flow_version.submitted_at,
            reviewed_by=flow_version.reviewed_by,
            reviewed_by_name=flow_version.reviewed_by_name,
            reviewed_by_email=flow_version.reviewed_by_email,
            reviewed_at=flow_version.reviewed_at,
            rejection_reason=flow_version.rejection_reason,
            created_at=flow_version.created_at,
            updated_at=flow_version.updated_at,
            status_name=FlowStatusEnum.REJECTED.value,
            submitter_name=flow_version.submitted_by_name,  # Alias
            submitter_email=flow_version.submitted_by_email,  # Alias
            reviewer_name=flow_version.reviewed_by_name,  # Alias
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting flow version: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject flow version: {str(e)}",
        )


@router.post("/cancel/{version_id}", response_model=FlowVersionRead)
async def cancel_submission(
    version_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Cancel a submitted flow version.

    Changes status from "Submitted" back to "Draft" and unlocks the flow.
    Only the flow owner can cancel their own submission.
    """
    try:
        # 1. Fetch the flow version
        stmt = (
            select(FlowVersion)
            .where(FlowVersion.id == version_id)
            .options(joinedload(FlowVersion.status))
        )
        result = await session.exec(stmt)
        flow_version = result.first()

        if not flow_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow version not found",
            )

        # 2. Verify user is the submitter
        if flow_version.submitted_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the submitter can cancel this submission",
            )

        # 3. Verify current status is "Submitted"
        if flow_version.status and flow_version.status.status_name != FlowStatusEnum.SUBMITTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Can only cancel flows in 'Submitted' status. Current status: {flow_version.status.status_name}",
            )

        # 4. Get "Draft" status ID
        draft_status_id = await _get_status_id_by_name(session, FlowStatusEnum.DRAFT.value)

        # 5. Update the flow version - revert to draft
        flow_version.status_id = draft_status_id
        flow_version.reviewed_by = None
        flow_version.reviewed_by_name = None
        flow_version.reviewed_by_email = None
        flow_version.reviewed_at = None
        flow_version.rejection_reason = None
        flow_version.updated_at = datetime.now(timezone.utc)

        # 6. Unlock the original flow so user can edit
        original_flow = await session.get(Flow, flow_version.original_flow_id)
        if original_flow:
            original_flow.locked = False
            session.add(original_flow)

        await session.commit()
        await session.refresh(flow_version)

        logger.info(f"Flow version {version_id} submission cancelled by user {current_user.id}")

        return FlowVersionRead(
            id=flow_version.id,
            original_flow_id=flow_version.original_flow_id,
            version_flow_id=flow_version.version_flow_id,
            status_id=flow_version.status_id,
            version=flow_version.version,
            title=flow_version.title,
            description=flow_version.description,
            tags=flow_version.tags,
            agent_logo=flow_version.agent_logo,
            sample_id=flow_version.sample_id,
            submitted_by=flow_version.submitted_by,
            submitted_by_name=flow_version.submitted_by_name,
            submitted_by_email=flow_version.submitted_by_email,
            submitted_at=flow_version.submitted_at,
            reviewed_by=flow_version.reviewed_by,
            reviewed_by_name=flow_version.reviewed_by_name,
            reviewed_by_email=flow_version.reviewed_by_email,
            reviewed_at=flow_version.reviewed_at,
            rejection_reason=flow_version.rejection_reason,
            created_at=flow_version.created_at,
            updated_at=flow_version.updated_at,
            status_name=FlowStatusEnum.DRAFT.value,
            submitter_name=flow_version.submitted_by_name,
            submitter_email=flow_version.submitted_by_email,
            reviewer_name=flow_version.reviewed_by_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling submission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel submission: {str(e)}",
        )


@router.get("/{version_id}", response_model=FlowVersionRead)
async def get_version(
    version_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Get a single flow version with full details including flow data.
    """
    try:
        stmt = (
            select(FlowVersion)
            .where(FlowVersion.id == version_id)
            .options(
                joinedload(FlowVersion.submitter),
                joinedload(FlowVersion.reviewer),
                joinedload(FlowVersion.status),
                joinedload(FlowVersion.version_flow),
            )
        )
        result = await session.exec(stmt)
        flow_version = result.first()

        if not flow_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow version not found",
            )

        # Get flow data from the cloned version flow
        flow_data = None
        if flow_version.version_flow:
            flow_data = flow_version.version_flow.data

        return FlowVersionRead(
            id=flow_version.id,
            original_flow_id=flow_version.original_flow_id,
            version_flow_id=flow_version.version_flow_id,
            status_id=flow_version.status_id,
            version=flow_version.version,
            title=flow_version.title,
            description=flow_version.description,
            tags=flow_version.tags,
            agent_logo=flow_version.agent_logo,
            sample_id=flow_version.sample_id,
            submitted_by=flow_version.submitted_by,
            submitted_by_name=flow_version.submitted_by_name,
            submitted_by_email=flow_version.submitted_by_email,
            submitted_at=flow_version.submitted_at,
            reviewed_by=flow_version.reviewed_by,
            reviewed_by_name=flow_version.reviewed_by_name,
            reviewed_by_email=flow_version.reviewed_by_email,
            reviewed_at=flow_version.reviewed_at,
            rejection_reason=flow_version.rejection_reason,
            created_at=flow_version.created_at,
            updated_at=flow_version.updated_at,
            status_name=flow_version.status.status_name if flow_version.status else None,
            # Use stored name/email, fallback to User relationship for backward compatibility
            submitter_name=flow_version.submitted_by_name or (flow_version.submitter.username if flow_version.submitter else None),
            submitter_email=flow_version.submitted_by_email,
            reviewer_name=flow_version.reviewed_by_name or (flow_version.reviewer.username if flow_version.reviewer else None),
            flow_data=flow_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching flow version: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch flow version: {str(e)}",
        )


@router.get("/flow/{flow_id}/versions", response_model=list[FlowVersionRead])
async def get_flow_versions(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Get all versions for a specific flow.
    """
    try:
        stmt = (
            select(FlowVersion)
            .where(FlowVersion.original_flow_id == flow_id)
            .options(
                joinedload(FlowVersion.status),
                joinedload(FlowVersion.submitter),
            )
            .order_by(FlowVersion.created_at.desc())
        )
        result = await session.exec(stmt)
        versions = result.unique().all()

        return [
            FlowVersionRead(
                id=v.id,
                original_flow_id=v.original_flow_id,
                version_flow_id=v.version_flow_id,
                status_id=v.status_id,
                version=v.version,
                title=v.title,
                description=v.description,
                tags=v.tags,
                agent_logo=v.agent_logo,
                sample_id=v.sample_id,
                submitted_by=v.submitted_by,
                submitted_by_name=v.submitted_by_name,
                submitted_by_email=v.submitted_by_email,
                submitted_at=v.submitted_at,
                reviewed_by=v.reviewed_by,
                reviewed_by_name=v.reviewed_by_name,
                reviewed_by_email=v.reviewed_by_email,
                reviewed_at=v.reviewed_at,
                rejection_reason=v.rejection_reason,
                created_at=v.created_at,
                updated_at=v.updated_at,
                status_name=v.status.status_name if v.status else None,
                # Use stored name/email, fallback to User relationship for backward compatibility
                submitter_name=v.submitted_by_name or (v.submitter.username if v.submitter else None),
                submitter_email=v.submitted_by_email,
                reviewer_name=v.reviewed_by_name,
            )
            for v in versions
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching flow versions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch flow versions: {str(e)}",
        )


def _parse_version(version_str: str) -> tuple:
    """Parse a semantic version string into a tuple for comparison.

    Args:
        version_str: Version string like "1.0.0", "1.2.3", etc.

    Returns:
        Tuple of integers (major, minor, patch) for comparison.
        Returns (0, 0, 0) if parsing fails.
    """
    try:
        parts = version_str.split(".")
        return tuple(int(p) for p in parts[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _increment_patch_version(version_str: str) -> str:
    """Increment the patch version of a semantic version string.

    Args:
        version_str: Version string like "1.0.0"

    Returns:
        Incremented version string like "1.0.1"
    """
    try:
        parts = version_str.split(".")
        if len(parts) >= 3:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{major}.{minor}.{patch + 1}"
    except (ValueError, AttributeError):
        pass
    return "1.0.0"


def _calculate_suggested_version(all_versions: list) -> str:
    """Calculate the suggested version for publish modal based on flow_version entries.

    Logic:
    - If no entries: return "1.0.0"
    - If highest version has status=Submitted(2) or Rejected(4): return same version (can be published)
    - If highest version has status=Published(5): return incremented version
    - If highest version has status=Unpublished(6) or other: increment from highest published, or highest+1

    Args:
        all_versions: List of FlowVersion objects

    Returns:
        Suggested version string
    """
    if not all_versions:
        return "1.0.0"

    # Status IDs
    SUBMITTED = 2
    REJECTED = 4
    PUBLISHED = 5

    # Sort by version number semantically (highest first)
    sorted_versions = sorted(
        all_versions,
        key=lambda v: _parse_version(v.version) if v.version else (0, 0, 0),
        reverse=True
    )
    highest = sorted_versions[0]

    if highest.status_id in [SUBMITTED, REJECTED]:
        # Can reuse this version (submitted for review or rejected)
        return highest.version
    elif highest.status_id == PUBLISHED:
        # Increment from published
        return _increment_patch_version(highest.version)
    else:
        # Unpublished or other - find highest published and increment, or increment from highest
        published_versions = [v for v in sorted_versions if v.status_id == PUBLISHED]
        if published_versions:
            return _increment_patch_version(published_versions[0].version)
        else:
            return _increment_patch_version(highest.version)


@router.get("/flow/{flow_id}/latest-status")
async def get_flow_latest_status(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """
    Get the latest version status for a flow.

    Returns the most recent version's status, useful for UI to show
    current approval state in the flow header.
    Also returns suggested_version for publish modal.
    """
    try:
        # Fetch ALL versions for this flow to calculate suggested version
        all_versions_stmt = (
            select(FlowVersion)
            .where(FlowVersion.original_flow_id == flow_id)
            .options(
                joinedload(FlowVersion.status),
                joinedload(FlowVersion.input_sample),
            )
        )
        all_versions_result = await session.exec(all_versions_stmt)
        all_versions = all_versions_result.unique().all()

        # Calculate suggested version based on all versions
        suggested_version = _calculate_suggested_version(all_versions)

        # Find the latest version by created_at for other fields
        latest_version = None
        if all_versions:
            latest_version = max(all_versions, key=lambda v: v.created_at if v.created_at else datetime.min.replace(tzinfo=timezone.utc))

        if not latest_version:
            return {
                "has_submissions": False,
                "latest_status": None,
                "latest_version": None,
                "suggested_version": "1.0.0",
            }

        # Extract sample data if available
        input_sample = latest_version.input_sample
        sample_text = input_sample.sample_text if input_sample else None
        file_names = input_sample.file_names if input_sample else None

        # Check for PublishedFlow inputs (prioritize these if they exist)
        # This ensures that if a user updated inputs during publishing, those updates carry forward
        published_flow_stmt = (
            select(PublishedFlow)
            .where(PublishedFlow.flow_cloned_from == flow_id)
            .options(selectinload(PublishedFlow.input_samples))
        )
        published_flow_result = await session.exec(published_flow_stmt)
        published_flow = published_flow_result.first()

        if published_flow and published_flow.input_samples:
            # Use published flow inputs as they are the most recent "public" state
            # We take the first one as we enforce single record per published flow now
            latest_published_sample = published_flow.input_samples[0]
            sample_text = latest_published_sample.sample_text
            file_names = latest_published_sample.file_names

        return {
            "has_submissions": True,
            "latest_status": latest_version.status.status_name if latest_version.status else None,
            "latest_version": latest_version.version,
            "suggested_version": suggested_version,
            "latest_version_id": str(latest_version.id),
            "submitted_at": latest_version.submitted_at.isoformat() if latest_version.submitted_at else None,
            "reviewed_at": latest_version.reviewed_at.isoformat() if latest_version.reviewed_at else None,
            "rejection_reason": latest_version.rejection_reason,
            # Data for pre-populating re-submissions
            "sample_text": sample_text,
            "file_names": file_names,
            "agent_logo": latest_version.agent_logo,
            "tags": latest_version.tags,
        }

    except Exception as e:
        logger.error(f"Error fetching flow latest status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch flow status: {str(e)}",
        )
