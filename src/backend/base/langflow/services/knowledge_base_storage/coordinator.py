"""Durable automatic local KB upgrade, with unpublished generations and routing CAS."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext
from lfx.base.knowledge_bases.migration import import_qualified_export, qualify_export
from lfx.base.knowledge_bases.migration.protocol import MigrationProtocolError
from lfx.log.logger import logger
from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.user.model import User
from langflow.services.database.service import get_sqlite_database_file_path
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from langflow.services.knowledge_base_storage import helper
from langflow.services.knowledge_base_storage.maintenance import (
    MaintenanceRequiredError,
    _fsync_directory,
    snapshot_source,
    tree_fingerprint,
    validate_receipt,
)
from langflow.services.knowledge_base_storage.runtime import (
    StorageUnavailableError,
    operation,
    private_directory,
    storage_root,
)

_tasks: set[asyncio.Task] = set()
_inventory_complete = True
_inventory_issue_count = 0
_MAX_BINDING_BYTES = 4096
_SOURCE_PATH_PARTS = 2


async def _worker(function, *args, **kwargs):
    """Cancellation never releases the fence while snapshot/import work is live."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        task.exception()
        raise asyncio.CancelledError
    return task.result()


def _model_fingerprint(record: KnowledgeBaseRecord) -> str:
    selection = record.model_selection
    if isinstance(selection, list):
        selection = selection[0] if selection else {}
    # Non-secret identity only. Never copy embedding-provider credentials.
    identity = {key: selection.get(key) for key in ("provider", "name")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def _phase(migration_id: UUID, phase: str, **changes) -> None:
    async with session_scope() as session:
        run = await session.get(KnowledgeBaseStorageMigration, migration_id)
        run.phase = phase
        run.updated_at = datetime.now(timezone.utc)
        for key, value in changes.items():
            setattr(run, key, value)
        await session.commit()


async def _prepare(record: KnowledgeBaseRecord) -> KnowledgeBaseStorageMigration:
    async with session_scope() as session:
        current = await session.get(KnowledgeBaseRecord, record.id)
        run = (
            await session.get(KnowledgeBaseStorageMigration, current.active_migration_id)
            if current.active_migration_id
            else None
        )
        if run is None:
            run = KnowledgeBaseStorageMigration(
                kb_id=current.id,
                source_backend=current.backend_type,
                source_generation=current.storage_generation,
                target_generation=current.storage_generation + 1,
            )
            session.add(run)
            current.active_migration_id = run.id
        current.storage_state = "migrating"
        run.attempts += 1
        run.error_code = None
        run.coordinator = f"{socket.gethostname()}:{os.getpid()}"
        run.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(run)
        return run


async def _attention(kb_id: UUID, migration_id: UUID, code: str) -> None:
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, kb_id)
        run = await session.get(KnowledgeBaseStorageMigration, migration_id)
        if row is not None and row.active_migration_id == migration_id:
            row.storage_state = "needs_attention"
        if run is not None:
            run.phase = "needs_attention"
            run.error_code = code
            run.updated_at = datetime.now(timezone.utc)
        await session.commit()


async def _complete(row: KnowledgeBaseRecord, run: KnowledgeBaseStorageMigration, target: SQLiteBackend) -> None:
    await target.ensure_ready()
    manifest = await target.read_migration_manifest()
    if (
        manifest is None
        or manifest.get("status") != "complete"
        or manifest.get("migration_id") != str(run.id)
        or await target.count() != manifest.get("count")
    ):
        msg = "Activated target lacks a verified completed migration"
        raise MigrationProtocolError(msg)
    await target.integrity_check()
    async with session_scope() as session:
        durable_run = await session.get(KnowledgeBaseStorageMigration, run.id)
    if not durable_run.source_identity or not durable_run.source_fingerprint:
        msg = "Migration source identity disappeared before activation"
        raise MigrationProtocolError(msg)
    await _worker(_write_source_binding, durable_run.source_identity, durable_run.source_fingerprint, row.id)
    async with session_scope() as session:
        result = await session.execute(
            update(KnowledgeBaseRecord)
            .where(
                KnowledgeBaseRecord.id == row.id,
                KnowledgeBaseRecord.active_migration_id == run.id,
                KnowledgeBaseRecord.backend_type == "sqlite",
                KnowledgeBaseRecord.storage_generation == run.target_generation,
                col(KnowledgeBaseRecord.storage_state).in_(("migrating", "needs_attention")),
            )
            .values(storage_state="ready")
        )
        if result.rowcount != 1:
            msg = "Knowledge base routing changed during activation"
            raise StorageUnavailableError(msg)
        current_run = await session.get(KnowledgeBaseStorageMigration, run.id)
        current_run.phase = "complete"
        current_run.error_code = None
        current_run.updated_at = datetime.now(timezone.utc)
        await session.commit()


