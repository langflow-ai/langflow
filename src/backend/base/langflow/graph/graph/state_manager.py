from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from langflow.services.deps import get_settings_service, get_state_service

if TYPE_CHECKING:
    from collections.abc import Callable

    from langflow.services.state.service import StateService


class GraphStateManager:
    def __init__(self):
        try:
            self.state_service: StateService = get_state_service()
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug("Error getting state service. Defaulting to InMemoryStateService")
            from langflow.services.state.service import InMemoryStateService

            self.state_service = InMemoryStateService(get_settings_service())

    def append_state(self, key, new_state, run_id: str):
        self.state_service.append_state(key, new_state, run_id)

    def update_state(self, key, new_state, run_id: str):
        self.state_service.update_state(key, new_state, run_id)

    def get_state(self, key, run_id: str):
        return self.state_service.get_state(key, run_id)

    def subscribe(self, key, observer: Callable):
        self.state_service.subscribe(key, observer)

    def notify_observers(self, key, new_state):
        for callback in self.observers[key]:
            callback(key, new_state, append=False)

    def notify_append_observers(self, key, new_state):
        for callback in self.observers[key]:
            try:
                callback(key, new_state, append=True)
            except Exception:  # noqa: BLE001
                logger.exception(f"Error in observer {callback} for key {key}")
                logger.warning("Callbacks not implemented yet")
