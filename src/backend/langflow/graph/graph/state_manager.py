from collections import defaultdict
from threading import Lock
from typing import Callable


class GraphStateManager:
    def __init__(self):
        self.states = {}
        self.observers = defaultdict(list)
        self.lock = Lock()

    def append_state(self, key, new_state):
        with self.lock:
            if key not in self.states:
                self.states[key] = []
            self.states[key].append(new_state)
            self.notify_append_observers(key, new_state)

    def update_state(self, key, new_state):
        with self.lock:
            self.states[key] = new_state
            self.notify_observers(key, new_state)

    def get_state(self, key):
        with self.lock:
            return self.states.get(key, None)

    def subscribe(self, key, observer: Callable):
        with self.lock:
            if observer not in self.observers[key]:
                self.observers[key].append(observer)

    def notify_observers(self, key, new_state):
        for callback in self.observers[key]:
            callback(key, new_state, append=False)

    def notify_append_observers(self, key, new_state):
        for callback in self.observers[key]:
            callback(key, new_state, append=True)
