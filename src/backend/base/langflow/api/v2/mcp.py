import contextlib
import json
from io import BytesIO
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from lfx.base.agents.utils import safe_cache_get, safe_cache_set
from lfx.base.mcp.util import update_tools

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v2.files import (
    MCP_SERVERS_FILE,
    delete_file,
    download_file,
    edit_file_name,
    get_file_by_name,
    get_mcp_file,
    upload_user_file,
)
from langflow.logging import logger
from langflow.services.database.models import Folder
from langflow.services.database.models.api_key.crud import create_api_key
from langflow.services.database.models.api_key.model import ApiKeyCreate
from langflow.services.deps import get_settings_service, get_shared_component_cache_service, get_storage_service
from langflow.services.settings.service import SettingsService
from langflow.services.storage.service import StorageService

router = APIRouter(tags=["MCP"], prefix="/mcp")


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
        # Storage file missing - DB entry may be stale. Remove it and recreate.
        if server_config_file:
            with contextlib.suppress(Exception):
                await delete_file(server_config_file.id, current_user, session, storage_service)

        # Create a fresh empty config
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

    servers_updated = False
    created_api_key = False
    mcp_servers = servers.get("mcpServers", {})

    for server_name, server_config in list(mcp_servers.items()):
        updated_config, config_changed, created_key = await _ensure_mcp_server_config(
            server_name=server_name,
            server_config=server_config,
            current_user=current_user,
            session=session,
            settings_service=settings_service,
        )
        if config_changed:
            servers_updated = True
            created_api_key = created_api_key or created_key
            mcp_servers[server_name] = updated_config

    if servers_updated:
        servers["mcpServers"] = mcp_servers
        if created_api_key:
            await session.commit()
        await upload_server_config(
            servers,
            current_user,
            session,
            storage_service=storage_service,
            settings_service=settings_service,
        )

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

    server_list = await get_server_list(current_user, session, storage_service, settings_service)

    if not action_count:
        # Return only the server names, with mode and toolsCount as None
        return [{"name": server_name, "mode": None, "toolsCount": None} for server_name in server_list["mcpServers"]]

    # Check all of the tool counts for each server concurrently
    async def check_server(server_name: str) -> dict:
        server_info: dict[str, str | int | None] = {"name": server_name, "mode": None, "toolsCount": None}
        try:
            mode, tool_list, _ = await update_tools(
                server_name=server_name,
                server_config=server_list["mcpServers"][server_name],
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
):
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
    else:
        server_list["mcpServers"][server_name] = server_config

    # Remove the existing file
    mcp_file = await get_mcp_file(current_user)
    server_config_file = await get_file_by_name(mcp_file, current_user, session)

    # Now we are ready to delete it and reprocess
    if server_config_file:
        await delete_file(server_config_file.id, current_user, session, storage_service)

    # Upload the updated server configuration
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


