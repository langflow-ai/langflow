"""Phase 3 of an erase: bytes outside the database.

The plan is snapshotted into the request before any row is deleted (rows are the only index of
some paths), and each item is removed from it only after its bytes are gone, so a crash retries it.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.components.files_and_knowledge._filesystem_isolation import load_isolation_config
from lfx.components.files_and_knowledge._filesystem_namespace import compute_user_namespace
from lfx.log.logger import logger
from lfx.utils.end_user_storage import (
    end_user_folder_lock,
    end_user_folder_owners,
    end_user_folder_segment,
    forget_end_user_folder,
)
from sqlmodel import select

from langflow.services.data_subjects.knowledge_base_steps import builder_directories, builder_upgrade_runs
from langflow.services.data_subjects.memory_base_storage import KIND_MEMORY_BASE, drop_memory_base
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.deps import get_settings_service, get_storage_service
from langflow.services.knowledge_base_storage.legacy_directories import (
    LegacyDirectories,
    is_legacy_directory,
    is_owner_folder,
    scan_legacy_directories,
)
from langflow.services.knowledge_base_storage.retained import remove_copy, remove_upgrade_evidence, retained_source
from langflow.services.knowledge_base_storage.runtime import storage_root

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext

KIND_NAMESPACE = "namespace"
KIND_KB_USER_DIR = "kb_user_dir"
KIND_KB_UPGRADE_EVIDENCE = "kb_upgrade_evidence"
KIND_KB_RETAINED_SOURCE = "kb_retained_source"
KIND_KB_SOURCE_BINDING = "kb_source_binding"
KIND_FLOWS_DIR = "flows_dir"
KIND_FS_SANDBOX = "fs_sandbox"
KIND_SAVE_FILE_DIR = "save_file_dir"
KIND_SKIPPED = "skipped"
SKIPPED_SHARED_ACROSS_FLOWS = "end_user_storage_shared_across_flows"
_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9_.-]")
_RESERVED_SEGMENTS = frozenset({"flows", "profile_pictures", "knowledge_bases", "fs_sandbox", "alembic", "logs"})


def _item(kind: str, value: str, **extra: str) -> dict[str, str]:
    return {"kind": kind, "value": value, **extra}


def _config_dir() -> Path:
    return Path(get_settings_service().settings.config_dir)


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _save_file_segment(raw_id: str) -> str | None:
    """The legacy sanitized folder name, unless it is a name other storage uses.

    Ownership is checked against the SaveToFile registry when the item runs.
    """
    segment = _SAFE_SEGMENT.sub("_", raw_id).strip("._")
    if not segment or segment in _RESERVED_SEGMENTS or _is_uuid(segment):
        return None
    return segment


async def builder_storage_plan(session: AsyncSession, ctx: EraseContext) -> list[dict[str, str]]:
    flow_ids = (await session.exec(select(Flow.id).where(Flow.user_id == ctx.subject_user_id))).all()
    plan = [_item(KIND_NAMESPACE, str(ctx.subject_user_id))]
    plan.extend(_item(KIND_NAMESPACE, str(flow_id)) for flow_id in flow_ids)
    plan.append(_item(KIND_FLOWS_DIR, str(ctx.subject_user_id)))
    plan.append(_item(KIND_FS_SANDBOX, str(ctx.subject_user_id)))
    if ctx.username:
        plan.extend(await _knowledge_base_plan(session, ctx))
    return plan


async def _knowledge_base_plan(session: AsyncSession, ctx: EraseContext) -> list[dict[str, str]]:
    """The builder's legacy directories and what the automatic storage upgrade kept of their bases.

    Each `<owner>/<name>` directory that belongs to the builder is removed whole, as a retained source is,
    and then the folder named after the builder once nothing else is in it, since a rename can leave
    another account's directories there. The snapshots and routing backups hold every chunk, and the
    bindings name the builder. The bindings run last, after the directories they guard, since the plan
    runs in order and stops at a failure.
    """
    username = str(ctx.username)
    owned = (
        await session.exec(
            select(KnowledgeBaseRecord.id, KnowledgeBaseRecord.name, KnowledgeBaseRecord.backend_type).where(
                KnowledgeBaseRecord.user_id == ctx.subject_user_id
            )
        )
    ).all()
    runs = (
        await session.exec(
            select(KnowledgeBaseStorageMigration.kb_id, KnowledgeBaseStorageMigration.source_identity).where(
                builder_upgrade_runs(ctx.subject_user_id, username)
            )
        )
    ).all()
    kb_ids = {kb_id for kb_id, _ in runs} | {kb_id for kb_id, _, _ in owned}
    # Only a Chroma base still reads `<username>/<name>`. An upgraded base's directory is its ledger row's.
    named = {identity for _, identity in runs if identity}
    named |= {f"{username}/{name}" for _, name, backend in owned if backend == "chroma"}
    found = await _scan_legacy_directories()
    sources = await builder_directories(session, ctx.subject_user_id, username, named=named, kb_ids=kb_ids, found=found)
    removed = sources & found.stores
    folder = [_item(KIND_KB_USER_DIR, username)] if is_owner_folder(username) else []
    if folder and (kept := {source for source in found.stores if source.startswith(f"{username}/")} - removed):
        await logger.awarning(
            "op=data_subject_erase kept %d directories in the builder's knowledge base folder that are not theirs",
            len(kept),
        )
    return [
        *(_item(KIND_KB_RETAINED_SOURCE, source) for source in sorted(removed)),
        *folder,
        *(_item(KIND_KB_UPGRADE_EVIDENCE, str(kb_id)) for kb_id in sorted(kb_ids, key=str)),
        *(_item(KIND_KB_SOURCE_BINDING, source) for source in sorted(sources)),
    ]


async def _scan_legacy_directories() -> LegacyDirectories:
    if not _local_storage_configured():
        return LegacyDirectories()
    try:
        return await asyncio.to_thread(scan_legacy_directories, storage_root())
    except OSError:
        # Nothing is removed then, and a binding waits until its directory is known to be gone.
        await logger.awarning("op=data_subject_erase could not list the knowledge base storage root")
        return LegacyDirectories()


def end_user_storage_plan(ctx: EraseContext) -> list[dict[str, str]]:
    """Files the end user keeps outside the database.

    The FileSystem sandbox and the SaveToFile folder belong to the person, not to a flow, so a request
    scoped to some flows keeps them: they may hold files written by flows outside the scope.
    """
    if ctx.end_user is None:
        return []
    if ctx.scope_flow_ids:
        return [_item(KIND_SKIPPED, SKIPPED_SHARED_ACROSS_FLOWS)]
    plan = [_item(KIND_FS_SANDBOX, ctx.end_user.raw_id)]
    # Older identities can exceed the new encoding limit and still own a legacy folder.
    with contextlib.suppress(ValueError):
        encoded = end_user_folder_segment(ctx.end_user.raw_id)
        plan.append(_item(KIND_SAVE_FILE_DIR, encoded, end_user_id=ctx.end_user.raw_id))
    segment = _save_file_segment(ctx.end_user.raw_id)
    if segment:
        plan.append(_item(KIND_SAVE_FILE_DIR, segment, end_user_id=ctx.end_user.raw_id))
    return plan


def _remove_dir(path: Path, root: Path) -> None:
    resolved = path.resolve()
    if resolved == root.resolve() or not resolved.is_relative_to(root.resolve()):
        msg = "Refusing to delete a path outside its storage root"
        raise ValueError(msg)
    if resolved.is_dir():
        shutil.rmtree(resolved)


def _remove_fs_sandbox(identity: str) -> None:
    # Same default as the FileSystem tool itself, or the erase would look in the wrong place.
    from lfx.components.files_and_knowledge.filesystem import _default_config_dir

    config = load_isolation_config(env=os.environ, default_config_dir=_default_config_dir())
    if not config.pepper_path.exists():
        return
    namespace = compute_user_namespace(identity, pepper=config.pepper_path.read_bytes())
    if namespace == Path():
        return
    _remove_dir(config.base_dir / namespace, config.base_dir)


def _remove_save_file_dir(segment: str, end_user_id: str) -> None:
    """Delete the folder only when SaveToFile recorded this end user as its sole owner."""
    root = _config_dir()
    with end_user_folder_lock(root, segment):
        owners = end_user_folder_owners(root, segment)
        if owners != frozenset({end_user_id}):
            logger.warning(
                "op=data_subject_erase kept save-file folder %s: %s",
                segment,
                "not written by SaveToFile" if owners is None else "shared with other end users",
            )
            return
        _remove_dir(root / segment, root)
        forget_end_user_folder(root, segment)


def _local_storage_configured() -> bool:
    return bool(get_settings_service().settings.knowledge_bases_dir)


def _remove_kb_user_dir(username: str) -> None:
    """Delete the folder named after the builder once nothing is left in it."""
    if _local_storage_configured() and is_owner_folder(username):
        with contextlib.suppress(OSError):
            (storage_root() / username).rmdir()


def _remove_retained_source(source_identity: str) -> None:
    """Delete one `<owner>/<name>` directory, then its owner's folder once nothing else is in it."""
    if not _local_storage_configured():
        return
    if not is_legacy_directory(source_identity):
        # A plan never names internal storage, so a stored item that does is kept rather than trusted.
        logger.warning("op=data_subject_erase kept a planned directory that is internal knowledge base storage")
        return
    root = storage_root()
    directory = retained_source(root, source_identity)
    remove_copy(directory, root)
    with contextlib.suppress(OSError):
        directory.parent.rmdir()


