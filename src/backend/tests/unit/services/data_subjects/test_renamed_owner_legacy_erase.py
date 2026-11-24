"""Upgrading and erasing a legacy base whose owner was renamed before the upgrade, and a newcomer took the name.

The upgrade finds the base's directory under the former username by evidence and records it in the ledger,
so erasing the renamed owner removes it, and erasing the newcomer keeps it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.services.database.models.data_subject_request import DataSubjectRequestStatus
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.knowledge_base_storage import coordinator

from tests.unit.services.data_subjects._legacy_store import KB_NAME, OWNER, erase_builder, install_legacy_store
from tests.unit.services.data_subjects._seed import create_user

if TYPE_CHECKING:
    from pathlib import Path

RENAMED = "renamed-owner"

pytestmark = pytest.mark.no_blockbuster


async def _rename(user_id: UUID, username: str) -> None:
    async with session_scope() as session:
        user = await session.get(User, user_id)
        user.username = username
        session.add(user)


async def _base(user_id: UUID, name: str = KB_NAME, backend_type: str = "chroma") -> UUID:
    async with session_scope() as session:
        record = KnowledgeBaseRecord(
            name=name,
            user_id=user_id,
            backend_type=backend_type,
            model_selection={"provider": "OpenAI", "name": "text-embedding-3-small"},
        )
        session.add(record)
        await session.flush()
        return record.id


async def _run(kb_id: UUID) -> KnowledgeBaseStorageMigration:
    record = await knowledge_base_service.get_by_id(kb_id)
    async with session_scope() as session:
        return await session.get(KnowledgeBaseStorageMigration, record.active_migration_id)


def _snapshot(root: Path, kb_id: UUID, run: KnowledgeBaseStorageMigration) -> Path:
    return root / ".migration" / str(kb_id) / str(run.id) / "source"


async def test_should_erase_a_base_upgraded_from_a_former_name_only_with_its_renamed_owner(storage_root):
    owner = await create_user(OWNER)
    # 1.12 wrote no sidecar, but an older base's sidecar in the same folder shows the folder was the owner's.
    install_legacy_store(storage_root, OWNER)
    kb_id = await _base(owner)
    older = await _base(owner, "older", backend_type="sqlite")
    (storage_root / OWNER / "older").mkdir()
    (storage_root / OWNER / "older" / "embedding_metadata.json").write_text(json.dumps({"id": str(older)}))
    await _rename(owner, RENAMED)
    await coordinator.fence_legacy_records()
    await coordinator.migrate_one(kb_id)
    record = await knowledge_base_service.get_by_id(kb_id)
    assert (record.backend_type, record.storage_state) == ("sqlite", "ready")
    run = await _run(kb_id)
    assert run.source_identity == f"{OWNER}/{KB_NAME}"
    original, snapshot = storage_root / OWNER / KB_NAME, _snapshot(storage_root, kb_id, run)
    newcomer = await create_user(OWNER)
    # The ledger gives the directory to the renamed owner's base, so the newcomer may use its name.
    await knowledge_base_service.create_record(user_id=newcomer, name=KB_NAME)

    status, request = await erase_builder(newcomer)

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert (original / "chroma.sqlite3").is_file()
    assert snapshot.is_dir()

    status, request = await erase_builder(owner)

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert not (storage_root / OWNER).exists()
    assert not snapshot.exists()


async def test_should_keep_a_renamed_owners_memory_base_from_a_newcomer_when_its_sidecar_id_is_stale(
    storage_root, monkeypatch
):
    # The upgrade pass leaves its inventory status in the coordinator, so later tests start from the current one.
    for status in ("_inventory_complete", "_inventory_issue_count", "_inventory_scanned"):
        monkeypatch.setattr(coordinator, status, getattr(coordinator, status))
    owner = await create_user(OWNER)
    install_legacy_store(storage_root, OWNER)
    kb_id = await _base(owner)
    async with session_scope() as session:
        flow = Flow(name="support", user_id=owner)
        session.add(flow)
        await session.flush()
        session.add(MemoryBase(name="memory", kb_name=KB_NAME, flow_id=flow.id, user_id=owner))
    original = storage_root / OWNER / KB_NAME
    # 1.12 gave the Memory Base's row a new id, so the id its 1.11 sidecar records names no base.
    (original / "embedding_metadata.json").write_text(json.dumps({"id": str(uuid4()), "name": KB_NAME}))
    chunks = (original / "chroma.sqlite3").read_bytes()
    await _rename(owner, RENAMED)
    newcomer = await create_user(OWNER)

    await coordinator.fence_legacy_records()
    await coordinator.run_pending()

    # Nothing ties the directory to the renamed owner, so their base waits for an administrator.
    assert (await _run(kb_id)).error_code == "legacy_source_missing"
    # The newcomer holds the folder's name, but a base of that name may still be the one it holds.
    assert await knowledge_base_service.get_by_user_and_name(newcomer, KB_NAME) is None
    assert coordinator.inventory_status() == {"complete": False, "issues": 1}

    status, request = await erase_builder(newcomer)

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert (original / "chroma.sqlite3").read_bytes() == chunks
