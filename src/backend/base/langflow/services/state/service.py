from collections import defaultdict
from collections.abc import Callable
from threading import Lock

from lfx.services.settings.service import SettingsService
from loguru import logger

from langflow.services.base import Service


class StateService(Service):
    name = "state_service"

    def append_state(self, key, new_state, run_id: str) -> None:
        raise NotImplementedError

    def update_state(self, key, new_state, run_id: str) -> None:
        raise NotImplementedError

    def get_state(self, key, run_id: str):
        raise NotImplementedError

    def subscribe(self, key, observer: Callable) -> None:
        raise NotImplementedError

    def unsubscribe(self, key, observer: Callable) -> None:
        raise NotImplementedError

    def notify_observers(self, key, new_state) -> None:
        raise NotImplementedError


class InMemoryStateService(StateService):
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self.states: dict[str, dict] = {}
        self.observers: dict[str, list[Callable]] = defaultdict(list)
        self.lock = Lock()

    def append_state(self, key, new_state, run_id: str) -> None:
        with self.lock:
            if run_id not in self.states:
                self.states[run_id] = {}
            if key not in self.states[run_id]:
                self.states[run_id][key] = []
            elif not isinstance(self.states[run_id][key], list):
                self.states[run_id][key] = [self.states[run_id][key]]
            self.states[run_id][key].append(new_state)
            self.notify_append_observers(key, new_state)

    def update_state(self, key, new_state, run_id: str) -> None:
        with self.lock:
            if run_id not in self.states:
                self.states[run_id] = {}
            self.states[run_id][key] = new_state
            self.notify_observers(key, new_state)

    def get_state(self, key, run_id: str):
        with self.lock:
            return self.states.get(run_id, {}).get(key, "")

    def subscribe(self, key, observer: Callable) -> None:
        with self.lock:
            if observer not in self.observers[key]:
                self.observers[key].append(observer)

    def notify_observers(self, key, new_state) -> None:
        for callback in self.observers[key]:
            callback(key, new_state, append=False)

    def notify_append_observers(self, key, new_state) -> None:
        for callback in self.observers[key]:
            try:
                callback(key, new_state, append=True)
            except Exception:  # noqa: BLE001
                logger.exception(f"Error in observer {callback} for key {key}")
                logger.warning("Callbacks not implemented yet")

    def unsubscribe(self, key, observer: Callable) -> None:
        with self.lock:
            if observer in self.observers[key]:
                # Use list.remove() since observers[key] is a list
                self.observers[key].remove(observer)
