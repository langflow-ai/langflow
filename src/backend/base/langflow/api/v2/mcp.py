import asyncio
import json
from collections import defaultdict
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile
from lfx.base.agents.utils import safe_cache_get, safe_cache_set
from lfx.base.mcp.util import update_tools

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v2.files import (
    MCP_SERVERS_FILE,
    download_file,
    edit_file_name,
    get_file_by_name,
    get_mcp_file,
    upload_user_file,
)
from langflow.api.v2.schemas import MCPServerConfig
from langflow.logging import logger
from langflow.services.deps import get_settings_service, get_shared_component_cache_service, get_storage_service
from langflow.services.settings.service import SettingsService
from langflow.services.storage.service import StorageService

router = APIRouter(tags=["MCP"], prefix="/mcp")

# Per-user locks to serialize update_server() calls and prevent lost updates
# from the non-atomic read-modify-write cycle on the MCP config file.
_update_server_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def is_mcp_servers_locked(settings: object) -> bool:
    """Return True only when MCP lock is explicitly enabled.

    Some tests patch settings with MagicMock objects where unknown attributes
    resolve to truthy placeholders. Using ``is True`` ensures lock enforcement
    only when the flag is explicitly set to ``True``.
    """
    return getattr(settings, "mcp_servers_locked", False) is True


def _enforce_immutable_server_name(server_name: str, server_config: dict) -> dict:
    """Enforce that the server name is owned by the URL path, not the request body.

    ``server_name`` is the immutable identifier for an MCP server: it is both the
    storage key and the POST/PATCH URL path segment. Because :class:`MCPServerConfig`
    permits extra fields (``extra="allow"``), a ``name`` in the request body would
    otherwise be silently persisted as stray config data and — on PATCH — echoed back
    in the 200 response, falsely implying that a rename succeeded.

    A body ``name`` that disagrees with the URL is rejected with 422 so the constraint
    is explicit. A redundant but matching ``name`` is dropped so it never pollutes the
    stored config.

    Args:
        server_name: The server name from the URL path (the canonical identifier).
        server_config: The request body dumped to a dict.

    Returns:
        A config dict with any ``name`` key removed.

    Raises:
        HTTPException: 422 when ``name`` is present and differs from ``server_name``.
    """
    if "name" not in server_config:
        return server_config

    body_name = server_config["name"]
    if body_name != server_name:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Server name is immutable and is determined by the URL path "
                f"('{server_name}'); it cannot be set or changed via the request body "
                f"(got '{body_name}'). To rename a server, delete it and create a new one."
            ),
        )
    # Matching name is redundant — drop it so it isn't persisted as stray config.
    return {key: value for key, value in server_config.items() if key != "name"}


