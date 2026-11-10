"""A storage upgrade ledger row names its knowledge base by `<username>/<name>`, so it is the builder's data."""

from uuid import uuid4

import pytest
from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.requests import approve, create_builder_request
from langflow.services.database.models.data_subject_request import DataSubjectRequestSource, DataSubjectRequestStatus
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlmodel import select

from tests.unit.services.data_subjects._seed import create_user


def _ledger_row(source_identity: str) -> KnowledgeBaseStorageMigration:
    return KnowledgeBaseStorageMigration(
        kb_id=uuid4(), source_generation=1, target_generation=2, source_identity=source_identity
    )


@pytest.mark.usefixtures("client")
async def test_should_erase_the_builders_storage_upgrade_ledger_and_keep_other_builders():
    subject_id = await create_user("kb_owner")
    await create_user("kb_owner2")
    admin_id = await create_user("dsr-admin-kb", superuser=True)
    async with session_scope() as session:
        session.add_all(
            [
                _ledger_row("kb_owner/Customer notes"),
                _ledger_row("kb_owner/Deleted earlier"),
                _ledger_row("kb_owner2/Shared docs"),
                _ledger_row("kbXowner/Wildcard lookalike"),
            ]
        )

    async with session_scope() as session:
        request, _ = await create_builder_request(
            session,
            subject=await session.get(User, subject_id),
            requested_by=admin_id,
            source=DataSubjectRequestSource.ADMIN,
        )
        await approve(session, request, admin_id)
        request_id = request.id
    status = await run_request(request_id)

    assert status == DataSubjectRequestStatus.DONE.value
    async with session_scope() as session:
        remaining = set((await session.exec(select(KnowledgeBaseStorageMigration.source_identity))).all())
    assert remaining == {"kb_owner2/Shared docs", "kbXowner/Wildcard lookalike"}
