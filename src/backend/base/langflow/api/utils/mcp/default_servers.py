"""Orchestrator that auto-installs the default MCP servers (registry-driven) for every user."""

import platform
from typing import Literal

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service
from sqlalchemy import exc as sqlalchemy_exc
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils.mcp.default_servers_specs import (
    DEFAULT_MCP_SERVERS,
    DefaultMcpServerConfig,
    DefaultMcpServerSpec,
)
from langflow.api.v2.mcp import get_server_list, update_server
from langflow.api.v2.schemas import MCPServerConfig
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_service
from langflow.services.schema import ServiceType

OsKind = Literal["unix", "windows"]


def _detect_os_kind() -> OsKind:
    """Collapse platform.system() into the two buckets we ship configs for.

    Why: WSL reports Linux and *BSD reports its own name; mcp-shell-server runs
    POSIX-style via uvx in all of those. Only Windows needs the `cmd /c` wrapper.
    """
    return "windows" if platform.system() == "Windows" else "unix"


def _select_os_config(spec: DefaultMcpServerSpec, os_kind: OsKind) -> DefaultMcpServerConfig:
    return spec.windows if os_kind == "windows" else spec.unix


def _build_server_payload(
    spec: DefaultMcpServerSpec,
    os_kind: OsKind,
) -> dict:
    """Build the persisted payload, re-validating via MCPServerConfig.

    Why re-validate something we authored: defense in depth. If a future commit
    drops a forbidden command, env var, or arg into the registry, this fails
    fast at startup instead of silently installing a backdoor.
    """
    cfg = _select_os_config(spec, os_kind)
    payload = {
        "command": cfg.command,
        "args": list(cfg.args),
        "env": dict(cfg.env),
        "metadata": {
            "description": spec.description,
            "auto_configured": True,
            "langflow_internal": True,
            "platform": os_kind,
        },
    }
    MCPServerConfig.model_validate(payload)
    return payload


async def auto_configure_default_mcp_servers(session: AsyncSession) -> None:
    """Install the curated default MCP servers for every existing user.

    Idempotent: if a user already has a server with the same name (whether we created
    it or they did), the entry is preserved. Errors per-user are logged and the loop
    continues — one bad user must never break others.
    """
    settings_service = get_settings_service()
    if not settings_service.settings.enable_default_mcp_servers:
        await logger.adebug("default_mcp_servers_disabled")
        return

    users = (await session.exec(select(User))).all()
    if not users:
        return

    storage_service = get_service(ServiceType.STORAGE_SERVICE)
    os_kind = _detect_os_kind()

    for server_name, spec in DEFAULT_MCP_SERVERS.items():
        payload = _build_server_payload(spec, os_kind)
        for user in users:
            try:
                existing = await get_server_list(user, session, storage_service, settings_service)
                if server_name in existing.get("mcpServers", {}):
                    await logger.adebug(
                        "default_mcp_server_skipped",
                        user_id=str(user.id),
                        server_name=server_name,
                        reason="already_exists",
                    )
                    continue
                await update_server(
                    server_name=server_name,
                    server_config=payload,
                    current_user=user,
                    session=session,
                    storage_service=storage_service,
                    settings_service=settings_service,
                )
                await logger.ainfo(
                    "default_mcp_server_added",
                    user_id=str(user.id),
                    server_name=server_name,
                    os_kind=os_kind,
                )
            except (
                HTTPException,
                sqlalchemy_exc.SQLAlchemyError,
                OSError,
                PermissionError,
                FileNotFoundError,
                RuntimeError,
                ValueError,
                AttributeError,
            ):
                await logger.aexception(
                    "default_mcp_server_failed",
                    user_id=str(user.id),
                    server_name=server_name,
                )
                continue
