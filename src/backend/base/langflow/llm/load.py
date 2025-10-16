from uuid import UUID

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.llm.utils import load_llm_settings_from_db
from langflow.services.settings.llm import LLMSettings
from langflow.services.variable.service import DatabaseVariableService

# Cache to store the initialized chat model
_CHAT_MODEL_CACHE: dict[tuple[str, str, str | None, str | None], BaseChatModel] = {}


async def load_llm(llm_settings: LLMSettings) -> BaseChatModel:
    """Load a chat model based on the provided LLM settings.

    Uses the universal init_chat_model function to initialize the appropriate
    chat model based on the provider, model, and API key.

    The model is cached based on its configuration to avoid reinitializing
    the same model multiple times.

    Args:
        llm_settings: Configuration settings for the LLM

    Returns:
        An initialized chat model instance

    Raises:
        ValueError: If the API key is not provided in the settings
    """
    return await _fetch_llm_instance(llm_settings)


async def load_llm_for_user(
    user_id: UUID | str,
    variable_service: DatabaseVariableService,
    session: AsyncSession,
    override_settings: LLMSettings | None = None,
) -> BaseChatModel:
    """Load a chat model for a specific user, using their saved settings from the database.

    If override_settings is provided, those settings will be used instead of the database settings.

    Args:
        user_id: The user ID
        variable_service: The Variable service
        session: The database session
        override_settings: Optional settings to override the database settings

    Returns:
        An initialized chat model instance

    Raises:
        ValueError: If the API key is not available
    """
    # Use override settings if provided, otherwise load from database
    if override_settings:
        llm_settings = override_settings
    else:
        llm_settings = await load_llm_settings_from_db(
            user_id=user_id,
            variable_service=variable_service,
            session=session,
        )

    # Load the model
    return await _fetch_llm_instance(llm_settings)


async def _fetch_llm_instance(llm_settings: LLMSettings) -> BaseChatModel:
    """Internal function to fetch or initialize an LLM instance.

    Args:
        llm_settings: Configuration settings for the LLM

    Returns:
        An initialized chat model instance

    Raises:
        ValueError: If the API key is not provided in the settings
    """
    if not llm_settings.api_key:
        msg = "API key is required to initialize the global chat model"
        raise ValueError(msg)

    # Create a cache key based on the model configuration
    cache_key = (
        llm_settings.provider,
        llm_settings.model,
        llm_settings.api_key,
        getattr(llm_settings, "base_url", None),
    )

    # Return cached model if it exists
    if cache_key in _CHAT_MODEL_CACHE:
        return _CHAT_MODEL_CACHE[cache_key]

    # Initialize and cache the model
    model = init_chat_model(
        model=llm_settings.model,
        model_provider=llm_settings.provider,
        api_key=llm_settings.api_key,
        base_url=llm_settings.base_url if hasattr(llm_settings, "base_url") else None,
    )

    _CHAT_MODEL_CACHE[cache_key] = model
    return model
