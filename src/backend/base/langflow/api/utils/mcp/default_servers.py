"""Orchestrator that auto-installs the default MCP servers (registry-driven) for every user."""

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service
from sqlalchemy import exc as sqlalchemy_exc
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils.mcp.default_servers_specs import (
    DEFAULT_MCP_SERVERS,
    DefaultMcpServerSpec,
)
from langflow.api.v2.mcp import get_server_list, update_server
from langflow.api.v2.schemas import MCPServerConfig
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_service
from langflow.services.schema import ServiceType


def _build_server_payload(spec: DefaultMcpServerSpec) -> dict:
    """Build the persisted payload, re-validating via MCPServerConfig.

    Why re-validate something we authored: defense in depth. If a future commit
    drops a forbidden command, env var, or arg into the registry, this fails
    fast at startup instead of silently installing a backdoor.

    When ``spec.startup_timeout_seconds`` is set, it surfaces as
    ``metadata.startup_timeout_seconds`` for ``update_tools`` to pick up and
    override the global ``mcp_server_timeout`` for this server only.
    """
    cfg = spec.config
    metadata: dict = {
        "description": spec.description,
        "auto_configured": True,
        "langflow_internal": True,
    }
    if spec.startup_timeout_seconds is not None:
        metadata["startup_timeout_seconds"] = spec.startup_timeout_seconds

    payload = {
        "command": cfg.command,
        "args": list(cfg.args),
        "env": dict(cfg.env),
        "metadata": metadata,
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

    for server_name, spec in DEFAULT_MCP_SERVERS.items():
        payload = _build_server_payload(spec)
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
