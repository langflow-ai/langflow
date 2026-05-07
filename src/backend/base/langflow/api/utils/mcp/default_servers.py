"""Orchestrator that auto-installs the default MCP servers (registry-driven) for every user."""

import platform

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

# Metadata fields the spec authors. We compare these (and only these) when
# deciding whether a persisted auto-configured entry has drifted from the
# canonical spec — extra metadata keys (added by future API extensions or
# user tooling) must not trigger spurious reconciliations.
_SPEC_OWNED_METADATA_KEYS: tuple[str, ...] = (
    "description",
    "auto_configured",
    "langflow_internal",
    "startup_timeout_seconds",
)


def _is_persisted_payload_in_sync(persisted: dict, canonical: dict) -> bool:
    """Return True iff the persisted MCP entry already matches the canonical spec.

    Compares only the fields the spec controls (command, args, env, and the
    spec-owned metadata keys). Extra fields on either side are ignored so we
    don't thrash on derived / user-added properties.
    """
    if persisted.get("command") != canonical["command"]:
        return False
    if list(persisted.get("args") or []) != list(canonical["args"]):
        return False
    if dict(persisted.get("env") or {}) != dict(canonical["env"]):
        return False
    persisted_meta = persisted.get("metadata") or {}
    canonical_meta = canonical["metadata"]
    return all(persisted_meta.get(key) == canonical_meta.get(key) for key in _SPEC_OWNED_METADATA_KEYS)


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
                existing_servers = (await get_server_list(user, session, storage_service, settings_service)).get(
                    "mcpServers", {}
                )
                persisted = existing_servers.get(server_name)
                is_reconcile = False
                if persisted is not None:
                    persisted_meta = persisted.get("metadata") or {}
                    if not persisted_meta.get("auto_configured"):
                        # User-owned entry (no `auto_configured` flag): never overwrite.
                        await logger.adebug(
                            "default_mcp_server_skipped",
                            user_id=str(user.id),
                            server_name=server_name,
                            reason="user_owned",
                        )
                        continue
                    if _is_persisted_payload_in_sync(persisted, payload):
                        await logger.adebug(
                            "default_mcp_server_skipped",
                            user_id=str(user.id),
                            server_name=server_name,
                            reason="already_in_sync",
                        )
                        continue
                    # Spec drifted (e.g. user upgraded across a commit that changed
                    # the canonical payload). `auto_configured: True` was our marker
                    # that the entry is ours, so overwriting is safe.
                    is_reconcile = True
                await update_server(
                    server_name=server_name,
                    server_config=payload,
                    current_user=user,
                    session=session,
                    storage_service=storage_service,
                    settings_service=settings_service,
                )
                # Distinct event names so Sentry/Datadog filtering can separate
                # fresh installs from upgrade-driven reconciliations. Platform is
                # included on reconcile because the bug that motivated this path
                # (first-run `npx -y` timeouts on Windows) is OS-correlated.
                if is_reconcile:
                    await logger.ainfo(
                        "default_mcp_server_reconciled",
                        user_id=str(user.id),
                        server_name=server_name,
                        platform=platform.system(),
                    )
                else:
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
