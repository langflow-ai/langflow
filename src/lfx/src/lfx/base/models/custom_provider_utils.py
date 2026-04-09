"""Helpers to load custom provider models into the unified model system."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from lfx.log.logger import logger
from lfx.utils.async_helpers import run_until_complete

_DEFAULT_MODEL_COUNT = 5


def _normalize_user_id(user_id: UUID | str) -> UUID:
    """Normalize a string or UUID user_id to a UUID object."""
    if isinstance(user_id, UUID):
        return user_id
    return UUID(str(user_id))


def get_custom_provider_options(user_id: UUID | str | None) -> list[dict[str, Any]]:
    """Fetch custom providers from DB and return model option dicts."""
    if not user_id:
        return []
    try:
        return run_until_complete(_fetch_options(_normalize_user_id(user_id)))
    except Exception:  # noqa: BLE001
        logger.debug("Could not load custom providers")
        return []


async def _fetch_options(user_id: UUID) -> list[dict[str, Any]]:
    try:
        from langflow.services.deps import session_scope
        from sqlalchemy.orm import selectinload
        from sqlmodel import select
    except ImportError:
        return []

    options = []
    try:
        async with session_scope() as session:
            from langflow.services.database.models.custom_provider.model import CustomProvider

            stmt = (
                select(CustomProvider)
                .options(selectinload(CustomProvider.models))
                .where(CustomProvider.user_id == user_id)
            )
            providers = list((await session.exec(stmt)).all())

            for cp in providers:
                for idx, model in enumerate(cp.models):
                    options.append(
                        {
                            "name": model.name,
                            "icon": "Bot",
                            "category": cp.name,
                            "provider": cp.name,
                            "metadata": {
                                "model_class": "ChatOpenAI",
                                "model_name_param": "model",
                                "api_key_param": "api_key",
                                "base_url_param": "base_url",
                                "custom_provider_id": str(cp.id),
                                "is_custom_provider": True,
                                "tool_calling": model.tool_calling,
                                "default": idx < _DEFAULT_MODEL_COUNT,
                            },
                        }
                    )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Error fetching custom providers: {e}")

    return options


def get_custom_provider_credentials(custom_provider_id: str, user_id: UUID | str) -> tuple[str, str] | None:
    """Fetch (base_url, decrypted_api_key) for a custom provider. Returns None if not found."""
    try:
        return run_until_complete(_fetch_credentials(custom_provider_id, _normalize_user_id(user_id)))
    except Exception:  # noqa: BLE001
        logger.debug(f"Could not fetch custom provider credentials for {custom_provider_id}")
        return None


async def _fetch_credentials(custom_provider_id: str, user_id: UUID) -> tuple[str, str] | None:
    try:
        from langflow.services.auth import utils as auth_utils
        from langflow.services.deps import session_scope
        from sqlmodel import select
    except ImportError:
        return None

    # Convert string IDs to UUID objects for sa.Uuid() column comparison
    provider_uuid = UUID(custom_provider_id) if isinstance(custom_provider_id, str) else custom_provider_id
    user_uuid = user_id

    try:
        async with session_scope() as session:
            from langflow.services.database.models.custom_provider.model import CustomProvider

            stmt = select(CustomProvider).where(
                CustomProvider.id == provider_uuid,
                CustomProvider.user_id == user_uuid,
            )
            cp = (await session.exec(stmt)).first()
            if not cp:
                return None
            decrypted_key = auth_utils.decrypt_api_key(cp.api_key)
            return (cp.base_url, decrypted_key)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Error fetching custom provider credentials: {e}")
        return None
