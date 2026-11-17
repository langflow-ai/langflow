from __future__ import annotations

import asyncio
import inspect
import json
import time
import uuid
from functools import partial
from typing import TYPE_CHECKING

from fastapi.encoders import jsonable_encoder
from typing_extensions import Protocol

from lfx.log.logger import logger
from lfx.serialization.serialization import serialize

if TYPE_CHECKING:
    from lfx.schema.log import OnTokenFunctionType

    # Lightweight type stub for log types
    LoggableType = dict | str | int | float | bool | list | None


class EventCallback(Protocol):
    def __call__(self, *, manager: EventManager, event_type: str, data: LoggableType): ...


class PartialEventCallback(Protocol):
    def __call__(self, *, data: LoggableType): ...


class EventManager:
    def __init__(self, queue):
        self.queue = queue
        self.events: dict[str, PartialEventCallback] = {}
        try:
            self._loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

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
        event_type: str,
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

    @staticmethod
    def _queue_item(event_type: str, data: LoggableType) -> tuple[str, bytes, float]:
        try:
            jsonable_data = jsonable_encoder(data)
        except (ValueError, TypeError) as exc:
            # Component payloads can contain objects that FastAPI's jsonable_encoder
            # cannot serialize — e.g. a vector-DB client holding a ``threading.Lock``
            # surfaced through a Loop's per-iteration build events (issue #12591).
            # jsonable_encoder's last-resort fallback raises ``ValueError([TypeError, ...])``
            # there, which would otherwise abort the entire flow build. Degrade to the
            # fail-safe serializer, which converts unknown objects to a string
            # representation instead of crashing.
            logger.debug(f"jsonable_encoder failed for event '{event_type}'; using safe serializer: {exc}")
            jsonable_data = serialize(data, to_str=True)
        json_data = {"event": event_type, "data": jsonable_data}
        event_id = f"{event_type}-{uuid.uuid4()}"
        str_data = json.dumps(json_data) + "\n\n"
        return event_id, str_data.encode("utf-8"), time.time()

    def send_event(self, *, event_type: str, data: LoggableType):
        item = self._queue_item(event_type, data)
        if self.queue:
            try:
                try:
                    asyncio.get_running_loop()
                    in_event_loop = True
                except RuntimeError:
                    in_event_loop = False

                if in_event_loop:
                    # Called from within the event loop — safe to call directly
                    self.queue.put_nowait(item)
                elif self._loop is not None and self._loop.is_running():
                    # Called from a thread outside the event loop (e.g. sync tool in executor)
                    # Use call_soon_threadsafe so asyncio wakes up the queue getter properly
                    try:
                        self._loop.call_soon_threadsafe(self.queue.put_nowait, item)
                    except RuntimeError:
                        logger.warning(
                            "Event loop stopped before event could be scheduled; event_type=%s dropped", event_type
                        )
                else:
                    # Sync context with no event loop — call directly (e.g. unit tests)
                    self.queue.put_nowait(item)
            except asyncio.QueueFull:
                logger.warning("Event queue full; dropping event_type=%s", event_type)
            except Exception:  # noqa: BLE001
                logger.error("Unexpected error dispatching event_type=%s", event_type, exc_info=True)

    def noop(self, *, data: LoggableType) -> None:
        pass

    async def put_token(self, data: dict) -> None:
        """Wait for space on the queue's owning loop."""
        if self.queue is None:
            return
        pending = self.queue.put(self._queue_item("token", data))
        if self._loop is None or self._loop is asyncio.get_running_loop():
            await pending
        else:
            await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(pending, self._loop))

    def __getattr__(self, name: str) -> PartialEventCallback:
        return self.events.get(name, self.noop)


class _QueuedTokenCallback:
    """Offer async producers backpressure while retaining the synchronous callback API."""

    def __init__(self, manager: EventManager) -> None:
        self.manager = manager

    def __call__(self, data: LoggableType) -> None:
        self.manager.send_event(event_type="token", data=data)


async def emit_token(callback: OnTokenFunctionType | PartialEventCallback, *, data: dict) -> None:
    """Wait for background queue space or run the component's synchronous callback off-loop."""
    if isinstance(callback, _QueuedTokenCallback):
        await callback.manager.put_token(data)
    else:
        await asyncio.to_thread(callback, data=data)


def create_default_event_manager(queue=None, *, await_token_capacity: bool = False):
    manager = EventManager(queue)
    if await_token_capacity:
        manager.events["on_token"] = _QueuedTokenCallback(manager)
    else:
        manager.register_event("on_token", "token")
    manager.register_event("on_vertices_sorted", "vertices_sorted")
    manager.register_event("on_error", "error")
    manager.register_event("on_end", "end")
    manager.register_event("on_message", "add_message")
    manager.register_event("on_remove_message", "remove_message")
    manager.register_event("on_end_vertex", "end_vertex")
    manager.register_event("on_build_start", "build_start")
    manager.register_event("on_build_end", "build_end")
    manager.register_event("on_log", "log")
    return manager


def create_stream_tokens_event_manager(queue=None):
    manager = EventManager(queue)
    manager.register_event("on_message", "add_message")
    manager.register_event("on_token", "token")
    manager.register_event("on_end", "end")
    manager.register_event("on_end_vertex", "end_vertex")
    manager.register_event("on_error", "error")
    manager.register_event("on_build_start", "build_start")
    manager.register_event("on_build_end", "build_end")
    manager.register_event("on_log", "log")
    return manager
