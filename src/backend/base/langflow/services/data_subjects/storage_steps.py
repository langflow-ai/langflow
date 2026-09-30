"""Phase 3 of an erase: bytes outside the database.

The plan is snapshotted into the request before any row is deleted (rows are the only index of
some paths), and each item is removed from it only after its bytes are gone, so a crash retries it.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.components.files_and_knowledge._filesystem_isolation import load_isolation_config
from lfx.components.files_and_knowledge._filesystem_namespace import compute_user_namespace
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_settings_service, get_storage_service

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext

KIND_NAMESPACE = "namespace"
KIND_KB_USER_DIR = "kb_user_dir"
KIND_FLOWS_DIR = "flows_dir"
KIND_FS_SANDBOX = "fs_sandbox"
KIND_SAVE_FILE_DIR = "save_file_dir"
KIND_SKIPPED = "skipped"
_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9_.-]")
_RESERVED_SEGMENTS = frozenset({"flows", "profile_pictures", "knowledge_bases", "fs_sandbox", "alembic", "logs"})


def _item(kind: str, value: str) -> dict[str, str]:
    return {"kind": kind, "value": value}


def _config_dir() -> Path:
    return Path(get_settings_service().settings.config_dir)


def _save_file_segment(raw_id: str) -> str | None:
    """The SaveToFile folder name, only when it maps back to this end user alone."""
    segment = _SAFE_SEGMENT.sub("_", raw_id).strip("._")
    if not segment or segment != raw_id or segment in _RESERVED_SEGMENTS:
        return None
    try:
        UUID(segment)
    except ValueError:
        return segment
    return None


async def builder_storage_plan(session: AsyncSession, ctx: EraseContext) -> list[dict[str, str]]:
    flow_ids = (await session.exec(select(Flow.id).where(Flow.user_id == ctx.subject_user_id))).all()
    plan = [_item(KIND_NAMESPACE, str(ctx.subject_user_id))]
    plan.extend(_item(KIND_NAMESPACE, str(flow_id)) for flow_id in flow_ids)
    plan.append(_item(KIND_FLOWS_DIR, str(ctx.subject_user_id)))
    plan.append(_item(KIND_FS_SANDBOX, str(ctx.subject_user_id)))
    if ctx.username:
        plan.append(_item(KIND_KB_USER_DIR, ctx.username))
    return plan


def end_user_storage_plan(ctx: EraseContext) -> list[dict[str, str]]:
    if ctx.end_user is None:
        return []
    plan = [_item(KIND_FS_SANDBOX, ctx.end_user.raw_id)]
    segment = _save_file_segment(ctx.end_user.raw_id)
    plan.append(_item(KIND_SAVE_FILE_DIR, segment) if segment else _item(KIND_SKIPPED, "save_file_dir_ambiguous"))
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


def _remove_kb_user_dir(username: str) -> None:
    from langflow.api.utils.kb_helpers import KBStorageHelper

    root = KBStorageHelper.get_root_path()
    _remove_dir(root / username, root)


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
        await asyncio.to_thread(_remove_dir, _config_dir() / value, _config_dir())