def _extract_project_id_from_url(url: str) -> UUID | None:
    """Return project UUID from a Langflow MCP URL if present."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    for idx, part in enumerate(path_parts):
        if part == "project" and idx + 1 < len(path_parts):
            candidate = path_parts[idx + 1]
            try:
                return UUID(candidate)
            except (ValueError, TypeError):
                return None
    return None


async def _ensure_mcp_server_config(
    *,
    server_name: str,
    server_config: dict,
    current_user: CurrentActiveUser,
    session: DbSession,
    settings_service: SettingsService,
) -> tuple[dict, bool, bool]:
    """Normalize stored MCP server configs and ensure auth headers when required."""
    args = server_config.get("args")
    if not isinstance(args, list) or not args:
        return server_config, False, False

    command = server_config.get("command")
    if command != "uvx":
        return server_config, False, False

    if "mcp-proxy" not in args:
        return server_config, False, False

    url_arg = next((arg for arg in reversed(args) if isinstance(arg, str) and arg.startswith("http")), None)
    if not url_arg:
        return server_config, False, False

    project_id = _extract_project_id_from_url(url_arg)
    if project_id is None:
        return server_config, False, False

    project: Folder | None = await session.get(Folder, project_id)
    if project is None:
        return server_config, False, False

    generated_api_key = False
    should_generate_api_key = False

    if settings_service.settings.mcp_composer_enabled:
        if project.auth_settings and project.auth_settings.get("auth_type") == "apikey":
            should_generate_api_key = True
    elif project.auth_settings:
        if project.auth_settings.get("auth_type") == "apikey":
            should_generate_api_key = True
    elif not settings_service.auth_settings.AUTO_LOGIN:
        should_generate_api_key = True

    if settings_service.auth_settings.AUTO_LOGIN and not settings_service.auth_settings.SUPERUSER:
        should_generate_api_key = True

    existing_header_tokens: list[str] | None = None
    preserved_args: list[str] = []
    uses_streamable = False

    start_index = 1 if args[0] == "mcp-proxy" else 0
    if start_index == 0:
        preserved_args.append(args[0])

    idx = start_index
    while idx < len(args):
        arg_item = args[idx]
        if arg_item == "--transport":
            uses_streamable = True
            idx += 2
            continue
        if arg_item == "--headers":
            existing_header_tokens = args[idx : idx + 3]
            idx += 3
            continue
        if isinstance(arg_item, str) and arg_item.startswith("http"):
            idx += 1
            continue
        preserved_args.append(arg_item)
        idx += 1

    if isinstance(url_arg, str) and not url_arg.endswith("/sse"):
        uses_streamable = True

    if not uses_streamable:
        if existing_header_tokens is None and should_generate_api_key:
            api_key_name = f"MCP Server {project.name}"
            new_api_key = await create_api_key(session, ApiKeyCreate(name=api_key_name), current_user.id)
            header_tokens = ["--headers", "x-api-key", new_api_key.api_key]
            generated_api_key = True

            url_index = len(args) - 1
            for idx_arg in range(len(args) - 1, -1, -1):
                if args[idx_arg] == url_arg:
                    url_index = idx_arg
                    break

            final_args = list(args)
            final_args[url_index:url_index] = header_tokens
            server_config["args"] = final_args
            await logger.adebug(
                "Added authentication headers for MCP server '%s' (project %s) while preserving SSE transport.",
                server_name,
                project_id,
            )
            return server_config, True, generated_api_key

        return server_config, False, generated_api_key

    streamable_http_url = url_arg.removesuffix("/sse")
    if not streamable_http_url.endswith("/streamable"):
        streamable_http_url = streamable_http_url.rstrip("/") + "/streamable"
    final_args: list[str] = ["mcp-proxy", "--transport", "streamablehttp"]

    if preserved_args:
        final_args.extend(preserved_args)

    header_tokens = existing_header_tokens
    if header_tokens is None and should_generate_api_key:
        api_key_name = f"MCP Server {project.name}"
        new_api_key = await create_api_key(session, ApiKeyCreate(name=api_key_name), current_user.id)
        header_tokens = ["--headers", "x-api-key", new_api_key.api_key]
        generated_api_key = True

    if header_tokens:
        final_args.extend(header_tokens)

    final_args.append(streamable_http_url)

    config_updated = final_args != args

    if config_updated:
        server_config["args"] = final_args
        await logger.adebug(
            "Normalized MCP server '%s' configuration for project %s (streamable HTTP + auth header).",
            server_name,
            project_id,
        )

    return server_config, config_updated, generated_api_key


@router.post("/servers/{server_name}")
async def add_server(
    server_name: str,
    server_config: dict,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    return await update_server(
        server_name,
        server_config,
        current_user,
        session,
        storage_service,
        settings_service,
        check_existing=True,
    )


@router.patch("/servers/{server_name}")
async def update_server_endpoint(
    server_name: str,
    server_config: dict,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    return await update_server(
        server_name,
        server_config,
        current_user,
        session,
        storage_service,
        settings_service,
    )


@router.delete("/servers/{server_name}")
async def delete_server(
    server_name: str,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
):
    return await update_server(
        server_name,
        {},
        current_user,
        session,
        storage_service,
        settings_service,
        delete=True,
    )
