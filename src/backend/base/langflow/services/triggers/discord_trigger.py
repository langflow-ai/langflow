from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from loguru import logger
from sqlmodel import select

from langflow.services.database.models.subscription.model import Subscription
from langflow.services.deps import session_scope
from langflow.services.triggers.base_trigger import BaseTrigger

if TYPE_CHECKING:
    from langflow.services.discord.service import DiscordService


class DiscordTrigger(BaseTrigger):
    """Base class for Discord triggers."""

    event_type: ClassVar[str] = "discord_message_received"

    # A reference to the Discord service
    _discord_service: DiscordService | None = None

    # Configuration
    discord_user_id: str  # Discord user ID to listen for (or "*" for all users)
    discord_username: str  # Friendly name for display purposes

    def __init__(self, discord_user_id: str = "*", discord_username: str = "Any Discord User"):
        self.discord_user_id = discord_user_id
        self.discord_username = discord_username

    @classmethod
    def from_component_data(cls, component_data: dict[str, Any]) -> BaseTrigger:
        """Create a trigger instance from component data."""
        discord_user_id = component_data.get("discord_user_id", "*")
        discord_username = component_data.get("discord_username", "Any Discord User")
        return cls(discord_user_id=discord_user_id, discord_username=discord_username)

    @classmethod
    def set_discord_service(cls, discord_service: DiscordService) -> None:
        """Initialize the Discord service used by the trigger."""
        cls._discord_service = discord_service
        logger.info("Discord service set for Discord trigger")

    def initial_state(self) -> str:
        """Return the initial state for this trigger."""
        state = {
            "last_checked": datetime.now(timezone.utc).isoformat(),
            "last_message_id": None,
            "config": {"discord_user_id": self.discord_user_id, "discord_username": self.discord_username},
        }
        return json.dumps(state)

    @classmethod
    async def check_events(cls, _subscription: Subscription) -> list[dict[str, Any]]:
        """Check for new Discord events for a given subscription.

        With direct processing enabled, this method is no longer needed for active
        event processing, but is kept for compatibility with the trigger system.
        It will always return an empty list since events are processed directly.

        Args:
            _subscription: The subscription to check events for

        Returns:
            An empty list, as events are processed directly
        """
        # Direct processing handles events immediately, so this method
        # doesn't need to return any events
        return []

    @classmethod
    async def _get_subscription_discord_user_id(cls, subscription_id: str | UUID) -> str:
        """Get the Discord user ID for a subscription."""
        # Default to "*" (any user) if we can't determine the actual user ID
        discord_user_id = "*"

        try:
            async with session_scope() as session:
                if isinstance(subscription_id, str):
                    subscription_id = UUID(subscription_id)
                result = await session.exec(select(Subscription).where(Subscription.id == subscription_id))
                subscription = result.first()

                if subscription and subscription.state:
                    state = json.loads(subscription.state)
                    config = state.get("config", {})
                    discord_user_id = config.get("discord_user_id", "*")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error getting Discord user ID for subscription {subscription_id}: {e}")

        return discord_user_id
