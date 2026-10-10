"""Erase and the application database backup that the automatic storage upgrade keeps while it runs."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.services.data_subjects.audit_events import ACTION_ERASE
from langflow.services.data_subjects.engine import RETAINED_BACKUPS, STORAGE_LOCATIONS
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.database.models.data_subject_request import DataSubjectRequestStatus
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.service import get_sqlite_database_file_path
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from langflow.services.knowledge_base_storage import application_backup, coordinator
from langflow.services.knowledge_base_storage.application_backup import backup_directory, backup_path
from langflow.services.knowledge_base_storage.cleanup import detach_attention_store
from sqlmodel import select

from tests.unit.services.data_subjects._legacy_store import (
    ALICE,
    KB_NAME,
    OWNER,
    erase_builder,
    erase_end_user,
    install_legacy_store,
)
from tests.unit.services.data_subjects._seed import create_user, end_user_message

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

pytestmark = pytest.mark.no_blockbuster

DONE = DataSubjectRequestStatus.DONE.value
MESSAGE = "Deliver it to 12 Elm Street"


def _backup(root: Path) -> Path:
    database = get_sqlite_database_file_path(get_db_service().database_url)
    assert database is not None
    return backup_path(backup_directory(root), database)


def _backed_up_messages(backup: Path) -> list[str]:
    with closing(sqlite3.connect(f"{backup.as_uri()}?mode=ro", uri=True)) as connection:
        return [text for (text,) in connection.execute("SELECT text FROM message")]


async def _live_messages() -> list[str]:
    async with session_scope() as session:
        return list((await session.exec(select(MessageTable.text))).all())


async def _legacy_knowledge_base(root: Path) -> UUID:
    """A 1.12.x knowledge base, and an end user's message that the upgrade's backup will hold."""
    owner = await create_user(OWNER)
    install_legacy_store(root, OWNER)
    async with session_scope() as session:
        flow = Flow(name="support", user_id=owner)
        session.add(flow)
        await session.flush()
        record = KnowledgeBaseRecord(
            name=KB_NAME,
            user_id=owner,
            backend_type="chroma",
            model_selection={"provider": "OpenAI", "name": "text-embedding-3-small"},
        )
        session.add_all([record, end_user_message(flow.id, ALICE, MESSAGE)])
        await session.flush()
        return record.id


async def _stalled_upgrade(root: Path, monkeypatch) -> KnowledgeBaseRecord:
    """An upgrade pass whose only base fails after the backup was taken, so the base needs attention."""
    record_id = await _legacy_knowledge_base(root)

    def interrupted(*_args, **_kwargs):
        msg = "export interrupted"
        raise OSError(msg)

    monkeypatch.setattr(coordinator, "export_local_snapshot", interrupted)
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()
    record = await knowledge_base_service.get_by_id(record_id)
    assert (record.backend_type, record.storage_state) == ("chroma", "needs_attention")
    assert _backed_up_messages(_backup(root)) == [MESSAGE]
    return record


async def _settle(record: KnowledgeBaseRecord) -> None:
    """Detach the base that held the upgrade open. This settles the upgrade outside a coordinator pass."""
    await detach_attention_store(record.id, expected_generation=record.storage_generation)


async def _erase_event(request_id: UUID) -> dict:
    async with session_scope() as session:
        event = (
            await session.exec(
                select(AuthzAuditLog).where(
                    AuthzAuditLog.action == ACTION_ERASE, AuthzAuditLog.resource_id == request_id
                )
            )
        ).one()
    return event.details


async def test_should_delete_the_backup_once_the_upgrade_finishes(storage_root):
    record_id = await _legacy_knowledge_base(storage_root)

    await coordinator.fence_legacy_records()
    await coordinator.run_pending()

    record = await knowledge_base_service.get_by_id(record_id)
    assert (record.backend_type, record.storage_state) == ("sqlite", "ready")
    # The run recorded where its backup was, and the pass that finished the upgrade deleted it.
    run_directory = storage_root / ".migration" / str(record.id) / str(record.active_migration_id)
    assert (run_directory / "application-backup.json").is_file()
    assert not _backup(storage_root).exists()


async def test_should_finish_the_upgrade_when_its_backup_cannot_be_deleted(storage_root, monkeypatch):
    record_id = await _legacy_knowledge_base(storage_root)

    def denied(*_args, **_kwargs):
        msg = "read-only volume"
        raise PermissionError(msg)

    monkeypatch.setattr(application_backup, "remove_backups", denied)

    await coordinator.fence_legacy_records()
    await coordinator.run_pending()

    record = await knowledge_base_service.get_by_id(record_id)
    assert (record.backend_type, record.storage_state) == ("sqlite", "ready")
    assert _backup(storage_root).exists()


async def test_should_keep_and_report_the_backup_while_a_base_needs_attention(storage_root, monkeypatch):
    await _stalled_upgrade(storage_root, monkeypatch)

    status, request = await erase_end_user(ALICE)

    assert status == DONE, request.error
    assert MESSAGE not in await _live_messages()
    # The base may still need the backup, so the erase leaves it and says so.
    assert _backed_up_messages(_backup(storage_root)) == [MESSAGE]
    assert request.counts["retained_backups"] == 1
    details = await _erase_event(request.id)
    assert details["backups_not_reached"] == 1
    assert details["rows_deleted"] == sum(
        value
        for key, value in request.counts.items()
        if isinstance(value, int) and key not in (STORAGE_LOCATIONS, RETAINED_BACKUPS)
    )


async def test_should_delete_the_backup_when_erasing_after_the_upgrade_settled(storage_root, monkeypatch):
    record = await _stalled_upgrade(storage_root, monkeypatch)
    await _settle(record)
    assert _backup(storage_root).exists()

    status, request = await erase_end_user(ALICE)

    assert status == DONE, request.error
    assert not _backup(storage_root).exists()
    assert request.counts["retained_backups"] == 0
    assert (await _erase_event(request.id))["backups_not_reached"] == 0


async def test_should_leave_the_backup_to_an_upgrade_pass_that_is_running(storage_root, monkeypatch):
    record = await _stalled_upgrade(storage_root, monkeypatch)
    await _settle(record)

    async with application_backup.upgrade_pass():
        status, request = await erase_end_user(ALICE)

    assert status == DONE, request.error
    assert _backup(storage_root).exists()
    assert request.counts["retained_backups"] == 1
    # That pass, or the next one, finds the upgrade finished and deletes the backup.
    await coordinator.run_pending()
    assert not _backup(storage_root).exists()


async def test_should_report_a_backup_that_the_erase_could_not_delete(storage_root, monkeypatch):
    record = await _stalled_upgrade(storage_root, monkeypatch)
    await _settle(record)

    def denied(*_args, **_kwargs):
        msg = "read-only volume"
        raise PermissionError(msg)

    monkeypatch.setattr(application_backup, "remove_backups", denied)

    status, request = await erase_end_user(ALICE)

    # The rows are gone and the erase completes. It does not claim the backup it could not delete.
    assert status == DONE, request.error
    assert MESSAGE not in await _live_messages()
    assert _backup(storage_root).exists()
    assert request.counts["retained_backups"] == 1
    assert (await _erase_event(request.id))["backups_not_reached"] == 1


async def test_should_keep_the_backup_while_discovery_is_incomplete(storage_root, monkeypatch):
    record = await _stalled_upgrade(storage_root, monkeypatch)
    await _settle(record)

    async def incomplete() -> dict:
        return {"complete": False, "issues": 1}

    # An unreadable legacy directory may still become a base that the upgrade has to copy.
    monkeypatch.setattr(coordinator, "published_inventory_status", incomplete)

    status, request = await erase_end_user(ALICE)

    assert status == DONE, request.error
    assert _backup(storage_root).exists()
    assert request.counts["retained_backups"] == 1


async def test_should_count_but_keep_the_backup_of_another_database(storage_root, monkeypatch):
    record = await _stalled_upgrade(storage_root, monkeypatch)
    await _settle(record)
    other = backup_path(backup_directory(storage_root), storage_root / "other-langflow.db")
    other.write_bytes(b"another application's rows")

    status, request = await erase_end_user(ALICE)

    assert status == DONE, request.error
    assert not _backup(storage_root).exists()
    assert other.exists()
    assert request.counts["retained_backups"] == 1


async def test_should_report_the_backup_when_erasing_a_builder_while_a_base_needs_attention(storage_root, monkeypatch):
    await _stalled_upgrade(storage_root, monkeypatch)
    builder = await create_user("departing-builder")

    status, request = await erase_builder(builder)

    assert status == DONE, request.error
    assert _backup(storage_root).exists()
    assert request.counts["retained_backups"] == 1
    assert (await _erase_event(request.id))["backups_not_reached"] == 1


async def test_should_delete_the_backup_when_erasing_the_builder_whose_base_held_the_upgrade_open(
    storage_root, monkeypatch
):
    record = await _stalled_upgrade(storage_root, monkeypatch)

    status, request = await erase_builder(record.user_id)

    assert status == DONE, request.error
    assert await knowledge_base_service.get_by_id(record.id) is None
    assert not _backup(storage_root).exists()
    assert request.counts["retained_backups"] == 0


async def test_should_report_no_backup_without_local_knowledge_storage(client, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", None)

    status, request = await erase_end_user(ALICE)

    assert status == DONE, request.error
    assert request.counts["retained_backups"] == 0
    assert (await _erase_event(request.id))["backups_not_reached"] == 0