def _remove_upgrade_evidence(kb_id: str) -> None:
    if _local_storage_configured():
        remove_upgrade_evidence(storage_root(), UUID(kb_id))


def _present(path: Path) -> bool:
    try:
        path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    return True


def _forget_source_binding(source_identity: str) -> None:
    # The coordinator pulls in the whole upgrade machinery, so load it only when a binding is due.
    from langflow.services.knowledge_base_storage.coordinator import forget_source_binding

    # A binding keeps its directory from being adopted again, so it stays as long as the directory does.
    if _local_storage_configured() and not _present(retained_source(storage_root(), source_identity)):
        forget_source_binding(source_identity)


async def run_storage_item(item: dict[str, Any]) -> None:
    kind, value = item["kind"], str(item["value"])
    if kind == KIND_NAMESPACE:
        await get_storage_service().delete_namespace(value)
    elif kind == KIND_FLOWS_DIR:
        root = _config_dir() / "flows"
        await asyncio.to_thread(_remove_dir, root / value, root)
    elif kind == KIND_FS_SANDBOX:
        await asyncio.to_thread(_remove_fs_sandbox, value)
    elif kind == KIND_KB_USER_DIR:
        await asyncio.to_thread(_remove_kb_user_dir, value)
    elif kind == KIND_SAVE_FILE_DIR:
        await asyncio.to_thread(_remove_save_file_dir, value, str(item.get("end_user_id", "")))
    elif kind == KIND_MEMORY_BASE:
        await drop_memory_base(item)
    elif kind == KIND_KB_UPGRADE_EVIDENCE:
        await asyncio.to_thread(_remove_upgrade_evidence, value)
    elif kind == KIND_KB_RETAINED_SOURCE:
        await asyncio.to_thread(_remove_retained_source, value)
    elif kind == KIND_KB_SOURCE_BINDING:
        await asyncio.to_thread(_forget_source_binding, value)
