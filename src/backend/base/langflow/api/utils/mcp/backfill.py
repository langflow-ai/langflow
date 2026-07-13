"""Backfill MCP servers from the legacy per-user JSON file into the mcp_server table.

Runs best-effort on startup and via ``langflow migrate-mcp``. Properties:

- **Idempotent** — only inserts a server that isn't already a row for that user, so
  it is safe to run on every boot and to re-run by hand.
- **Multi-replica safe** — the ``(user_id, name)`` unique constraint is the backstop;
  a concurrent insert from another replica raises ``IntegrityError`` which is caught.
- **Backend-agnostic** — reads through the storage service, so it covers local disk
  and S3/Ceph/MinIO identically.
- **Non-destructive** — the legacy file is never deleted, so rolling back to a
  file-based Langflow remains safe.
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.api.v2.mcp import _read_legacy_mcp_file
from langflow.logging import logger
from langflow.services.auth.mcp_encryption import encrypt_mcp_config
from langflow.services.database.models import MCPServer
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, get_storage_service


async def backfill_mcp_servers_from_files(session, *, dry_run: bool = False) -> dict[str, int]:
    """Import each user's legacy ``_mcp_servers_<id>.json`` entries into ``mcp_server``.

    Args:
        session: An async DB session.
        dry_run: If True, count what would be imported without writing.

    Returns:
        Summary counts: ``{"users", "imported", "skipped", "errors"}``.
    """
    storage_service = get_storage_service()
    settings_service = get_settings_service()
    summary = {"users": 0, "imported": 0, "skipped": 0, "errors": 0}

    users = (await session.exec(select(User))).all()
    for user in users:
        summary["users"] += 1
        try:
            legacy = await _read_legacy_mcp_file(
                user, session, storage_service, settings_service, create_if_missing=False
            )
        except Exception as e:  # noqa: BLE001
            summary["errors"] += 1
            await logger.awarning(f"MCP backfill: could not read legacy MCP file for user {user.id}: {e}")
            continue

        pending = 0
        for name, config in (legacy.get("mcpServers") or {}).items():
            already = (
                await session.exec(select(MCPServer).where(MCPServer.user_id == user.id, MCPServer.name == name))
            ).first()
            if already is not None:
                summary["skipped"] += 1
                continue
            summary["imported"] += 1
            if dry_run:
                continue
            session.add(MCPServer(user_id=user.id, name=name, config=encrypt_mcp_config(config or {})))
            pending += 1

        if pending:
            try:
                await session.commit()
            except IntegrityError:
                # Another replica imported this user's servers first; safe to skip.
                await session.rollback()

    await logger.ainfo(
        "MCP backfill complete: users=%s imported=%s skipped=%s errors=%s",
        summary["users"],
        summary["imported"],
        summary["skipped"],
        summary["errors"],
    )
    return summary
