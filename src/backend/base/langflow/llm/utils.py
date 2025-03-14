"""Utility functions for LLM settings."""

from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.settings.llm import LLMSettings
from langflow.services.variable.service import DatabaseVariableService


async def save_llm_settings_to_db(
    user_id: UUID | str,
    llm_settings: LLMSettings,
    variable_service: DatabaseVariableService,
    session: AsyncSession,
) -> None:
    """Save LLM settings to the database using the Variable service.

    Args:
        user_id: The user ID
        llm_settings: The LLMSettings object
        variable_service: The Variable service
        session: The database session
    """
    # Convert LLMSettings to dictionary
    settings_dict = llm_settings.model_dump()

    # Save to database
    await variable_service.save_llm_settings(
        user_id=user_id,
        llm_settings=settings_dict,
        session=session,
    )


async def load_llm_settings_from_db(
    user_id: UUID | str,
    variable_service: DatabaseVariableService,
    session: AsyncSession,
) -> LLMSettings:
    """Load LLM settings from the database using the Variable service.

    Args:
        user_id: The user ID
        variable_service: The Variable service
        session: The database session

    Returns:
        LLMSettings object with values from the database or defaults
    """
    # Get settings from database
    settings_dict = await variable_service.get_llm_settings(
        user_id=user_id,
        session=session,
    )

    # Create LLMSettings object (will use defaults for missing values)
    return LLMSettings(**settings_dict)
