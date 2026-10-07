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
from lfx.base.knowledge_bases.migration import ExportHeader, import_qualified_export, qualify_export, write_export
from lfx.base.knowledge_bases.migration.legacy_reader import export_local_snapshot
from lfx.base.knowledge_bases.migration.protocol import AutomaticMigrationLimitError, MigrationProtocolError
from lfx.log.logger import logger
from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.user.model import User
from langflow.services.database.service import get_sqlite_database_file_path
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from langflow.services.knowledge_base_storage import helper
from langflow.services.knowledge_base_storage.automatic import (
    AutomaticUpgradeUnavailableError,
    check_local_upgrade,
    preserve_routing,
)
from langflow.services.knowledge_base_storage.maintenance import (
    MaintenanceRequiredError,
    _fsync_directory,
    snapshot_source,
    tree_fingerprint,
    tree_stat_fingerprint,
    validate_receipt,
)
from langflow.services.knowledge_base_storage.runtime import (
    StorageUnavailableError,
    operation,
    private_directory,
    storage_root,
)
from langflow.services.memory_base.embedding_helpers import infer_embedding_provider

_tasks: set[asyncio.Task] = set()
_inventory_complete = True
_inventory_scanned = False
_inventory_issue_count = 0
_retry_requested = False
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
        except Exception:
            if not cancelled:
                raise
    if cancelled:
        task.exception()
        raise asyncio.CancelledError
    return task.result()


def _model_fingerprint(record: KnowledgeBaseRecord) -> str:
    """Hash the persisted embedding selection for migration compatibility checks."""
    selection = record.model_selection
    if isinstance(selection, list):
        selection = selection[0] if selection else {}
    # Non-secret identity only. Never copy embedding-provider credentials.
    identity = {key: selection.get(key) for key in ("provider", "name")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def _phase(migration_id: UUID, phase: str, **changes) -> None:
    """Persist migration progress and its updated timestamp in the ledger."""
    async with session_scope() as session:
        run = await session.get(KnowledgeBaseStorageMigration, migration_id)
        run.phase = phase
        run.updated_at = datetime.now(timezone.utc)
        for key, value in changes.items():
            setattr(run, key, value)
        await session.commit()


async def _prepare(record: KnowledgeBaseRecord) -> KnowledgeBaseStorageMigration:
    """Create or resume a migration identity and fence its current routing generation."""
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
        run.phase = "discovered"
        run.error_code = None
        run.coordinator = f"{socket.gethostname()}:{os.getpid()}"
        run.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(run)
        return run


async def _attention(kb_id: UUID, migration_id: UUID, code: str, *, exception_type: str | None = None) -> str:
    """Retain the source and record a safe error code for operator recovery."""
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, kb_id)
        run = await session.get(KnowledgeBaseStorageMigration, migration_id)
        if row is not None and row.active_migration_id == migration_id:
            row.storage_state = "needs_attention"
        phase = run.phase if run else "discovered"
        if run is not None:
            if exception_type:
                run.validation = {
                    **run.validation,
                    "diagnostic": {"phase": phase, "exception_type": exception_type[:100]},
                }
            run.phase = "needs_attention"
            run.error_code = code
            run.updated_at = datetime.now(timezone.utc)
        await session.commit()
    return phase


async def _complete(row: KnowledgeBaseRecord, run: KnowledgeBaseStorageMigration, target: SQLiteBackend) -> None:
    """Verify the activated target and publish readiness only if its routing still matches."""
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
    from langflow.services.memory_base.ingestion import apply_pending_session_purges

    await apply_pending_session_purges(row, target)
    chunks = await target.count()
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
            .values(storage_state="ready", chunks=chunks)
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
    """Validate a helper export into a private replayable staging ledger."""
    with path.open("rb") as stream:
        return qualify_export(stream, expected_header=header, scratch_directory=directory)


