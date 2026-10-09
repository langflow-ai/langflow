"""The upgrade finds a base's legacy directory by evidence, whatever username its owner holds now.

A 1.12 directory stays under the username its owner had when it was written. These cover an owner renamed
before the upgrade, and a newcomer who takes the old name.
"""

from __future__ import annotations

import json
import tarfile
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.user.model import User
from langflow.services.knowledge_base_storage import cleanup, coordinator, maintenance, runtime
from sqlmodel import select

from . import test_storage_upgrade as storage_tests

database = storage_tests.database
read_kb = storage_tests.read_kb
created_now = storage_tests.created_now

pytestmark = pytest.mark.no_blockbuster

# The native Chroma 1.5.9 fixture holds one collection, named after its base.
KB_NAME = "fixture-l2"
FIXTURES = Path(__file__).resolve().parents[6] / "src/lfx/tests/unit/base/knowledge_bases/fixtures"
FIXTURE = FIXTURES / "chroma-1.5.9-local.tar.gz"
FORMER = "owner"
RENAMED = "renamed"


def legacy_store(
    database, folder: str, name: str = KB_NAME, *, sidecar: dict[str, Any] | None = None, native: bool = True
) -> Path:
    """A legacy directory: the real native store, or a placeholder for a base that is never copied."""
    source = database.root / folder / name
    if native:
        with tarfile.open(FIXTURE) as archive:
            for member in archive:
                if member.isfile() and member.name.startswith("source/"):
                    destination = source / Path(member.name).relative_to("source")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as stream:
                        destination.write_bytes(stream.read())
    else:
        source.mkdir(parents=True)
        (source / "chroma.sqlite3").write_bytes(b"legacy chunks")
    if sidecar is not None:
        (source / "embedding_metadata.json").write_text(json.dumps(sidecar))
    return source


async def add_user(database, username: str) -> UUID:
    user = User(username=username, password=uuid4().hex, is_active=True)
    async with database.sessions() as session:
        session.add(user)
        await session.commit()
    return user.id


async def add_base(database, user_id: UUID, name: str = KB_NAME, **fields: Any) -> UUID:
    row = KnowledgeBaseRecord(user_id=user_id, name=name, backend_type="chroma", **fields)
    async with database.sessions() as session:
        session.add(row)
        await session.commit()
    return row.id


async def rename(database, user_id: UUID, username: str) -> None:
    async with database.sessions() as session:
        user = await session.get(User, user_id)
        user.username = username
        session.add(user)
        await session.commit()


async def run_of(database, kb_id: UUID) -> KnowledgeBaseStorageMigration:
    row = await read_kb(database, kb_id)
    async with database.sessions() as session:
        return await session.get(KnowledgeBaseStorageMigration, row.active_migration_id)


async def bases_of(database, user_id: UUID) -> list[KnowledgeBaseRecord]:
    async with database.sessions() as session:
        statement = select(KnowledgeBaseRecord).where(KnowledgeBaseRecord.user_id == user_id)
        return list((await session.exec(statement)).all())


async def delete_base(database, kb_id: UUID) -> None:
    await runtime.delete_storage_for_record(await read_kb(database, kb_id))
    async with database.sessions() as session:
        await session.delete(await session.get(KnowledgeBaseRecord, kb_id))
        await session.commit()


def inventory(database) -> list[dict[str, str]]:
    return json.loads((database.root / ".migration" / "inventory.json").read_text())["issues"]


async def upgrade() -> None:
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()


async def test_should_upgrade_a_renamed_owners_base_from_the_directory_its_sidecar_names(database):
    kb_id = await add_base(database, database.user.id)
    source = legacy_store(database, FORMER, sidecar={"id": str(kb_id)})
    original = maintenance.tree_fingerprint(source)
    await rename(database, database.user.id, RENAMED)

    await upgrade()

    current = await read_kb(database, kb_id)
    assert (current.backend_type, current.storage_state, current.chunks) == ("sqlite", "ready", 239)
    assert (await run_of(database, kb_id)).source_identity == f"{FORMER}/{KB_NAME}"
    # Nobody holds the former name, yet the directory is its base's, not an ownerless one.
    assert coordinator.inventory_status() == {"complete": True, "issues": 0}
    assert maintenance.tree_fingerprint(source) == original


async def test_should_find_a_renamed_owners_base_under_a_former_name_that_another_base_shows(database):
    # 1.12 wrote no sidecar, but an older base in the same folder records its id, so the folder was the owner's.
    older = await add_base(database, database.user.id, "older")
    legacy_store(database, FORMER, "older", sidecar={"id": str(older)}, native=False)
    kb_id = await add_base(database, database.user.id)
    legacy_store(database, FORMER)
    await rename(database, database.user.id, RENAMED)

    await upgrade()

    current = await read_kb(database, kb_id)
    assert (current.backend_type, current.storage_state, current.chunks) == ("sqlite", "ready", 239)
    assert (await run_of(database, kb_id)).source_identity == f"{FORMER}/{KB_NAME}"
    assert (await run_of(database, older)).source_identity == f"{FORMER}/older"


