from collections import defaultdict
from threading import Lock
from typing import Callable

from loguru import logger

from langflow.services.base import Service
from langflow.services.settings.service import SettingsService


class StateService(Service):
    name = "state_service"

    def append_state(self, key, new_state, run_id: str):
        raise NotImplementedError

    def update_state(self, key, new_state, run_id: str):
        raise NotImplementedError

    def get_state(self, key, run_id: str):
        raise NotImplementedError

    def subscribe(self, key, observer: Callable):
        raise NotImplementedError

    def notify_observers(self, key, new_state):
        raise NotImplementedError


class InMemoryStateService(StateService):
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self.states: dict = {}
        self.observers: dict = defaultdict(list)
        self.lock = Lock()

    def append_state(self, key, new_state, run_id: str):
        with self.lock:
            if run_id not in self.states:
                self.states[run_id] = {}
            if key not in self.states[run_id]:
                self.states[run_id][key] = []
            elif not isinstance(self.states[run_id][key], list):
                self.states[run_id][key] = [self.states[run_id][key]]
            self.states[run_id][key].append(new_state)
            self.notify_append_observers(key, new_state)

    def update_state(self, key, new_state, run_id: str):
        with self.lock:
            if run_id not in self.states:
                self.states[run_id] = {}
            self.states[run_id][key] = new_state
            self.notify_observers(key, new_state)

    def get_state(self, key, run_id: str):
        with self.lock:
            return self.states.get(run_id, {}).get(key, "")

    def subscribe(self, key, observer: Callable):
        with self.lock:
            if observer not in self.observers[key]:
                self.observers[key].append(observer)

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