def _binding_path(relative: str, *, root: Path | None = None) -> Path:
    """Derive the retained source binding path from its relative identity."""
    return (
        (root or storage_root()) / ".migration" / "bindings" / f"{hashlib.sha256(relative.encode()).hexdigest()}.json"
    )


def _write_source_binding(relative: str, fingerprint: str | None, kb_id: UUID, *, retired: bool = False) -> None:
    """Prevent a retained old source from being re-adopted after KB/user deletion."""
    path = _binding_path(relative)
    private_directory(path.parent)
    if path.is_symlink():
        msg = "Invalid source migration binding"
        raise MaintenanceRequiredError(msg)
    temporary = path.with_suffix(f".{uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(
            {
                "source": relative,
                "fingerprint": fingerprint,
                "stat_fingerprint": None if retired else tree_stat_fingerprint(storage_root() / relative),
                "kb_id": str(kb_id),
                "retired": retired,
            },
            stream,
        )
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    _fsync_directory(path.parent)


def _is_retired_source(relative: str, *, root: Path | None = None) -> bool:
    """Check whether a retained legacy source was already adopted by an upgrade."""
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
    if binding.get("retired") is True:
        # Explicit retirement is permanent. Changed or unreadable retained
        # sources must never be silently adopted under a reused name.
        return True
    if binding.get("stat_fingerprint") == tree_stat_fingerprint(source_root / relative):
        return True
    if binding.get("fingerprint") != tree_fingerprint(source_root / relative):
        msg = "Retired migration source changed. Administrator recovery is required before adoption."
        raise MaintenanceRequiredError(msg)
    if root is None:
        _write_source_binding(relative, binding["fingerprint"], UUID(binding["kb_id"]))
    return True


async def retire_legacy_source(record: KnowledgeBaseRecord) -> None:
    """Bind retained local sources and preserve their ledger before detachment/deletion.

    No removed provider is instantiated. Cloud and remote sources remain with
    their provider. The caller holds the immutable KB's exclusive operation.
    """
    async with session_scope() as session:
        owner = await session.get(User, record.user_id)
        run = (
            await session.get(KnowledgeBaseStorageMigration, record.active_migration_id)
            if record.active_migration_id
            else None
        )
    if owner is not None and get_settings_service().settings.knowledge_bases_dir:
        relative = f"{owner.username}/{record.name}"
        if len(Path(relative).parts) != _SOURCE_PATH_PARTS or "\\" in relative:
            msg = "Invalid retained source identity"
            raise MaintenanceRequiredError(msg)
        source = storage_root() / relative
        if source.is_dir() and (source / "chroma.sqlite3").exists():
            await _worker(_write_source_binding, relative, None, record.id, retired=True)
    if run is not None:
        await _phase(run.id, "detached", error_code=None)


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
            receipt = None
            if receipt_name:
                if database is None:
                    msg = "The managed receipt requires a SQLite application database"
                    raise MaintenanceRequiredError(msg)
                receipt = await _worker(
                    validate_receipt, root=storage_root(), database=database, receipt=Path(receipt_name)
                )
            else:
                await _worker(check_local_upgrade, storage_root(), get_settings_service().settings)
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
            fingerprint = (
                receipt.get("sources", {}).get(source.relative_to(storage_root()).as_posix())
                if receipt
                else await _worker(tree_fingerprint, source)
            )
            if not isinstance(fingerprint, str):
                msg = "Source was not inventoried by the stopped-worker controller"
                raise MaintenanceRequiredError(msg)
            if run.source_fingerprint and run.source_fingerprint != fingerprint:
                msg = "Source fingerprint changed between migration attempts"
                raise MaintenanceRequiredError(msg)
            directory = private_directory(storage_root() / ".migration" / str(row.id) / str(run.id))
            await _phase(run.id, "snapshotting")
            if receipt is None:
                await _worker(
                    preserve_routing,
                    directory,
                    row,
                    database,
                    backup_directory=private_directory(storage_root() / ".migration" / "application-backups"),
                )
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
            arguments = {
                "collection_name": row.name,
                "source_id": str(row.id),
                "source_fingerprint": fingerprint,
                "model_fingerprint": _model_fingerprint(row),
            }
            if (
                receipt is None
                and row.chunks == 0
                and not (snapshot / "chroma.sqlite3").exists()
                and not any(path.name != "embedding_metadata.json" for path in snapshot.iterdir())
            ):
                # Historical empty rows can have only an empty directory or
                # embedding sidecar. Any other file requires source recovery.
                header = ExportHeader(str(row.id), fingerprint, "chroma-empty", 0, None, "l2", _model_fingerprint(row))
                with output.open("wb") as stream:
                    write_export(stream, header, [])
            elif receipt is not None:
                header = await helper.export_snapshot(snapshot, output, **arguments)
            else:
                header = await _worker(export_local_snapshot, snapshot, output, **arguments)
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
            if receipt is None:
                await _worker(check_local_upgrade, storage_root(), get_settings_service().settings)
            if await _worker(tree_fingerprint, source) != fingerprint:
                msg = "The legacy source changed before activation"
                raise MaintenanceRequiredError(msg)
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
                exc.code
                if isinstance(exc, AutomaticUpgradeUnavailableError)
                else "automatic_reader_limit"
                if isinstance(exc, AutomaticMigrationLimitError)
                else "maintenance_required"
                if isinstance(exc, MaintenanceRequiredError)
                else "validation_failed"
                if isinstance(exc, MigrationProtocolError)
                else "storage_changed"
                if isinstance(exc, StorageUnavailableError)
                else "migration_failed"
            )
            phase = await _attention(row.id, run.id, code, exception_type=type(exc).__name__)
            await logger.awarning(
                "Knowledge base storage upgrade %s requires attention: code=%s phase=%s exception=%s",
                row.id,
                code,
                phase,
                type(exc).__name__,
            )
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


