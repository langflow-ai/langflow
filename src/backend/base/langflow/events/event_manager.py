import asyncio
import json
import time
import uuid
from functools import partial

from typing_extensions import Protocol

from langflow.schema.log import LoggableType


class EventCallback(Protocol):
    def __call__(self, event_type: str, data: LoggableType): ...


class EventManager:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.events: dict[str, EventCallback] = {}

    def register_event(self, name: str, event_type: str | None = None):
        if event_type is None:
            self.events[name] = self.send_event
        else:
            self.events[name] = partial(self.send_event, event_type)

    def register_event_function(self, name: str, event_function: EventCallback):
        self.events[name] = event_function

    def send_event(self, event_type: str, data: dict):
        json_data = {"event": event_type, "data": data}
        event_id = uuid.uuid4()
        str_data = json.dumps(json_data) + "\n\n"
        self.queue.put_nowait((event_id, str_data.encode("utf-8"), time.time()))

    def noop(self, event_type: str, data: dict):
        pass

    def __getattr__(self, name: str) -> EventCallback:
        return self.events.get(name, self.noop)


def create_default_event_manager(queue):
    manager = EventManager(queue)
    manager.register_event("on_token", "token")
    manager.register_event("on_vertices_sorted", "vertices_sorted")
    manager.register_event("on_error", "error")
    manager.register_event("on_end", "end")
    manager.register_event("on_message", "message")
    manager.register_event("on_end_vertex", "end_vertex")
    return manager
