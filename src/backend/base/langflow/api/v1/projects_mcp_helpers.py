"""MCP server registration and management helpers for projects.

Extracted from projects.py to reduce file size and isolate MCP concerns (SO1).
"""

from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.services.mcp_composer.service import MCPComposerService

from langflow.api.utils.mcp.config_utils import validate_mcp_server_for_project
from langflow.api.v1.mcp_projects import get_project_streamable_http_url
from langflow.api.v2.mcp import update_server
from langflow.services.database.models.api_key.crud import create_api_key
from langflow.services.database.models.api_key.model import ApiKeyCreate
from langflow.services.deps import get_service, get_settings_service, get_storage_service
from langflow.services.schema import ServiceType


def _server_config_uses_streamable_http(args: list[Any], streamable_http_url: str) -> bool:
    """Return whether the server args target this project's Streamable HTTP endpoint."""
    string_args = [arg for arg in args if isinstance(arg, str)]
    return (
        "mcp-proxy" in string_args
        and "--transport" in string_args
        and "streamablehttp" in string_args
        and streamable_http_url in string_args
    )


def _server_config_has_project_api_key(args: list[Any]) -> bool:
    """Return whether the server args include the generated Langflow API key header."""
    return any(
        arg == "--headers" and index + 2 < len(args) and args[index + 1] == "x-api-key"
        for index, arg in enumerate(args)
    )


def _server_config_matches_project_auth(
    existing_config: dict[str, Any] | None,
    auth_type: str,
    streamable_http_url: str,
) -> bool:
    """Check whether the stored MCP server config already matches the project's auth mode."""
    if not existing_config:
        return False

    args = existing_config.get("args")
    if not isinstance(args, list) or not _server_config_uses_streamable_http(args, streamable_http_url):
        return False

    has_project_api_key = _server_config_has_project_api_key(args)
    if auth_type == "apikey":
        return has_project_api_key
    if auth_type == "none":
        return not has_project_api_key
    return False


async def register_mcp_servers_for_project(
    project,
    default_auth: dict,
    current_user,
    session,
    *,
    raise_on_error: bool = False,
) -> bool:
    """Register MCP servers for a newly created project.

    This handles the full MCP auto-registration flow: building the transport URL,
    creating API keys if needed, validating conflicts, and calling update_server.

    Returns:
        True when the server config was created or updated, otherwise False.

    Raises:
        HTTPException: On server name conflicts.
    """
    try:
        streamable_http_url = await get_project_streamable_http_url(project.id)
        auth_type = default_auth.get("auth_type", "none")

        validation_result = await validate_mcp_server_for_project(
            project.id,
            project.name,
            current_user,
            session,
            get_storage_service(),
            get_settings_service(),
            operation="create",
        )

        if validation_result.has_conflict:
            await logger.aerror(validation_result.conflict_message)
            raise HTTPException(
                status_code=409,
                detail=validation_result.conflict_message,
            )

        if validation_result.should_skip and _server_config_matches_project_auth(
            validation_result.existing_config,
            auth_type,
            streamable_http_url,
        ):
            await logger.adebug(
                "MCP server '%s' already matches auth %s for project %s, skipping",
                validation_result.server_name,
                auth_type,
                project.id,
            )
            return False

        if auth_type == "apikey":
            api_key_name = f"MCP Project {project.name} - default"
            unmasked_api_key = await create_api_key(session, ApiKeyCreate(name=api_key_name), current_user.id)
            command = "uvx"
            args = [
                "mcp-proxy",
                "--transport",
                "streamablehttp",
                "--headers",
                "x-api-key",
                unmasked_api_key.api_key,
                streamable_http_url,
            ]
        elif auth_type == "oauth":
            msg = "OAuth authentication is not yet implemented for MCP server creation during project creation."
            await logger.awarning(msg)
            return False
        else:
            command = "uvx"
            args = [
                "mcp-proxy",
                "--transport",
                "streamablehttp",
                streamable_http_url,
            ]

        server_config = {"command": command, "args": args}

        if validation_result.should_skip:
            await logger.adebug(
                "MCP server '%s' exists for project %s but does not match auth %s, updating",
                validation_result.server_name,
                project.id,
                auth_type,
            )

        server_name = validation_result.server_name

        await update_server(
            server_name,
            server_config,
            current_user,
            session,
            get_storage_service(),
            get_settings_service(),
        )
    except HTTPException:
        raise
    except Exception as e:
        await logger.aexception("Failed to auto-register MCP server for project %s: %s", project.id, e)
        if raise_on_error:
            raise
        return False
    else:
        return True