async def ensure_legacy_name_available(user_id: UUID, name: str) -> None:
    """Reserve an unadopted source name even while background discovery is running."""
    if not get_settings_service().settings.knowledge_bases_dir:
        return
    async with session_scope() as session:
        owner = await session.get(User, user_id)
    if owner is None:
        return

    def reserved():
        """Check whether a live legacy directory reserves this owner and display name."""
        root = storage_root()
        owner_path = root / owner.username
        source = owner_path / name
        if owner_path.is_symlink() or source.is_symlink() or not source.resolve().is_relative_to(root):
            return True
        if not (source / "chroma.sqlite3").exists() or (source / ".kb_deleted").exists():
            return False
        return not _is_retired_source(source.relative_to(root).as_posix())

    try:
        unavailable = await _worker(reserved)
    except (OSError, MaintenanceRequiredError, ValueError) as exc:
        msg = "This name is held by data from a previous version. Choose another name or contact your administrator."
        raise StorageUnavailableError(msg) from exc
    if unavailable:
        msg = (
            f"Knowledge base '{name}' is held by data from a previous version. "
            "Choose another name or contact your administrator."
        )
        raise StorageUnavailableError(msg)


async def reconcile_legacy_inventory() -> None:
    """Adopt unambiguous local sidecar identities from a bounded source inventory.

    Unknown owners or damaged metadata remain visible upgrade blockers. They
    cannot disappear just because there is no corresponding application row.
    """
    global _inventory_complete, _inventory_issue_count  # noqa: PLW0603 -- process-local readiness during inventory
    _inventory_complete = False
    receipt_name = os.environ.get("LANGFLOW_KB_UPGRADE_RECEIPT")
    if receipt_name:
        database = get_sqlite_database_file_path(get_db_service().database_url)
        if database is None:
            msg = "The local upgrade controller requires a SQLite metadata database"
            raise MaintenanceRequiredError(msg)
        receipt = await _worker(validate_receipt, root=storage_root(), database=database, receipt=Path(receipt_name))
    else:
        if not get_settings_service().settings.knowledge_bases_dir:
            _inventory_issue_count = 0
            _inventory_complete = True
            return

        def discover():
            """Inventory legacy sources without following owner or storage symlinks."""
            root = storage_root()
            sources = {}
            if not root.exists():
                return {"sources": sources}
            for owner in root.iterdir():
                if owner.is_symlink():
                    msg = "Legacy owner directory is a symbolic link"
                    raise MaintenanceRequiredError(msg)
                if not owner.is_dir():
                    continue
                for source in owner.iterdir():
                    if (
                        not source.is_dir()
                        or not (source / "chroma.sqlite3").exists()
                        or (source / ".kb_deleted").exists()
                    ):
                        continue
                    relative = source.relative_to(root).as_posix()
                    if not _is_retired_source(relative):
                        sources[relative] = tree_fingerprint(source)
            return {"sources": sources}

        receipt = await _worker(discover)
    async with session_scope() as session:
        owners = {user.username: user for user in (await session.exec(select(User))).all()}
        rows = {(row.user_id, row.name): row for row in (await session.exec(select(KnowledgeBaseRecord))).all()}
        runs = {run.id: run for run in (await session.exec(select(KnowledgeBaseStorageMigration))).all()}
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
        if (source / ".kb_deleted").exists():
            continue
        if (owner.id, parts[1]) in rows:
            row = rows[owner.id, parts[1]]
            run = runs.get(row.active_migration_id)
            recovering_activation = bool(
                row.backend_type == "sqlite"
                and run
                and run.source_backend == "chroma"
                and run.source_identity == relative
                and run.source_fingerprint == receipt["sources"][relative]
                and run.target_generation == row.storage_generation
                and row.storage_state in ("migrating", "needs_attention")
            )
            if row.backend_type != "chroma" and not recovering_activation:
                issues.append({"code": "ambiguous_source_identity", "owner_id": str(owner.id)})
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
            selection = metadata.get("model_selection") or {}
            if isinstance(selection, list):
                selection = selection[0] if selection else {}
            if not isinstance(selection, dict):
                raise TypeError
            if not selection:
                model = str(metadata.get("embedding_model") or "")
                provider = str(metadata.get("embedding_provider") or "Unknown")
                if provider == "Unknown" and model:
                    # Match the legacy sidecar backfill so a migrated base can
                    # still construct its query embedder after the vector copy.
                    provider = await _worker(infer_embedding_provider, model)
                selection = {"provider": provider, "name": model}
            config = metadata.get("backend_config") or {}
            if not isinstance(config, dict):
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
                backend_config=config,
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
                        select(KnowledgeBaseRecord).where(
                            KnowledgeBaseRecord.user_id == owner.id, KnowledgeBaseRecord.name == parts[1]
                        )
                    )
                ).first()
            if found is None or found.backend_type != "chroma":
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
    """Report discovery completion and the number of unresolved source identities."""
    return {"complete": _inventory_complete, "issues": _inventory_issue_count}