async def upload_server_config(
    server_config: dict,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    content_str = json.dumps(server_config)
    content_bytes = content_str.encode("utf-8")  # Convert to bytes
    file_obj = BytesIO(content_bytes)  # Use BytesIO for binary data

    mcp_file = await get_mcp_file(current_user, extension=True)
    upload_file = UploadFile(file=file_obj, filename=mcp_file, size=len(content_str))

    return await upload_user_file(
        file=upload_file,
        session=session,
        current_user=current_user,
        storage_service=storage_service,
        settings_service=settings_service,
    )


async def get_server_list(
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    # Backwards compatibilty with old format file name
    mcp_file = await get_mcp_file(current_user)
    old_format_config_file = await get_file_by_name(MCP_SERVERS_FILE, current_user, session)
    if old_format_config_file:
        await edit_file_name(old_format_config_file.id, mcp_file, current_user, session)

    # Read the server configuration from a file using the files api
    server_config_file = await get_file_by_name(mcp_file, current_user, session)

    # Attempt to download the configuration file content
    try:
        server_config_bytes = await download_file(
            server_config_file.id if server_config_file else None,
            current_user,
            session,
            storage_service=storage_service,
            return_content=True,
        )
    except (FileNotFoundError, HTTPException):
        if server_config_file:
            # DB record exists but storage file is missing — likely a transient state
            # during a concurrent update_server() write cycle. Return empty config
            # WITHOUT persisting to avoid permanently wiping existing servers.
            logger.warning(
                "MCP config file missing from storage for user %s (transient). "
                "Returning empty config without persisting.",
                current_user.id,
            )
            return {"mcpServers": {}}

        # No DB record and no storage file — genuinely first-time use. Create empty config.
        await upload_server_config(
            {"mcpServers": {}},
            current_user,
            session,
            storage_service=storage_service,
            settings_service=settings_service,
        )

        # Fetch and download again
        mcp_file = await get_mcp_file(current_user)
        server_config_file = await get_file_by_name(mcp_file, current_user, session)
        if not server_config_file:
            raise HTTPException(status_code=500, detail="Failed to create MCP Servers configuration file") from None

        server_config_bytes = await download_file(
            server_config_file.id,
            current_user,
            session,
            storage_service=storage_service,
            return_content=True,
        )

    # Parse JSON content
    try:
        servers = json.loads(server_config_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid server configuration file format.") from None

    return servers


async def get_server(
    server_name: str,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
    server_list: dict | None = None,
):
    """Get a specific server configuration."""
    if server_list is None:
        server_list = await get_server_list(current_user, session, storage_service, settings_service)

    if server_name not in server_list["mcpServers"]:
        return None

    return server_list["mcpServers"][server_name]


# Define a Get servers endpoint
@router.get("/servers")
async def get_servers(
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
    *,
    action_count: bool | None = None,
):
    """Get the list of available servers."""
    import asyncio

    from lfx.base.mcp.util import MCPStdioClient, MCPStreamableHttpClient

    server_list = await get_server_list(current_user, session, storage_service, settings_service)

    if not action_count:
        # Return only the server names, with mode and toolsCount as None
        return [{"name": server_name, "mode": None, "toolsCount": None} for server_name in server_list["mcpServers"]]

    # Check all of the tool counts for each server concurrently
    async def check_server(server_name: str) -> dict:
        server_info: dict[str, str | int | None] = {"name": server_name, "mode": None, "toolsCount": None}
        # Create clients that we control so we can clean them up after
        mcp_stdio_client = MCPStdioClient()
        mcp_streamable_http_client = MCPStreamableHttpClient()
        try:
            # Get global variables from database for header resolution
            request_variables = {}
            try:
                from sqlmodel import select

                from langflow.services.auth import utils as auth_utils
                from langflow.services.database.models.variable.model import Variable

                # Load variables directly from database and decrypt ALL types (including CREDENTIAL)
                stmt = select(Variable).where(Variable.user_id == current_user.id)
                variables = list((await session.exec(stmt)).all())

                # Decrypt variables based on type (following the pattern from get_all_decrypted_variables)
                for variable in variables:
                    if variable.name and variable.value:
                        # Prior to v1.8, both Generic and Credential variables were encrypted.
                        # As such, must attempt to decrypt both types to ensure backwards-compatibility.
                        try:
                            decrypted_value = auth_utils.decrypt_api_key(variable.value)
                            request_variables[variable.name] = decrypted_value
                        except Exception as e:  # noqa: BLE001
                            await logger.aerror(
                                f"Failed to decrypt credential variable '{variable.name}': {e}. "
                                "This credential will not be available for MCP server."
                            )
            except Exception as e:  # noqa: BLE001
                await logger.awarning(f"Failed to load global variables for MCP server test: {e}")

            mode, tool_list, _ = await update_tools(
                server_name=server_name,
                server_config=server_list["mcpServers"][server_name],
                mcp_stdio_client=mcp_stdio_client,
                mcp_streamable_http_client=mcp_streamable_http_client,
                request_variables=request_variables,
            )
            server_info["mode"] = mode.lower()
            server_info["toolsCount"] = len(tool_list)
            if len(tool_list) == 0:
                server_info["error"] = "No tools found"
        except ValueError as e:
            # Configuration validation errors, invalid URLs, etc.
            await logger.aerror(f"Configuration error for server {server_name}: {e}")
            server_info["error"] = f"Configuration error: {e}"
        except ConnectionError as e:
            # Network connection and timeout issues
            await logger.aerror(f"Connection error for server {server_name}: {e}")
            server_info["error"] = f"Connection failed: {e}"
        except (TimeoutError, asyncio.TimeoutError) as e:
            # Timeout errors
            await logger.aerror(f"Timeout error for server {server_name}: {e}")
            server_info["error"] = "Timeout when checking server tools"
        except OSError as e:
            # System-level errors (process execution, file access)
            await logger.aerror(f"System error for server {server_name}: {e}")
            server_info["error"] = f"System error: {e}"
        except (KeyError, TypeError) as e:
            # Data parsing and access errors
            await logger.aerror(f"Data error for server {server_name}: {e}")
            server_info["error"] = f"Configuration data error: {e}"
        except (RuntimeError, ProcessLookupError, PermissionError) as e:
            # Runtime and process-related errors
            await logger.aerror(f"Runtime error for server {server_name}: {e}")
            server_info["error"] = f"Runtime error: {e}"
        except Exception as e:  # noqa: BLE001
            # Generic catch-all for other exceptions (including ExceptionGroup)
            if hasattr(e, "exceptions") and e.exceptions:
                # Extract the first underlying exception for a more meaningful error message
                underlying_error = e.exceptions[0]
                if hasattr(underlying_error, "exceptions"):
                    await logger.aerror(
                        f"Error checking server {server_name}: {underlying_error}, {underlying_error.exceptions}"
                    )
                    underlying_error = underlying_error.exceptions[0]
                else:
                    await logger.aexception(f"Error checking server {server_name}: {underlying_error}")
                server_info["error"] = f"Error loading server: {underlying_error}"
            else:
                await logger.aexception(f"Error checking server {server_name}: {e}")
                server_info["error"] = f"Error loading server: {e}"
        finally:
            # Always disconnect clients to prevent mcp-proxy process leaks
            # These clients spawn subprocesses that need to be explicitly terminated
            await mcp_stdio_client.disconnect()
            await mcp_streamable_http_client.disconnect()
        return server_info

    # Run all server checks concurrently
    tasks = [check_server(server) for server in server_list["mcpServers"]]
    return await asyncio.gather(*tasks, return_exceptions=True)


@router.get("/servers/{server_name}")
async def get_server_endpoint(
    server_name: str,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    """Get a specific server."""
    return await get_server(server_name, current_user, session, storage_service, settings_service)


async def update_server(
    server_name: str,
    server_config: dict,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
    *,
    check_existing: bool = False,
    delete: bool = False,
    merge_existing: bool = False,
):
    async with _update_server_locks[str(current_user.id)]:
        server_list = await get_server_list(current_user, session, storage_service, settings_service)

        # Validate server name
        if check_existing and server_name in server_list["mcpServers"]:
            raise HTTPException(status_code=500, detail="Server already exists.")

        # Handle the delete case
        if delete:
            if server_name in server_list["mcpServers"]:
                del server_list["mcpServers"][server_name]
            else:
                raise HTTPException(status_code=500, detail="Server not found.")
        elif merge_existing:
            existing_config = server_list["mcpServers"].get(server_name, {})
            server_list["mcpServers"][server_name] = {**existing_config, **server_config}
        else:
            server_list["mcpServers"][server_name] = server_config

        # Upload the updated server configuration
        # (upload_user_file handles replacing the existing MCP file atomically)
        await upload_server_config(
            server_list, current_user, session, storage_service=storage_service, settings_service=settings_service
        )

        shared_component_cache_service = get_shared_component_cache_service()
        # Clear the servers cache
        servers = safe_cache_get(shared_component_cache_service, "servers", {})
        if isinstance(servers, dict):
            if server_name in servers:
                del servers[server_name]
            safe_cache_set(shared_component_cache_service, "servers", servers)

        return await get_server(
            server_name,
            current_user,
            session,
            storage_service,
            settings_service,
            server_list=server_list,
        )


@router.post("/servers/{server_name}")
async def add_server(
    server_name: str,
    *,
    server_config: Annotated[MCPServerConfig, Body()],
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    if is_mcp_servers_locked(settings_service.settings) and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is locked. Contact an administrator to manage external MCP servers.",
        )

    return await update_server(
        server_name,
        _enforce_immutable_server_name(server_name, server_config.model_dump(exclude_unset=True)),
        current_user,
        session,
        storage_service,
        settings_service,
        check_existing=True,
    )


@router.patch("/servers/{server_name}")
async def update_server_endpoint(
    server_name: str,
    *,
    server_config: Annotated[MCPServerConfig, Body()],
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    if is_mcp_servers_locked(settings_service.settings) and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is locked. Contact an administrator to manage external MCP servers.",
        )

    return await update_server(
        server_name,
        _enforce_immutable_server_name(server_name, server_config.model_dump(exclude_unset=True)),
        current_user,
        session,
        storage_service,
        settings_service,
        merge_existing=True,
    )


@router.delete("/servers/{server_name}")
async def delete_server(
    server_name: str,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    if is_mcp_servers_locked(settings_service.settings) and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is locked. Contact an administrator to manage external MCP servers.",
        )

    return await update_server(
        server_name,
        {},
        current_user,
        session,
        storage_service,
        settings_service,
        delete=True,
    )