def _qualify(path, header, directory):
    with path.open("rb") as stream:
        return qualify_export(stream, expected_header=header, scratch_directory=directory)


def _binding_path(relative: str, *, root: Path | None = None) -> Path:
    return (
        (root or storage_root()) / ".migration" / "bindings" / f"{hashlib.sha256(relative.encode()).hexdigest()}.json"
    )


def _write_source_binding(relative: str, fingerprint: str, kb_id: UUID) -> None:
    """Prevent a retained old source from being re-adopted after KB/user deletion."""
    path = _binding_path(relative)
    private_directory(path.parent)
    if path.is_symlink():
        msg = "Invalid source migration binding"
        raise MaintenanceRequiredError(msg)
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump({"source": relative, "fingerprint": fingerprint, "kb_id": str(kb_id)}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    _fsync_directory(path.parent)


def _is_retired_source(relative: str, *, root: Path | None = None) -> bool:
    source_root = root or storage_root()
    path = _binding_path(relative, root=source_root)
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BINDING_BYTES:
        msg = "Invalid source migration binding"
        raise MaintenanceRequiredError(msg)
    binding = json.loads(path.read_bytes())
    if not isinstance(binding, dict) or binding.get("source") != relative:
        msg = "Invalid source migration binding"
        raise MaintenanceRequiredError(msg)
    if binding.get("fingerprint") != tree_fingerprint(source_root / relative):
        msg = "Retired migration source changed. Administrator recovery is required before adoption."
        raise MaintenanceRequiredError(msg)
    return True


async def migrate_one(kb_id: UUID) -> None:
    """Idempotently migrate or recover one fenced KB, including a Memory backing KB."""
    async with operation(kb_id, allowed_states=("ready", "migrating", "needs_attention", "deleting", "deleted")):
        async with session_scope() as session:
            row = await session.get(KnowledgeBaseRecord, kb_id)
        if row is None or row.storage_state in ("deleting", "deleted"):
            return
        if row.backend_type == "sqlite" and row.storage_state == "ready":
            return
        if row.backend_type not in ("sqlite", "chroma"):
            return
        run = await _prepare(row)
        target = None
        try:
            # A crash after the routing transaction needs only target health and
            # the final ready transition. Never return to the old source.
            if row.backend_type == "sqlite":
                target = SQLiteBackend(
                    kb_name=row.name,
                    backend_config=row.backend_config,
                    storage_context=SQLiteStorageContext(storage_root(), row.user_id, row.id, row.storage_generation),
                )
                await _complete(row, run, target)
                return
            if row.backend_config.get("mode", "local") != "local":
                await _attention(row.id, run.id, "remote_source_requires_migration")
                return
            database = get_sqlite_database_file_path(get_db_service().database_url)
            receipt_name = os.environ.get("LANGFLOW_KB_UPGRADE_RECEIPT")
            if database is None or not receipt_name:
                msg = "A managed stopped-worker receipt and metadata backup are required"
                raise MaintenanceRequiredError(msg)
            receipt = await _worker(
                validate_receipt, root=storage_root(), database=database, receipt=Path(receipt_name)
            )
            async with session_scope() as session:
                owner = await session.get(User, row.user_id)
            if owner is None:
                msg = "Legacy store owner is missing"
                raise MaintenanceRequiredError(msg)
            if any(
                part in ("", ".", "..") or Path(part).name != part or "\\" in part
                for part in (owner.username, row.name)
            ):
                msg = "Legacy storage identity is ambiguous"
                raise MaintenanceRequiredError(msg)
            source = storage_root() / owner.username / row.name
            if source.parent.is_symlink() or (source / ".kb_deleted").exists():
                msg = "Legacy source is a symlink or a deletion tombstone"
                raise MaintenanceRequiredError(msg)
            fingerprint = receipt.get("sources", {}).get(source.relative_to(storage_root()).as_posix())
            if not isinstance(fingerprint, str):
                msg = "Source was not inventoried by the stopped-worker controller"
                raise MaintenanceRequiredError(msg)
            if run.source_fingerprint and run.source_fingerprint != fingerprint:
                msg = "Source fingerprint changed between migration attempts"
                raise MaintenanceRequiredError(msg)
            directory = private_directory(storage_root() / ".migration" / str(row.id) / str(run.id))
            snapshot = directory / "source"
            await _phase(
                run.id,
                "snapshotting",
                source_fingerprint=fingerprint,
                source_identity=source.relative_to(storage_root()).as_posix(),
            )
            await _worker(snapshot_source, source, snapshot, fingerprint)
            await _phase(run.id, "exporting")
            output = directory / "export.jsonl"
            # A crash can leave a complete interchange before its phase update.
            # The pristine source remains authoritative, so retry may safely
            # discard and re-export this disposable file into the same ledger.
            output.unlink(missing_ok=True)
            header = await helper.export_snapshot(
                snapshot,
                output,
                collection_name=row.name,
                source_id=str(row.id),
                source_fingerprint=fingerprint,
                model_fingerprint=_model_fingerprint(row),
            )
            await _phase(
                run.id, "importing", source_version=header.source_version, validation={"header": asdict(header)}
            )
            config = {"metric": header.metric, "model_fingerprint": header.model_fingerprint}
            target = SQLiteBackend(
                kb_name=row.name,
                backend_config=config,
                storage_context=SQLiteStorageContext(storage_root(), row.user_id, row.id, run.target_generation),
                create=True,
            )
            source_export = await _worker(_qualify, output, header, directory)
            with source_export:
                verified = await import_qualified_export(source_export, target, migration_id=run.id)
            await _phase(run.id, "verified", validation=json.loads(json.dumps(asdict(verified), default=str)))
            # Target completion is durable before this compare-and-swap. Backend
            # routing and ownership never depend on a path supplied by the helper.
            async with session_scope() as session:
                result = await session.execute(
                    update(KnowledgeBaseRecord)
                    .where(
                        KnowledgeBaseRecord.id == row.id,
                        KnowledgeBaseRecord.user_id == row.user_id,
                        KnowledgeBaseRecord.backend_type == "chroma",
                        KnowledgeBaseRecord.storage_generation == run.source_generation,
                        KnowledgeBaseRecord.active_migration_id == run.id,
                        KnowledgeBaseRecord.storage_state == "migrating",
                    )
                    .values(
                        backend_type="sqlite",
                        backend_config=config,
                        storage_generation=run.target_generation,
                        chunks=verified.count,
                    )
                )
                if result.rowcount != 1:
                    msg = "Knowledge base routing changed before activation"
                    raise StorageUnavailableError(msg)
                current_run = await session.get(KnowledgeBaseStorageMigration, run.id)
                current_run.phase = "activated"
                await session.commit()
            await _complete(row, run, target)
            # Retain pristine source and durable validation. The interchange is
            # disposable after success and may contain sensitive document text.
            output.unlink(missing_ok=True)
        except asyncio.CancelledError:
            await _attention(row.id, run.id, "interrupted")
            raise
        except Exception as exc:  # noqa: BLE001 -- persist a safe failure, never expose a partial target
            code = (
                "maintenance_required"
                if isinstance(exc, MaintenanceRequiredError)
                else "validation_failed"
                if isinstance(exc, MigrationProtocolError)
                else "storage_changed"
                if isinstance(exc, StorageUnavailableError)
                else "migration_failed"
            )
            await _attention(row.id, run.id, code)
            await logger.awarning("Knowledge base storage upgrade %s requires attention (%s)", row.id, code)
        finally:
            if target is not None:
                await target.teardown()


async def fence_legacy_records() -> None:
    """Also catch rows adopted after Alembic, before starting any background writer."""
    async with session_scope() as session:
        await session.execute(
            update(KnowledgeBaseRecord)
            .where(KnowledgeBaseRecord.backend_type == "chroma", KnowledgeBaseRecord.storage_state == "ready")
            .values(storage_state="migrating")
        )
        await session.commit()


async def reconcile_legacy_inventory() -> None:
    """Adopt only controller-inventoried, unambiguous local sidecar identities.

    Unknown owners or damaged metadata remain visible upgrade blockers. They
    cannot disappear just because there is no corresponding application row.
    """
    global _inventory_complete, _inventory_issue_count  # noqa: PLW0603 -- process-local readiness during inventory
    _inventory_complete = False
    receipt_name = os.environ.get("LANGFLOW_KB_UPGRADE_RECEIPT")
    if not receipt_name:
        # Missing rows are not evidence of a fresh install. Detect old source
        # directories so an unconfigured upgrade cannot silently ignore them.
        configured = get_settings_service().settings.knowledge_bases_dir
        if configured:

            def discover():
                root = storage_root()
                if not root.exists():
                    return 0
                count = 0
                for owner in root.iterdir():
                    if owner.name.startswith(".") or owner.name == "sqlite":
                        continue
                    if owner.is_symlink():
                        return 1
                    if owner.is_dir():
                        count += sum(
                            1
                            for source in owner.iterdir()
                            if source.is_dir()
                            and (source / "chroma.sqlite3").exists()
                            and not (source / ".kb_deleted").exists()
                            and not _is_retired_source(source.relative_to(root).as_posix())
                        )
                return count

            _inventory_issue_count = await _worker(discover)
        else:
            _inventory_issue_count = 0
        _inventory_complete = _inventory_issue_count == 0
        return
    _inventory_complete = False
    database = get_sqlite_database_file_path(get_db_service().database_url)
    if database is None:
        msg = "The local upgrade controller requires a SQLite metadata database"
        raise MaintenanceRequiredError(msg)
    receipt = await _worker(validate_receipt, root=storage_root(), database=database, receipt=Path(receipt_name))
    async with session_scope() as session:
        owners = {user.username: user for user in (await session.exec(select(User))).all()}
        rows = {(row.user_id, row.name): row for row in (await session.exec(select(KnowledgeBaseRecord))).all()}
    issues = []
    for relative in receipt.get("sources", {}):
        parts = Path(relative).parts
        if len(parts) != _SOURCE_PATH_PARTS or any(part in (".", "..") or "\\" in part for part in parts):
            issues.append({"code": "ambiguous_source_identity"})
            continue
        if await _worker(_is_retired_source, relative):
            continue
        owner = owners.get(parts[0])
        if owner is None:
            issues.append({"code": "missing_source_owner"})
            continue
        source = storage_root() / relative
        if (source / ".kb_deleted").exists() or (owner.id, parts[1]) in rows:
            continue
        try:
            if await _worker(tree_fingerprint, source) != receipt["sources"][relative]:
                raise ValueError
            path = source / "embedding_metadata.json"
            if path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError
            metadata = json.loads(await _worker(path.read_bytes))
            if not isinstance(metadata, dict) or metadata.get("backend_type", "chroma") != "chroma":
                raise ValueError
            if metadata.get("name", parts[1]) != parts[1]:
                raise ValueError
            selection = metadata.get("model_selection") or {
                "provider": metadata.get("embedding_provider", "Unknown"),
                "name": metadata.get("embedding_model", ""),
            }
            if isinstance(selection, list):
                selection = selection[0] if selection else {}
            if not isinstance(selection, dict):
                raise TypeError
            row = KnowledgeBaseRecord(
                id=UUID(str(metadata["id"])) if metadata.get("id") else uuid4(),
                user_id=owner.id,
                name=parts[1],
                model_selection=selection,
                chunk_size=int(metadata.get("chunk_size", 1000)),
                chunk_overlap=int(metadata.get("chunk_overlap", 200)),
                separator=metadata.get("separator"),
                column_config=metadata.get("column_config", []),
                backend_type="chroma",
                backend_config={},
                storage_state="migrating",
            )
            async with session_scope() as session:
                session.add(row)
                await session.commit()
        except Exception:  # noqa: BLE001 -- retain an explicit inventory blocker
            # A different new worker may have adopted this same source first.
            async with session_scope() as session:
                found = (
                    await session.exec(
                        select(KnowledgeBaseRecord.id).where(
                            KnowledgeBaseRecord.user_id == owner.id, KnowledgeBaseRecord.name == parts[1]
                        )
                    )
                ).first()
            if found is None:
                issues.append({"code": "unreadable_or_ambiguous_legacy_metadata", "owner_id": str(owner.id)})
    _inventory_issue_count = len(issues)
    directory = private_directory(storage_root() / ".migration")
    path = directory / "inventory.json"
    if path.is_symlink():
        msg = "Invalid upgrade inventory path"
        raise MaintenanceRequiredError(msg)
    path.write_text(json.dumps({"issues": issues}), encoding="utf-8")
    _inventory_complete = not issues


def inventory_status() -> dict:
    return {"complete": _inventory_complete, "issues": _inventory_issue_count}


async def run_pending() -> None:
    # This local-only discovery occurs after the controller barrier and before
    # selecting work, so legacy Memory/KB identities are included automatically.
    try:
        await reconcile_legacy_inventory()
    except Exception:  # noqa: BLE001 -- still persist actionable errors on registered KBs
        logger.warning("Legacy storage inventory requires controller recovery")
    async with session_scope() as session:
        rows = list(
            (
                await session.exec(
                    select(KnowledgeBaseRecord).where(
                        col(KnowledgeBaseRecord.storage_state).in_(("migrating", "needs_attention")),
                        col(KnowledgeBaseRecord.backend_type).in_(("chroma", "sqlite")),
                    )
                )
            ).all()
        )
    if not rows:
        return
    try:
        for row in rows:
            try:
                await migrate_one(row.id)
            except StorageUnavailableError:
                # Owner deletion may cascade a queued identity away while a
                # preceding KB migrates. Only a freshly confirmed disappearance
                # is safe to skip. Existing identities must retain visible
                # routing/lock failures rather than silently abandon the run.
                async with session_scope() as session:
                    if await session.get(KnowledgeBaseRecord, row.id) is not None:
                        raise
    finally:
        # Image cleanup is separate from data success and must not revert an
        # activated generation. The helper protects images used by other runs.
        if os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_IMAGE"):
            try:
                await helper.cleanup_helper_artifact()
            except Exception:  # noqa: BLE001
                logger.warning("Temporary knowledge base migration helper requires cleanup")


def schedule_upgrade() -> asyncio.Task:
    global _inventory_complete  # noqa: PLW0603 -- readiness must close before scheduling inventory
    for existing in _tasks:
        if not existing.done():
            return existing
    _inventory_complete = False
    task = asyncio.create_task(run_pending(), name="knowledge-base-storage-upgrade")
    _tasks.add(task)

    def finished(completed):
        _tasks.discard(completed)
        if not completed.cancelled() and completed.exception() is not None:
            logger.error("Knowledge base upgrade coordinator failed. Readiness remains blocked.")

    task.add_done_callback(finished)
    return task


async def stop_upgrade() -> None:
    for task in tuple(_tasks):
        task.cancel()
    if _tasks:
        await asyncio.gather(*tuple(_tasks), return_exceptions=True)


async def readiness() -> bool:
    if not _inventory_complete:
        return False
    async with session_scope() as session:
        row = (
            await session.exec(
                select(KnowledgeBaseRecord.id)
                .where(
                    (KnowledgeBaseRecord.backend_type == "chroma")
                    | col(KnowledgeBaseRecord.storage_state).in_(("migrating", "needs_attention"))
                )
                .limit(1)
            )
        ).first()
    return row is None
