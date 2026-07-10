from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from cryptography.fernet import InvalidToken
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.triton_server.model import (
    TritonServer,
    TritonServerCredentials,
    TritonServerRead,
)
from langflow.services.database.utils import normalize_string_or_none, parse_uuid

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


def _strip_or_raise(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    return stripped


def _encrypt_token(raw: str) -> str:
    stripped = raw.strip()
    if not stripped:
        msg = "auth_token must not be empty"
        raise ValueError(msg)
    try:
        return auth_utils.encrypt_api_key(stripped)
    except (ValueError, InvalidToken, TypeError, AttributeError) as e:
        msg = "Failed to encrypt auth_token -- check server encryption configuration"
        raise RuntimeError(msg) from e


def _decrypt_token(encrypted: str | None) -> str | None:
    if not encrypted:
        return None
    try:
        return auth_utils.decrypt_api_key(encrypted)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to decrypt triton auth_token: %s", exc)
        return None


def to_read(server: TritonServer) -> TritonServerRead:
    return TritonServerRead(
        id=server.id,
        user_id=server.user_id,
        name=server.name,
        base_url=server.base_url,
        notes=server.notes,
        has_auth_token=bool(server.auth_token),
        created_at=server.created_at,  # type: ignore[arg-type]
        updated_at=server.updated_at,  # type: ignore[arg-type]
    )


async def get_triton_server(
    db: AsyncSession,
    *,
    server_id: UUID | str,
    user_id: UUID | str,
) -> TritonServer | None:
    server_uuid = parse_uuid(server_id, field_name="server_id")
    user_uuid = parse_uuid(user_id, field_name="user_id")
    stmt = select(TritonServer).where(
        TritonServer.id == server_uuid,
        TritonServer.user_id == user_uuid,
    )
    return (await db.exec(stmt)).first()


async def list_triton_servers(
    db: AsyncSession,
    *,
    user_id: UUID | str,
    offset: int = 0,
    limit: int | None = None,
) -> list[TritonServer]:
    user_uuid = parse_uuid(user_id, field_name="user_id")
    stmt = (
        select(TritonServer)
        .where(TritonServer.user_id == user_uuid)
        .order_by(col(TritonServer.created_at).desc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await db.exec(stmt)).all())


async def create_triton_server(
    db: AsyncSession,
    *,
    user_id: UUID | str,
    name: str,
    base_url: str,
    auth_token: str | None,
    notes: str | None,
) -> TritonServer:
    user_uuid = parse_uuid(user_id, field_name="user_id")
    name_s = _strip_or_raise(name, "name")
    base_url_s = _strip_or_raise(base_url, "base_url")
    notes_n = normalize_string_or_none(notes)

    encrypted = _encrypt_token(auth_token) if auth_token is not None else None

    now = datetime.now(timezone.utc)
    server = TritonServer(
        user_id=user_uuid,
        name=name_s,
        base_url=base_url_s,
        auth_token=encrypted,
        notes=notes_n,
        created_at=now,
        updated_at=now,
    )
    db.add(server)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        await logger.aerror(
            "IntegrityError creating triton server (user_id=%s, name=%s)",
            user_uuid,
            name_s,
        )
        msg = f"Triton server already exists (name={name_s!r})"
        raise ValueError(msg) from exc
    await db.refresh(server)
    return server


async def update_triton_server(
    db: AsyncSession,
    *,
    server: TritonServer,
    name: str | None = None,
    base_url: str | None = None,
    auth_token: str | None = None,
    notes: str | None = None,
) -> TritonServer:
    if name is not None:
        server.name = _strip_or_raise(name, "name")
    if base_url is not None:
        server.base_url = _strip_or_raise(base_url, "base_url")
    if auth_token is not None:
        stripped = auth_token.strip()
        if not stripped:
            server.auth_token = None
        else:
            server.auth_token = _encrypt_token(stripped)
    if notes is not None:
        server.notes = normalize_string_or_none(notes)

    server.updated_at = datetime.now(timezone.utc)
    db.add(server)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        await logger.aerror("IntegrityError updating triton server id=%s", server.id)
        msg = "Triton server update conflicts with an existing record (name already in use)"
        raise ValueError(msg) from exc
    await db.refresh(server)
    return server


async def delete_triton_server(
    db: AsyncSession,
    *,
    server: TritonServer,
) -> None:
    await db.delete(server)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        await logger.aerror("Failed to delete triton server id=%s", server.id)
        msg = f"Failed to delete triton server id={server.id}"
        raise ValueError(msg) from exc


def get_credentials(server: TritonServer) -> TritonServerCredentials:
    return TritonServerCredentials(auth_token=_decrypt_token(server.auth_token))