async def reconcile_mcp_server_for_auth_update(
    project,
    new_auth_type: str | None,
    current_user,
    session,
) -> bool:
    """Sync the MCP server config for a project whose auth settings just changed.

    OAuth reconciliation is driven separately by MCP Composer, so this helper only
    touches apikey/none modes. Returns True when the server config was updated.
    """
    if new_auth_type not in {"apikey", "none"}:
        return False

    if not get_settings_service().settings.add_projects_to_mcp_servers:
        return False

    return await register_mcp_servers_for_project(
        project,
        {"auth_type": new_auth_type},
        current_user,
        session,
    )


async def handle_mcp_server_rename(
    existing_project,
    old_project_name: str,
    new_project_name: str,
    current_user,
    session,
) -> None:
    """Handle MCP server name update when a project is renamed.

    Validates old and new server names, checks for conflicts, and performs
    the rename (delete old + create new) if needed.

    Raises HTTPException on name conflicts.
    """
    try:
        old_validation = await validate_mcp_server_for_project(
            existing_project.id,
            old_project_name,
            current_user,
            session,
            get_storage_service(),
            get_settings_service(),
            operation="update",
        )

        new_validation = await validate_mcp_server_for_project(
            existing_project.id,
            new_project_name,
            current_user,
            session,
            get_storage_service(),
            get_settings_service(),
            operation="update",
        )

        if old_validation.server_name != new_validation.server_name:
            if new_validation.has_conflict:
                await logger.aerror(new_validation.conflict_message)
                raise HTTPException(
                    status_code=409,
                    detail=new_validation.conflict_message,
                )

            if old_validation.server_exists and old_validation.project_id_matches:
                await update_server(
                    old_validation.server_name,
                    {},
                    current_user,
                    session,
                    get_storage_service(),
                    get_settings_service(),
                    delete=True,
                )

                await update_server(
                    new_validation.server_name,
                    old_validation.existing_config or {},
                    current_user,
                    session,
                    get_storage_service(),
                    get_settings_service(),
                )

                await logger.adebug(
                    "Updated MCP server name from %s to %s",
                    old_validation.server_name,
                    new_validation.server_name,
                )
            else:
                await logger.adebug(
                    "Old MCP server '%s' not found for this project, skipping rename",
                    old_validation.server_name,
                )

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        await logger.awarning("Failed to handle MCP server name update for project rename: %s", e)


async def cleanup_mcp_on_delete(
    project,
    project_id: UUID,
    current_user,
    session,
) -> None:
    """Clean up MCP resources when a project is deleted.

    Stops the MCP Composer if the project uses OAuth, and removes the
    corresponding MCP server entry if auto-add was enabled.
    """
    # Stop MCP Composer if project used OAuth
    if project.auth_settings and project.auth_settings.get("auth_type") == "oauth":
        try:
            mcp_composer_service: MCPComposerService = cast(
                MCPComposerService, get_service(ServiceType.MCP_COMPOSER_SERVICE)
            )
            await mcp_composer_service.stop_project_composer(str(project_id))
            await logger.adebug("Stopped MCP Composer for deleted OAuth project %s (%s)", project.name, project_id)
        except Exception as e:  # noqa: BLE001
            await logger.aerror("Failed to stop MCP Composer for deleted project %s: %s", project_id, e)

    # Delete corresponding MCP server if auto-add was enabled
    if get_settings_service().settings.add_projects_to_mcp_servers:
        try:
            validation_result = await validate_mcp_server_for_project(
                project_id,
                project.name,
                current_user,
                session,
                get_storage_service(),
                get_settings_service(),
                operation="delete",
            )

            if validation_result.server_exists and validation_result.project_id_matches:
                await update_server(
                    validation_result.server_name,
                    {},
                    current_user,
                    session,
                    get_storage_service(),
                    get_settings_service(),
                    delete=True,
                )
                await logger.adebug(
                    "Deleted MCP server %s for deleted project %s (%s)",
                    validation_result.server_name,
                    project.name,
                    project_id,
                )
            elif validation_result.server_exists and not validation_result.project_id_matches:
                await logger.adebug(
                    "MCP server '%s' exists but belongs to different project, skipping deletion",
                    validation_result.server_name,
                )
            else:
                await logger.adebug("No MCP server found for deleted project %s (%s)", project.name, project_id)

        except Exception as e:  # noqa: BLE001
            await logger.awarning("Failed to handle MCP server cleanup for deleted project %s: %s", project_id, e)