def upgrade_in_progress() -> bool:
    """Report background work without making it an application readiness gate."""
    return any(not task.done() for task in _tasks)


def _publish_inventory_status() -> None:
    """Share the latest completed scan across workers on this storage root."""
    directory = private_directory(storage_root() / ".migration")
    path = directory / "inventory-status.json"
    if path.is_symlink():
        msg = "Invalid shared inventory status path"
        raise MaintenanceRequiredError(msg)
    temporary = directory / f"inventory-status-{uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(inventory_status(), stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    _fsync_directory(directory)


async def published_inventory_status() -> dict:
    """Read a shared completed scan, with a startup fallback before its first publication."""
    configured = get_settings_service().settings.knowledge_bases_dir
    if not configured:
        return inventory_status()
    path = storage_root() / ".migration" / "inventory-status.json"
    if not path.exists():
        return inventory_status()
    try:
        value = json.loads(await _worker(helper._verification_file, path, limit=4096))  # noqa: SLF001 -- reuse bounded no-follow reads
        if (
            type(value) is not dict
            or set(value) != {"complete", "issues"}
            or type(value["complete"]) is not bool
            or type(value["issues"]) is not int
            or value["issues"] < 0
        ):
            raise ValueError
    except (ValueError, helper.MigrationHelperError):
        return {"complete": False, "issues": 1}
    else:
        return value