@pytest.mark.parametrize("newcomer", [False, True])
async def test_should_keep_a_renamed_owners_base_waiting_when_nothing_ties_its_directory_to_them(database, newcomer):
    kb_id = await add_base(database, database.user.id, "knowledge")
    source = legacy_store(database, FORMER, "knowledge", native=False)
    await rename(database, database.user.id, RENAMED)
    newcomer_id = await add_user(database, FORMER) if newcomer else None

    await upgrade()

    assert (await read_kb(database, kb_id)).storage_state == "needs_attention"
    run = await run_of(database, kb_id)
    assert (run.error_code, run.source_identity) == ("legacy_source_missing", None)
    # Whoever holds the folder's name now does not adopt it, and the inventory says why.
    expected = {"code": "unattributed_legacy_source", "owner_id": str(newcomer_id)} if newcomer else None
    assert inventory(database) == [expected or {"code": "missing_source_owner"}]
    if newcomer_id:
        assert await bases_of(database, newcomer_id) == []
    assert not await coordinator.readiness()
    assert (source / "chroma.sqlite3").read_bytes() == b"legacy chunks"


async def test_should_not_let_a_newcomer_adopt_the_directory_of_a_renamed_owners_base(database):
    kb_id = await add_base(database, database.user.id)
    legacy_store(database, FORMER, sidecar={"id": str(kb_id)})
    await rename(database, database.user.id, RENAMED)
    newcomer = await add_user(database, FORMER)

    await upgrade()

    assert (await read_kb(database, kb_id)).storage_state == "ready"
    assert await bases_of(database, newcomer) == []
    assert coordinator.inventory_status() == {"complete": True, "issues": 0}


async def test_should_not_let_a_newcomer_adopt_a_renamed_owners_directory_whose_sidecar_id_is_stale(database):
    kb_id = await add_base(database, database.user.id, chunks=239)
    await rename(database, database.user.id, RENAMED)
    newcomer = await add_user(database, FORMER)
    # 1.12 gave the rows of older Memory Bases new ids, so the sidecar names a base that no longer exists.
    # Even a creation time after the newcomer joined does not make it theirs while the owner's base has none.
    sidecar = {"id": str(uuid4()), "name": KB_NAME, "created_at": created_now()}
    source = legacy_store(database, FORMER, sidecar=sidecar, native=False)

    await upgrade()

    assert await bases_of(database, newcomer) == []
    assert inventory(database) == [{"code": "unattributed_legacy_source", "owner_id": str(newcomer)}]
    assert (await run_of(database, kb_id)).error_code == "legacy_source_missing"
    assert (source / "chroma.sqlite3").read_bytes() == b"legacy chunks"


async def test_should_not_let_a_newcomer_adopt_a_disk_only_base_in_a_folder_another_account_held(database):
    older = await add_base(database, database.user.id, "older")
    legacy_store(database, FORMER, "older", sidecar={"id": str(older)}, native=False)
    await rename(database, database.user.id, RENAMED)
    newcomer = await add_user(database, FORMER)
    disk_only = uuid4()
    sidecar = {"id": str(disk_only), "created_at": created_now()}
    legacy_store(database, FORMER, "notes", sidecar=sidecar, native=False)

    await coordinator.reconcile_legacy_inventory()

    assert await read_kb(database, disk_only) is None
    assert inventory(database) == [{"code": "unattributed_legacy_source", "owner_id": str(newcomer)}]


async def test_should_not_adopt_a_directory_without_a_recorded_id_for_whoever_holds_its_folder(database):
    legacy_store(database, FORMER, "knowledge", sidecar={"name": "knowledge", "embedding_model": "fixed"}, native=False)

    await coordinator.reconcile_legacy_inventory()

    assert await bases_of(database, database.user.id) == []
    assert inventory(database) == [{"code": "unattributed_legacy_source", "owner_id": str(database.user.id)}]


