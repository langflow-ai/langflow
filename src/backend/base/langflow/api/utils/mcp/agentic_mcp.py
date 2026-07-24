"""Per-user agentic global variables (FLOW_ID, COMPONENT_ID, FIELD_NAME).

The MCP-server auto-configuration that used to live here was removed: external
clients connect to the HTTP mount at ``/api/v1/agentic/mcp`` with their own API
key instead of a per-user auto-registered stdio entry.
"""

from uuid import UUID

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service
from sqlalchemy import exc as sqlalchemy_exc
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.user.model import User
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE


async def initialize_agentic_global_variables(session: AsyncSession) -> None:
    """Initialize default global variables for agentic experience for all users.

    This function creates agentic-specific global variables (FLOW_ID, COMPONENT_ID, FIELD_NAME)
    for all users if they don't already exist. These variables are used by the agentic
    experience to provide context-aware suggestions and operations.

    Args:
        session: Database session for querying users and creating variables.
    """
    settings_service = get_settings_service()

    # Only initialize if agentic experience is enabled
    if not settings_service.settings.agentic_experience:
        await logger.adebug("Agentic experience disabled, skipping agentic variables initialization")
        return

    await logger.ainfo("Initializing agentic global variables for all users...")

    try:
        # Get all users in the system
        users = (await session.exec(select(User))).all()
        await logger.adebug(f"Found {len(users)} users for agentic variables initialization")

        if not users:
            await logger.adebug("No users found, skipping agentic variables initialization")
            return

        variable_service = get_variable_service()

        # Define agentic variables with default values
        agentic_variables = {
            "FLOW_ID": "",
            "COMPONENT_ID": "",
            "FIELD_NAME": "",
        }

        # Initialize variables for each user
        variables_created = 0
        variables_skipped = 0

        for user in users:
            try:
                await logger.adebug(f"Initializing agentic variables for user: {user.username}")

                # Get existing variables for this user
                existing_vars = await variable_service.list_variables(user.id, session)

                for var_name, default_value in agentic_variables.items():
                    try:
                        if var_name not in existing_vars:
                            # Create variable with default value
                            await variable_service.create_variable(
                                user_id=user.id,
                                name=var_name,
                                value=default_value,
                                default_fields=[],
                                type_=GENERIC_TYPE,
                                session=session,
                            )
                            variables_created += 1
                            await logger.adebug(f"Created agentic variable {var_name} for user {user.username}")
                        else:
                            variables_skipped += 1
                            await logger.adebug(
                                f"Agentic variable {var_name} already exists for user {user.username}, skipping"
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
                    ) as e:
                        await logger.aexception(
                            f"Error creating agentic variable {var_name} for user {user.username}: {e}"
                        )
                        continue

            except (
                HTTPException,
                sqlalchemy_exc.SQLAlchemyError,
                OSError,
                PermissionError,
                FileNotFoundError,
                RuntimeError,
                ValueError,
                AttributeError,
            ) as e:
                await logger.aexception(f"Failed to initialize agentic variables for user {user.username}: {e}")
                continue

        await logger.ainfo(
            f"Agentic variables initialization complete: {variables_created} created, {variables_skipped} skipped"
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
    ) as e:
        await logger.aexception(f"Error during agentic variables initialization: {e}")


async def initialize_agentic_user_variables(user_id: UUID | str, session: AsyncSession) -> None:
    """Initialize agentic-specific global variables for a single user if they don't exist.

    This function is called during user login or creation to ensure each user has the
    required agentic variables (FLOW_ID, COMPONENT_ID, FIELD_NAME).

    Args:
        user_id: The user ID to initialize variables for.
        session: Database session for creating variables.
    """
    settings_service = get_settings_service()

    # Only initialize if agentic experience is enabled
    if not settings_service.settings.agentic_experience:
        await logger.adebug(f"Agentic experience disabled, skipping agentic variables for user {user_id}")
        return

    await logger.adebug(f"Initializing agentic variables for user {user_id}")

    try:
        variable_service = get_variable_service()

        # Define agentic variables with defaults
        from lfx.services.settings.constants import AGENTIC_VARIABLES, DEFAULT_AGENTIC_VARIABLE_VALUE

        # Create a dict with agentic variable names and default values as empty strings
        agentic_variables = dict.fromkeys(AGENTIC_VARIABLES, DEFAULT_AGENTIC_VARIABLE_VALUE)
        await logger.adebug(f"Agentic variables: {list(agentic_variables.keys())}")

        existing_vars = await variable_service.list_variables(user_id, session)

        for var_name, default_value in agentic_variables.items():
            logger.adebug(f"Checking if agentic variable {var_name} exists for user {user_id}")
            if var_name not in existing_vars:
                try:
                    await variable_service.create_variable(
                        user_id=user_id,
                        name=var_name,
                        value=default_value,
                        default_fields=[],
                        type_=CREDENTIAL_TYPE,
                        session=session,
                    )
                    await logger.adebug(f"Created agentic variable {var_name} for user {user_id}")
                except (
                    HTTPException,
                    sqlalchemy_exc.SQLAlchemyError,
                    OSError,
                    PermissionError,
                    FileNotFoundError,
                    RuntimeError,
                    ValueError,
                    AttributeError,
                ) as e:
                    await logger.aexception(f"Error creating agentic variable {var_name} for user {user_id}: {e}")
            else:
                await logger.adebug(f"Agentic variable {var_name} already exists for user {user_id}, skipping")

    except (
        HTTPException,
        sqlalchemy_exc.SQLAlchemyError,
        OSError,
        PermissionError,
        FileNotFoundError,
        RuntimeError,
        ValueError,
        AttributeError,
    ) as e:
        await logger.aexception(f"Error initializing agentic variables for user {user_id}: {e}")