async def run_pending() -> None:
    """Reconcile legacy inventory and resume eligible storage migrations."""
    global _inventory_scanned, _inventory_issue_count  # noqa: PLW0603 -- process-local discovery status
    try:
        await reconcile_legacy_inventory()
    except Exception:  # noqa: BLE001 -- still persist actionable errors on registered KBs
        _inventory_issue_count = max(1, _inventory_issue_count)
        await logger.awarning("Legacy storage inventory requires administrator recovery")
    finally:
        if get_settings_service().settings.knowledge_bases_dir:
            try:
                await _worker(_publish_inventory_status)
            except Exception:  # noqa: BLE001 -- unavailable storage must not disable remote operations
                await logger.awarning("Legacy storage inventory status could not be published")
        _inventory_scanned = True
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


def schedule_upgrade(*, retry: bool = False) -> asyncio.Task:
    """Schedule one background discovery and upgrade task per running coordinator."""
    global _inventory_complete  # noqa: PLW0603 -- readiness must close before scheduling inventory
    global _inventory_scanned  # noqa: PLW0603 -- close initial discovery, keep admin retries available
    global _retry_requested  # noqa: PLW0603 -- coalesce retries requested during an existing run
    for existing in _tasks:
        if not existing.done():
            if retry:
                _retry_requested = True
            return existing
    _inventory_complete = False
    if not retry:
        _inventory_scanned = False
    _retry_requested = False

    async def run_requested():
        """Replay accepted retries after the current batch, including earlier failures."""
        global _retry_requested  # noqa: PLW0603 -- same event-loop coordinator flag
        while True:
            await run_pending()
            if not _retry_requested:
                return
            _retry_requested = False

    task = asyncio.create_task(run_requested(), name="knowledge-base-storage-upgrade")
    _tasks.add(task)

    def finished(completed):
        """Remove a finished task and report unexpected coordinator failures."""
        _tasks.discard(completed)
        if not completed.cancelled() and completed.exception() is not None:
            logger.error("Knowledge base upgrade coordinator failed. Unfinished bases remain unavailable.")

    task.add_done_callback(finished)
    return task


async def stop_upgrade() -> None:
    """Cancel and drain coordinator tasks before application shutdown."""
    for task in tuple(_tasks):
        task.cancel()
    if _tasks:
        await asyncio.gather(*tuple(_tasks), return_exceptions=True)


async def wait_for_upgrade(*, timeout: float = 30) -> None:
    """Wait for this worker's scheduled discovery without exposing task internals."""
    if _tasks:
        await asyncio.wait_for(asyncio.shield(asyncio.gather(*tuple(_tasks))), timeout=timeout)


async def readiness(*, require_storage_ready: bool = True) -> bool:
    """Keep ordinary readiness usable while strict upgrade probes check retained stores."""
    if not require_storage_ready:
        # Discovery and copying are background work. Ordinary health probes
        # must not restart the process while either is still progressing.
        return True
    if not _inventory_complete:
        return False
    async with session_scope() as session:
        row = (
            await session.exec(
                select(KnowledgeBaseRecord.id)
                .where(
                    ((KnowledgeBaseRecord.backend_type == "chroma") & (KnowledgeBaseRecord.storage_state != "detached"))
                    | col(KnowledgeBaseRecord.storage_state).in_(("migrating", "needs_attention"))
                )
                .limit(1)
            )
        ).first()
    return row is None
