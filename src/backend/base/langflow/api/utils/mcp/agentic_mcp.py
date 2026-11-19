"""Per-user agentic global variables (FLOW_ID, COMPONENT_ID, FIELD_NAME).

The MCP-server auto-configuration that used to live here was removed: external
clients connect to the HTTP mount at ``/api/v1/agentic/mcp`` with their own API
key instead of a per-user auto-registered stdio entry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service
from lfx.services.settings.constants import AGENTIC_VARIABLES, DEFAULT_AGENTIC_VARIABLE_VALUE
from sqlalchemy import false, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select

from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlmodel.ext.asyncio.session import AsyncSession

# Startup initialization seeds these context placeholders as empty Generic rows.
# Login/user initialization also seeds ASTRA_TOKEN (via AGENTIC_VARIABLES).
_STARTUP_AGENTIC_PLACEHOLDERS = {
    "FLOW_ID": DEFAULT_AGENTIC_VARIABLE_VALUE,
    "COMPONENT_ID": DEFAULT_AGENTIC_VARIABLE_VALUE,
    "FIELD_NAME": DEFAULT_AGENTIC_VARIABLE_VALUE,
}


async def _use_read_committed_if_possible(session: AsyncSession) -> None:
    """Use a fresh READ COMMITTED snapshot without ending caller-owned work."""
    if session.get_bind().dialect.name != "postgresql":
        return
    if not session.in_transaction():
        await session.connection(execution_options={"isolation_level": "READ COMMITTED"})
    else:
        connection = await session.connection()
        if await connection.get_isolation_level() != "READ COMMITTED":
            msg = "Agentic variable initialization needs READ COMMITTED; call it before starting a transaction"
            raise RuntimeError(msg)


async def _serialize_agentic_variable_initialization(session: AsyncSession, user_id: UUID | str) -> None:
    """Reserve the user before checking placeholders, matching environment imports.

    Row locks avoid an advisory-lock entry per user during a startup sweep. The
    caller owns the transaction and therefore the lifetime of these reservations.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        await session.exec(select(User.id).where(User.id == UUID(str(user_id))).with_for_update())
    elif dialect == "sqlite":
        # Reserve SQLite's writer before reading, without changing any rows.
        await session.exec(update(Variable).where(false()).values(name=Variable.name))


async def _create_missing_agentic_variables(
    session: AsyncSession,
    user_id: UUID | str,
    agentic_variables: Mapping[str, str],
    type_: str,
    *,
    user_label: str,
) -> tuple[int, int]:
    """Create missing placeholders without overwriting or deleting existing rows.

    Returns:
        A ``(created, skipped)`` count pair for this user.
    """
    await _serialize_agentic_variable_initialization(session, user_id)
    variable_service = get_variable_service()
    existing_counts = await variable_service.existing_variable_name_counts(
        user_id, list(agentic_variables), session=session
    )
    created = 0
    skipped = 0

    for var_name, default_value in agentic_variables.items():
        existing_count = existing_counts.get(var_name, 0)
        if existing_count:
            if existing_count > 1:
                await logger.awarning(
                    "User %s already has %s rows named %s; leaving historical duplicates unchanged",
                    user_label,
                    existing_count,
                    var_name,
                )
            skipped += 1
            await logger.adebug(f"Agentic variable {var_name} already exists for user {user_label}, skipping")
            continue
        try:
            async with session.begin_nested():
                await variable_service.create_variable(
                    user_id=user_id,
                    name=var_name,
                    value=default_value,
                    default_fields=[],
                    type_=type_,
                    session=session,
                )
            created += 1
            existing_counts[var_name] = 1
            await logger.adebug(f"Created agentic variable {var_name} for user {user_label}")
        except IntegrityError as e:
            if not session.is_active or e.connection_invalidated:
                raise
            counts = await variable_service.existing_variable_name_counts(user_id, [var_name], session=session)
            if counts.get(var_name):
                skipped += 1
                existing_counts[var_name] = counts[var_name]
                await logger.adebug(
                    "Agentic variable %s already exists for user %s after a concurrent insert, skipping",
                    var_name,
                    user_label,
                )
            else:
                await logger.aexception(f"Error creating agentic variable {var_name} for user {user_label}: {e}")
        except SQLAlchemyError as e:
            if not session.is_active or getattr(e, "connection_invalidated", False):
                raise
            await logger.aexception(f"Error creating agentic variable {var_name} for user {user_label}: {e}")
        except (
            HTTPException,
            OSError,
            PermissionError,
            FileNotFoundError,
            RuntimeError,
            ValueError,
            AttributeError,
        ) as e:
            await logger.aexception(f"Error creating agentic variable {var_name} for user {user_label}: {e}")

    return created, skipped


async def initialize_agentic_global_variables(session: AsyncSession) -> None:
    """Initialize default global variables for agentic experience for all users.

    This function creates agentic-specific global variables (FLOW_ID, COMPONENT_ID, FIELD_NAME)
    for all users if they don't already exist. These variables are used by the agentic
    experience to provide context-aware suggestions and operations.

    Existence is determined by a user-and-name query that includes empty placeholder
    values, so repeated boots and concurrent workers do not create additional copies.
    Existing rows, including user-edited values and historical duplicates, are left
    unchanged.

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
        await _use_read_committed_if_possible(session)

        # Get all users in the system
        users = (await session.exec(select(User).order_by(User.id))).all()
        await logger.adebug(f"Found {len(users)} users for agentic variables initialization")

        if not users:
            await logger.adebug("No users found, skipping agentic variables initialization")
            return

        # Initialize variables for each user
        variables_created = 0
        variables_skipped = 0

        for user in users:
            try:
                await logger.adebug(f"Initializing agentic variables for user: {user.username}")
                created, skipped = await _create_missing_agentic_variables(
                    session,
                    user.id,
                    _STARTUP_AGENTIC_PLACEHOLDERS,
                    GENERIC_TYPE,
                    user_label=user.username,
                )
                variables_created += created
                variables_skipped += skipped

            except (
                HTTPException,
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
        await _use_read_committed_if_possible(session)
        agentic_variables = dict.fromkeys(AGENTIC_VARIABLES, DEFAULT_AGENTIC_VARIABLE_VALUE)
        await logger.adebug(f"Agentic variables: {list(agentic_variables.keys())}")
        await _create_missing_agentic_variables(
            session,
            user_id,
            agentic_variables,
            CREDENTIAL_TYPE,
            user_label=str(user_id),
        )

    except (
        HTTPException,
        OSError,
        PermissionError,
        FileNotFoundError,
        RuntimeError,
        ValueError,
        AttributeError,
    ) as e:
        await logger.aexception(f"Error initializing agentic variables for user {user_id}: {e}")
