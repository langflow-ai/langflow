"""MCP server registration and management helpers for projects.

Extracted from projects.py to reduce file size and isolate MCP concerns (SO1).
"""

from typing import cast
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


async def register_mcp_servers_for_project(
    project,
    default_auth: dict,
    current_user,
    session,
) -> None:
    """Register MCP servers for a newly created project.

    This handles the full MCP auto-registration flow: building the transport URL,
    creating API keys if needed, validating conflicts, and calling update_server.

    Raises HTTPException on conflicts or unsupported auth types.
    """
    try:
        streamable_http_url = await get_project_streamable_http_url(project.id)

        if default_auth.get("auth_type", "none") == "apikey":
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
        elif default_auth.get("auth_type", "none") == "oauth":
            msg = "OAuth authentication is not yet implemented for MCP server creation during project creation."
            await logger.awarning(msg)
            return
        else:
            command = "uvx"
            args = [
                "mcp-proxy",
                "--transport",
                "streamablehttp",
                streamable_http_url,
            ]

        server_config = {"command": command, "args": args}

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

        if validation_result.should_skip:
            await logger.adebug(
                "MCP server '%s' already exists for project %s, updating",
                validation_result.server_name,
                project.id,
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
    except Exception as e:  # noqa: BLE001
        await logger.aexception("Failed to auto-register MCP server for project %s: %s", project.id, e)


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
