from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.data_subjects.engine import MAX_ATTEMPTS
from langflow.services.data_subjects.worker import CANDIDATE_BATCH, DataSubjectEraseWorker
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
    DataSubjectType,
)
from langflow.services.deps import session_scope


def _approved(decided_at: datetime, error: dict | None = None) -> DataSubjectRequest:
    return DataSubjectRequest(
        subject_type=DataSubjectType.BUILDER.value,
        subject_user_id=uuid4(),
        source=DataSubjectRequestSource.ADMIN.value,
        status=DataSubjectRequestStatus.ERASING.value if error else DataSubjectRequestStatus.APPROVED.value,
        due_at=decided_at + timedelta(days=30),
        decided_at=decided_at,
        error=error,
    )


@pytest.mark.usefixtures("client")
async def test_should_reach_a_fresh_approval_behind_a_full_batch_of_exhausted_requests():
    start = datetime.now(timezone.utc) - timedelta(days=1)
    exhausted = {"attempts": MAX_ATTEMPTS, "retry_at": start.isoformat()}
    async with session_scope() as session:
        session.add_all(_approved(start + timedelta(seconds=i), exhausted) for i in range(CANDIDATE_BATCH))
        fresh = _approved(start + timedelta(hours=1))
        session.add(fresh)
        await session.flush()
        fresh_id = fresh.id

    due = await DataSubjectEraseWorker()._due_requests()

    assert due == [fresh_id]
