from collections import defaultdict
from threading import Lock
from typing import Callable

from loguru import logger


class GraphStateManager:
    def __init__(self):
        self.states = {}
        self.observers = defaultdict(list)
        self.lock = Lock()

    def append_state(self, key, new_state, run_id: str):
        with self.lock:
            if run_id not in self.states:
                self.states[run_id] = {}
            if key not in self.states[run_id]:
                self.states[run_id][key] = []
            elif not isinstance(self.states[key], list):
                self.states[run_id][key] = [self.states[key]]
            self.states[run_id][key].append(new_state)
            self.notify_append_observers(key, new_state)

    def update_state(self, key, new_state, run_id: str):
        with self.lock:
            if run_id not in self.states:
                self.states[run_id] = {}
            if key not in self.states[run_id]:
                self.states[run_id][key] = {}
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
