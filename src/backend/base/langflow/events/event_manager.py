import asyncio
import inspect
import json
import time
import uuid
from functools import partial
from typing import Literal

from fastapi.encoders import jsonable_encoder
from loguru import logger
from typing_extensions import Protocol

from langflow.schema.log import LoggableType
from langflow.schema.playground_events import create_event_by_type


class EventCallback(Protocol):
    def __call__(self, *, manager: "EventManager", event_type: str, data: LoggableType): ...


class PartialEventCallback(Protocol):
    def __call__(self, *, data: LoggableType): ...


class EventManager:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.events: dict[str, PartialEventCallback] = {}

    @staticmethod
    def _validate_callback(callback: EventCallback) -> None:
        if not callable(callback):
            msg = "Callback must be callable"
            raise TypeError(msg)
        # Check if it has `self, event_type and data`
        sig = inspect.signature(callback)
        parameters = ["manager", "event_type", "data"]
        if len(sig.parameters) != len(parameters):
            msg = "Callback must have exactly 3 parameters"
            raise ValueError(msg)
        if not all(param.name in parameters for param in sig.parameters.values()):
            msg = "Callback must have exactly 3 parameters: manager, event_type, and data"
            raise ValueError(msg)

    def register_event(
        self,
        name: str,
        event_type: Literal["message", "error", "warning", "info", "token"],
        callback: EventCallback | None = None,
    ) -> None:
        if not name:
            msg = "Event name cannot be empty"
            raise ValueError(msg)
        if not name.startswith("on_"):
            msg = "Event name must start with 'on_'"
            raise ValueError(msg)
        if callback is None:
            callback_ = partial(self.send_event, event_type=event_type)
        else:
            callback_ = partial(callback, manager=self, event_type=event_type)
        self.events[name] = callback_

    def send_event(self, *, event_type: Literal["message", "error", "warning", "info", "token"], data: LoggableType):
        try:
            if isinstance(data, dict) and event_type in {"message", "error", "warning", "info", "token"}:
                data = create_event_by_type(event_type, **data)
        except TypeError as e:
            logger.debug(f"Error creating playground event: {e}")
        except Exception:
            raise
        jsonable_data = jsonable_encoder(data)
        json_data = {"event": event_type, "data": jsonable_data}
        event_id = f"{event_type}-{uuid.uuid4()}"
        str_data = json.dumps(json_data) + "\n\n"
        self.queue.put_nowait((event_id, str_data.encode("utf-8"), time.time()))

    def noop(self, *, data: LoggableType) -> None:
        pass

    def __getattr__(self, name: str) -> PartialEventCallback:
        return self.events.get(name, self.noop)


def create_default_event_manager(queue):
    manager = EventManager(queue)
    manager.register_event("on_token", "token")
    manager.register_event("on_vertices_sorted", "vertices_sorted")
    manager.register_event("on_error", "error")
    manager.register_event("on_end", "end")
    manager.register_event("on_message", "add_message")
    manager.register_event("on_remove_message", "remove_message")
    manager.register_event("on_end_vertex", "end_vertex")
    manager.register_event("on_build_start", "build_start")
    manager.register_event("on_build_end", "build_end")
    return manager
