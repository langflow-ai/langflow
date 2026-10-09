"""Erase reaches the pre-upgrade Chroma copies that the automatic SQLite upgrade keeps for rollback."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.services.data_subjects.context import EraseContext
from langflow.services.data_subjects.end_user_legacy_copies import erase_retained_memory_copies
from langflow.services.data_subjects.identity import end_user_keys
from langflow.services.database.models.data_subject_request import DataSubjectRequestStatus
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.knowledge_base_storage import coordinator
from langflow.services.knowledge_base_storage.runtime import StorageUnavailableError, backend_for_record
from sqlmodel import delete

from tests.unit.services.data_subjects._legacy_store import (
    ALICE,
    BOB,
    KB_NAME,
    OWNER,
    erase_builder,
    erase_end_user,
    install_legacy_store,
)
from tests.unit.services.data_subjects._seed import create_user

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.no_blockbuster


async def _legacy_memory_base(root: Path, username: str) -> tuple[UUID, UUID]:
    owner = await create_user(username)
    install_legacy_store(root, username)
    async with session_scope() as session:
        flow = Flow(name="support", user_id=owner)
        session.add(flow)
        await session.flush()
        record = KnowledgeBaseRecord(
            name=KB_NAME,
            user_id=owner,
            backend_type="chroma",
            model_selection={"provider": "OpenAI", "name": "text-embedding-3-small"},
            source_types=["memory"],
        )
        session.add_all([record, MemoryBase(name="memory", kb_name=KB_NAME, flow_id=flow.id, user_id=owner)])
        await session.flush()
        return record.id, flow.id


async def _upgraded_memory_base(root: Path, username: str = OWNER) -> tuple[KnowledgeBaseRecord, UUID]:
    record_id, flow_id = await _legacy_memory_base(root, username)
    await coordinator.fence_legacy_records()
    await coordinator.migrate_one(record_id)
    record = await knowledge_base_service.get_by_id(record_id)
    assert (record.backend_type, record.storage_state) == ("sqlite", "ready")
    return record, flow_id


def _copies(root: Path, record: KnowledgeBaseRecord, username: str = OWNER) -> tuple[Path, Path]:
    snapshot = root / ".migration" / str(record.id) / str(record.active_migration_id) / "source"
    return root / username / KB_NAME, snapshot


async def _live_end_users(record: KnowledgeBaseRecord) -> list[str]:
    backend = await backend_for_record(record)
    try:
        return sorted(
            [
                doc.metadata["end_user_id"]
                async for batch in backend.iter_documents()
                for doc in batch
                if "end_user_id" in doc.metadata
            ]
        )
    finally:
        await backend.teardown()


async def _set_state(record_id: UUID, state: str) -> None:
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record_id)
        row.storage_state = state
        session.add(row)


async def _drop_memory_base_row() -> None:
    async with session_scope() as session:
        await session.exec(delete(MemoryBase).where(MemoryBase.kb_name == KB_NAME))


async def _rename(user_id: UUID, username: str) -> None:
    async with session_scope() as session:
        user = await session.get(User, user_id)
        user.username = username
        session.add(user)


async def _run_step_alone(end_user: str = ALICE) -> None:
    ctx = EraseContext(request_id=uuid4(), subject_user_id=uuid4(), end_user=end_user_keys(end_user))
    async with session_scope() as session:
        while await erase_retained_memory_copies(session, ctx):
            pass


def _binding(root: Path, username: str = OWNER) -> Path:
    digest = hashlib.sha256(f"{username}/{KB_NAME}".encode()).hexdigest()
    return root / ".migration" / "bindings" / f"{digest}.json"


async def test_should_remove_the_retained_copies_that_hold_the_end_users_chunks(storage_root):
    record, _ = await _upgraded_memory_base(storage_root)
    original, snapshot = _copies(storage_root, record)
    assert original.is_dir()
    assert snapshot.is_dir()

    status, request = await erase_end_user(ALICE)

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert await _live_end_users(record) == [BOB]
    assert not original.exists()
    assert not snapshot.exists()
    # The binding still fences the name, and the next startup scan accepts the removed source.
    assert _binding(storage_root).is_file()
    await coordinator.run_pending()
    assert coordinator.inventory_status() == {"complete": True, "issues": 0}


async def test_should_keep_the_retained_copies_when_the_end_user_has_no_chunks_there(storage_root):
    record, _ = await _upgraded_memory_base(storage_root)
    original, snapshot = _copies(storage_root, record)

    status, request = await erase_end_user("eu-carol-55d")

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert original.is_dir()
    assert snapshot.is_dir()


async def test_should_remove_the_copies_a_deleted_memory_base_left_behind(storage_root):
    record, _ = await _upgraded_memory_base(storage_root)
    original, snapshot = _copies(storage_root, record)
    await _drop_memory_base_row()
    # Deleting a base tombstones its live store and, by design, keeps the pre-upgrade copies.
    await knowledge_base_service.delete_record(record.id)
    assert original.is_dir()
    assert snapshot.is_dir()

    status, request = await erase_end_user(ALICE)

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert not original.exists()
    assert not snapshot.exists()


async def test_should_only_remove_the_copies_of_memory_bases_in_a_flow_scoped_erase(storage_root):
    record, flow_id = await _upgraded_memory_base(storage_root)
    original, snapshot = _copies(storage_root, record)
    async with session_scope() as session:
        other_flow = Flow(name="elsewhere", user_id=record.user_id)
        session.add(other_flow)
        await session.flush()
        other_flow_id = other_flow.id

    status, request = await erase_end_user(ALICE, scope_flow_ids=[other_flow_id])

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert original.is_dir()
    assert snapshot.is_dir()

    status, request = await erase_end_user(ALICE, scope_flow_ids=[flow_id])

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert not original.exists()
    assert not snapshot.exists()


async def test_should_keep_the_only_copy_of_a_memory_base_that_has_not_finished_upgrading(storage_root, monkeypatch):
    record_id, _ = await _legacy_memory_base(storage_root, OWNER)

    def interrupted(*_args, **_kwargs):
        msg = "export interrupted"
        raise OSError(msg)

    monkeypatch.setattr(coordinator, "export_local_snapshot", interrupted)
    await coordinator.fence_legacy_records()
    await coordinator.migrate_one(record_id)
    record = await knowledge_base_service.get_by_id(record_id)
    assert (record.backend_type, record.storage_state) == ("chroma", "needs_attention")
    original, snapshot = _copies(storage_root, record)
    assert snapshot.is_dir()
    # The engine holds such a request at memory_vectors, so drive this step on its own.
    await _run_step_alone()

    assert original.is_dir()
    assert snapshot.is_dir()


async def test_should_remove_the_upgrade_evidence_when_erasing_the_builder(storage_root):
    record, _ = await _upgraded_memory_base(storage_root)
    colleague, _ = await _upgraded_memory_base(storage_root, "colleague")
    colleague_original, colleague_snapshot = _copies(storage_root, colleague, "colleague")

    status, request = await erase_builder(record.user_id)

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert not (storage_root / OWNER).exists()
    assert not (storage_root / ".migration" / str(record.id)).exists()
    assert not _binding(storage_root).exists()
    assert colleague_original.is_dir()
    assert colleague_snapshot.is_dir()
    assert _binding(storage_root, "colleague").is_file()


async def test_should_wait_for_a_failed_deletion_before_erasing_its_copies(storage_root):
    record, _ = await _upgraded_memory_base(storage_root)
    original, snapshot = _copies(storage_root, record)
    await _drop_memory_base_row()
    # A deletion that failed after fencing the store leaves it ``deleting``, with its copies in place.
    await _set_state(record.id, "deleting")

    with pytest.raises(StorageUnavailableError):
        await _run_step_alone()

    assert original.is_dir()
    assert snapshot.is_dir()
    # Someone whose chunks are not there has nothing to wait for.
    await _run_step_alone("eu-carol-55d")

    await _set_state(record.id, "deleted")
    await _run_step_alone()

    assert not original.exists()
    assert not snapshot.exists()


async def test_should_remove_the_export_a_failed_upgrade_left_with_the_end_users_chunks(storage_root, monkeypatch):
    record_id, _ = await _legacy_memory_base(storage_root, OWNER)

    async def interrupted(*_args, **_kwargs):
        msg = "import interrupted"
        raise OSError(msg)

    monkeypatch.setattr(coordinator, "import_qualified_export", interrupted)
    await coordinator.fence_legacy_records()
    await coordinator.migrate_one(record_id)
    record = await knowledge_base_service.get_by_id(record_id)
    assert record.storage_state == "needs_attention"
    export = storage_root / ".migration" / str(record.id) / str(record.active_migration_id) / "export.jsonl"
    assert export.is_file()
    original, snapshot = _copies(storage_root, record)
    await _drop_memory_base_row()
    await knowledge_base_service.delete_record(record.id)

    status, request = await erase_end_user(ALICE)

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert not export.exists()
    assert not original.exists()
    assert not snapshot.exists()


async def test_should_erase_the_upgrade_evidence_kept_under_a_builders_former_name(storage_root):
    record, _ = await _upgraded_memory_base(storage_root)
    original, _ = _copies(storage_root, record)
    await _rename(record.user_id, "renamed-owner")

    status, request = await erase_builder(record.user_id)

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert not original.exists()
    assert not (storage_root / ".migration" / str(record.id)).exists()
    assert not _binding(storage_root).exists()


async def test_should_leave_a_renamed_builders_upgrade_evidence_when_erasing_whoever_took_the_name(storage_root):
    record, _ = await _upgraded_memory_base(storage_root)
    await _rename(record.user_id, "renamed-owner")
    newcomer = await create_user(OWNER)

    status, request = await erase_builder(newcomer)

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert (storage_root / ".migration" / str(record.id)).is_dir()
    assert _binding(storage_root).is_file()
    async with session_scope() as session:
        assert await session.get(KnowledgeBaseStorageMigration, record.active_migration_id) is not None
