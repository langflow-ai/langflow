"""Deletion-request state for the admin users table (the badge and its filter)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlmodel import col, select

from langflow.services.database.models.data_subject_request import (
    OPEN_STATUSES,
    DataSubjectRequest,
    DataSubjectType,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


def _is_open_builder_request():
    return (
        DataSubjectRequest.subject_type == DataSubjectType.BUILDER.value,
        col(DataSubjectRequest.status).in_([status.value for status in OPEN_STATUSES]),
    )


def open_deletion_request_subjects():
    """Subquery of user ids with an open account deletion request."""
    return select(DataSubjectRequest.subject_user_id).where(*_is_open_builder_request())


async def open_deletion_request_statuses(session: AsyncSession, user_ids: list[UUID]) -> dict[str, str]:
    """Status of each listed user's open request; empty while the feature is off."""
    if not FEATURE_FLAGS.data_subject_requests or not user_ids:
        return {}
    rows = (
        await session.exec(
            select(DataSubjectRequest).where(
                *_is_open_builder_request(), col(DataSubjectRequest.subject_user_id).in_(user_ids)
            )
        )
    ).all()
    return {str(row.subject_user_id): row.status for row in rows}