@pytest.mark.parametrize(("offset", "adopted"), [(timedelta(days=-1), False), (timedelta(days=1), True)])
async def test_should_adopt_a_disk_only_base_only_for_an_account_that_existed_when_it_was_created(
    database, offset, adopted
):
    disk_only = uuid4()
    created = database.user.create_at + offset
    sidecar = {"id": str(disk_only), "created_at": created.isoformat()}
    legacy_store(database, FORMER, sidecar=sidecar, native=False)

    await coordinator.reconcile_legacy_inventory()

    assert (await read_kb(database, disk_only) is not None) is adopted
    if adopted:
        # Adoption records the directory in the base's ledger run, so a later rename cannot move it.
        assert (await run_of(database, disk_only)).source_identity == f"{FORMER}/{KB_NAME}"
    else:
        assert inventory(database) == [{"code": "unattributed_legacy_source", "owner_id": str(database.user.id)}]


async def test_should_hold_a_directory_that_a_renamed_owner_and_a_newcomer_both_may_own(database):
    older = await add_base(database, database.user.id, "older")
    legacy_store(database, FORMER, "older", sidecar={"id": str(older)}, native=False)
    renamed_kb = await add_base(database, database.user.id, "knowledge")
    legacy_store(database, FORMER, "knowledge", native=False)
    await rename(database, database.user.id, RENAMED)
    newcomer = await add_user(database, FORMER)
    newcomer_kb = await add_base(database, newcomer, "knowledge")

    await upgrade()

    for kb_id in (renamed_kb, newcomer_kb):
        run = await run_of(database, kb_id)
        assert (run.error_code, run.source_identity) == ("legacy_source_ambiguous", None)
    assert {"code": "ambiguous_source_identity"} in inventory(database)


async def test_should_keep_the_recorded_directory_when_the_owner_is_renamed_after_a_failed_attempt(
    database, monkeypatch
):
    kb_id = await add_base(database, database.user.id)
    legacy_store(database, FORMER)

    def refused(*_args):
        msg = "another worker holds the storage"
        raise maintenance.MaintenanceRequiredError(msg)

    monkeypatch.setattr(coordinator, "check_local_upgrade", refused)
    await upgrade()
    assert (await run_of(database, kb_id)).source_identity == f"{FORMER}/{KB_NAME}"
    await rename(database, database.user.id, RENAMED)
    monkeypatch.setattr(coordinator, "check_local_upgrade", lambda *_args: None)

    await coordinator.migrate_one(kb_id)

    current = await read_kb(database, kb_id)
    assert (current.backend_type, current.storage_state, current.chunks) == ("sqlite", "ready", 239)


async def test_should_upgrade_an_adopted_base_whose_owner_is_renamed_before_the_copy(database):
    kb_id = uuid4()
    legacy_store(database, FORMER, sidecar={"id": str(kb_id), "name": KB_NAME, "created_at": created_now()})
    await coordinator.reconcile_legacy_inventory()
    await rename(database, database.user.id, RENAMED)

    await coordinator.migrate_one(kb_id)

    current = await read_kb(database, kb_id)
    assert (current.user_id, current.storage_state, current.chunks) == (database.user.id, "ready", 239)


async def test_should_not_retire_a_renamed_owners_directory_when_a_newcomer_deletes_a_base_of_that_name(database):
    kb_id = await add_base(database, database.user.id)
    legacy_store(database, FORMER, sidecar={"id": str(kb_id)})
    await rename(database, database.user.id, RENAMED)
    newcomer = await add_user(database, FORMER)
    newcomer_kb = await add_base(database, newcomer, storage_state="needs_attention")

    await delete_base(database, newcomer_kb)

    assert not coordinator._binding_path(f"{FORMER}/{KB_NAME}").exists()
    await upgrade()
    current = await read_kb(database, kb_id)
    assert (current.backend_type, current.storage_state, current.chunks) == ("sqlite", "ready", 239)
    assert coordinator.inventory_status() == {"complete": True, "issues": 0}


async def test_should_retire_a_renamed_owners_directory_under_the_former_name_when_its_base_is_deleted(database):
    kb_id = await add_base(database, database.user.id, "knowledge", storage_state="needs_attention")
    legacy_store(database, FORMER, "knowledge", sidecar={"id": str(kb_id)}, native=False)
    await rename(database, database.user.id, RENAMED)

    await delete_base(database, kb_id)

    binding = json.loads(coordinator._binding_path(f"{FORMER}/knowledge").read_text())
    assert (binding["kb_id"], binding["retired"]) == (str(kb_id), True)
    # A newcomer who takes the name finds nothing to adopt, and the deleted base stays deleted.
    newcomer = await add_user(database, FORMER)
    await coordinator.reconcile_legacy_inventory()
    assert await bases_of(database, newcomer) == []
    assert coordinator.inventory_status() == {"complete": True, "issues": 0}


