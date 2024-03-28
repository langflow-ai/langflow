from typing import TYPE_CHECKING, Callable

from langflow.services.deps import get_state_service
from loguru import logger

if TYPE_CHECKING:
    from langflow.services.state.service import StateService


class GraphStateManager:
    def __init__(self):
        self.state_service: "StateService" = get_state_service()

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
            except Exception as e:
                logger.error(f"Error in observer {callback} for key {key}: {e}")
                logger.warning("Callbacks not implemented yet")
