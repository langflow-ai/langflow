from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from langflow.services.database.models.subscription.model import Subscription


class BaseTrigger(ABC):
    """Base class for all trigger components.

    Triggers are components that can create tasks based on external events.
    Each trigger type should subclass this and implement the required methods.
    """

    # Class variable that should be overridden by subclasses
    event_type: ClassVar[str]

    @classmethod
    @abstractmethod
    def from_component_data(cls, component_data: dict[str, Any]) -> BaseTrigger:
        """Create a trigger instance from component data in the flow."""
        raise NotImplementedError

    @abstractmethod
    def initial_state(self) -> str:
        """Return the initial state for this trigger as a JSON string."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def check_events(cls, subscription: Subscription) -> list[dict[str, Any]]:
        """Check for events based on the subscription.

        Args:
            subscription: The subscription to check events for

        Returns:
            A list of event data dictionaries, each containing trigger_data
            that will be passed to the flow as input
        """
        raise NotImplementedError

    @staticmethod
    def update_last_checked(subscription: Subscription) -> None:
        """Update the last_checked timestamp in the subscription state."""
        try:
            state = json.loads(subscription.state or "{}")
            state["last_checked"] = datetime.now(tz=timezone.utc).isoformat()
            subscription.state = json.dumps(state)
        except Exception as e:
            msg = f"Failed to update last_checked timestamp: {e}"
            raise ValueError(msg) from e