async def test_should_reserve_a_name_held_under_a_renamed_owners_former_username(database):
    older = await add_base(database, database.user.id, "older")
    legacy_store(database, FORMER, "older", sidecar={"id": str(older)}, native=False)
    # A base on disk only, that startup adoption has not registered yet.
    legacy_store(database, FORMER, "notes", sidecar={"id": str(uuid4())}, native=False)
    await rename(database, database.user.id, RENAMED)
    newcomer = await add_user(database, FORMER)

    for user_id in (database.user.id, newcomer):
        with pytest.raises(runtime.StorageUnavailableError, match="held by data from a previous version"):
            await coordinator.ensure_legacy_name_available(user_id, "notes")
    # The renamed owner's base holds its directory, so the newcomer may use that name.
    await coordinator.ensure_legacy_name_available(newcomer, "older")


@pytest.mark.parametrize("resolution", ["detach", "delete"])
async def test_should_not_let_a_newcomer_adopt_a_renamed_owners_directory_once_its_base_is_resolved(
    database, monkeypatch, resolution
):
    monkeypatch.setattr(cleanup, "session_scope", database.sessions)
    kb_id = await add_base(database, database.user.id, chunks=239)
    # 1.11 recorded no creation time when it backfilled an id into an older sidecar.
    source = legacy_store(database, FORMER, sidecar={"id": str(uuid4()), "name": KB_NAME}, native=False)
    await rename(database, database.user.id, RENAMED)
    newcomer = await add_user(database, FORMER)
    await upgrade()
    assert (await run_of(database, kb_id)).error_code == "legacy_source_missing"

    # The usual answers to a base that needs attention leave nothing that waits for the directory.
    if resolution == "detach":
        await cleanup.detach_attention_store(kb_id, expected_generation=1)
    else:
        await delete_base(database, kb_id)
    await coordinator.reconcile_legacy_inventory()

    assert await bases_of(database, newcomer) == []
    assert inventory(database) == [{"code": "unattributed_legacy_source", "owner_id": str(newcomer)}]
    assert (source / "chroma.sqlite3").read_bytes() == b"legacy chunks"


async def test_should_hold_a_directory_a_newcomers_base_may_own_when_a_renamed_owners_base_lost_its_data(database):
    # Nothing shows the renamed owner held the name, but their base of that name holds data and found no directory.
    renamed_kb = await add_base(database, database.user.id, "knowledge", chunks=12)
    legacy_store(database, FORMER, "knowledge", native=False)
    await rename(database, database.user.id, RENAMED)
    newcomer = await add_user(database, FORMER)
    newcomer_kb = await add_base(database, newcomer, "knowledge")

    await upgrade()

    for kb_id in (renamed_kb, newcomer_kb):
        run = await run_of(database, kb_id)
        assert (run.error_code, run.source_identity) == ("legacy_source_ambiguous", None)
    assert {"code": "ambiguous_source_identity"} in inventory(database)


async def test_should_let_a_newcomer_create_a_base_of_the_name_without_blocking_the_renamed_owners_upgrade(
    database, monkeypatch
):
    monkeypatch.setattr(knowledge_base_service, "session_scope", database.sessions)
    older = await add_base(database, database.user.id, "older")
    legacy_store(database, FORMER, "older", sidecar={"id": str(older)}, native=False)
    kb_id = await add_base(database, database.user.id)
    legacy_store(database, FORMER)
    await rename(database, database.user.id, RENAMED)
    newcomer = await add_user(database, FORMER)

    # The renamed owner's base holds the directory, so the name is free for a new SQLite base.
    created = await knowledge_base_service.create_record(user_id=newcomer, name=KB_NAME)
    await upgrade()

    current = await read_kb(database, kb_id)
    assert (current.backend_type, current.storage_state, current.chunks) == ("sqlite", "ready", 239)
    assert (await read_kb(database, created.id)).storage_state == "ready"


async def test_should_locate_a_directory_again_when_it_moved_before_the_copy(database, monkeypatch):
    kb_id = await add_base(database, database.user.id)
    source = legacy_store(database, FORMER)

    def refused(*_args):
        msg = "another worker holds the storage"
        raise maintenance.MaintenanceRequiredError(msg)

    monkeypatch.setattr(coordinator, "check_local_upgrade", refused)
    await upgrade()
    assert (await run_of(database, kb_id)).source_identity == f"{FORMER}/{KB_NAME}"
    # An administrator renames the owner and moves the directory to match, as the guidance says.
    await rename(database, database.user.id, RENAMED)
    (database.root / RENAMED).mkdir()
    source.rename(database.root / RENAMED / KB_NAME)
    monkeypatch.setattr(coordinator, "check_local_upgrade", lambda *_args: None)

    await coordinator.migrate_one(kb_id)

    current = await read_kb(database, kb_id)
    assert (current.storage_state, current.chunks) == ("ready", 239)
    assert (await run_of(database, kb_id)).source_identity == f"{RENAMED}/{KB_NAME}"
