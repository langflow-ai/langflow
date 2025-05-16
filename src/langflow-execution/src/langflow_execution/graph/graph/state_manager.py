from __future__ import annotations

from typing import TYPE_CHECKING

# TODO: Split Settings into separate set of execution-specific configs
from langflow.services.deps import get_settings_service

from langflow_execution.service.state.service import InMemoryStateService

if TYPE_CHECKING:
    from collections.abc import Callable


class GraphStateManager:
    def __init__(self) -> None:
        self.state_service = InMemoryStateService(get_settings_service())

    def append_state(self, key, new_state, run_id: str) -> None:
        self.state_service.append_state(key, new_state, run_id)

    def update_state(self, key, new_state, run_id: str) -> None:
        self.state_service.update_state(key, new_state, run_id)

    def get_state(self, key, run_id: str):
        return self.state_service.get_state(key, run_id)

    def subscribe(self, key, observer: Callable) -> None:
        self.state_service.subscribe(key, observer)

    def unsubscribe(self, key, observer: Callable) -> None:
        self.state_service.unsubscribe(key, observer)
