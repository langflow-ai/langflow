import functools
from collections.abc import Awaitable, Callable
from typing import Any

from ag_ui.encoder.encoder import EventEncoder

from lfx.log.logger import logger

AsyncMethod = Callable[..., Awaitable[Any]]

encoder: EventEncoder = EventEncoder()


def observable(observed_method: AsyncMethod) -> AsyncMethod:
    """Decorator to make an async method observable by emitting lifecycle events.

    Decorated classes are expected to implement specific methods to emit AGUI events:
    - `before_callback_event(*args, **kwargs)`: Called before the decorated method executes.
      It should return a dictionary representing the event payload.
    - `after_callback_event(result, *args, **kwargs)`: Called after the decorated method
      successfully completes. It should return a dictionary representing the event payload.
      The `result` of the decorated method is passed as the first argument.
    - `error_callback_event(exception, *args, **kwargs)`: (Optional) Called if the decorated
      method raises an exception. It should return a dictionary representing the error event payload.
      The `exception` is passed as the first argument.

    If these methods are implemented, the decorator will call them to generate event payloads.
    If an implementation is missing, the corresponding event publishing will be skipped without error.

    Payloads returned by these methods can include custom metrics by placing them
    under the 'langflow' key within the 'raw_events' dictionary.

    Example:
        class MyClass:
            display_name = "My Observable Class"

            def before_callback_event(self, *args, **kwargs):
                return {"event_name": "my_method_started", "data": {"input_args": args}}

            async def my_method(self, event_manager: EventManager, data: str):
                # ... method logic ...
                return "processed_data"

            def after_callback_event(self, result, *args, **kwargs):
                return {"event_name": "my_method_completed", "data": {"output": result}}

            def error_callback_event(self, exception, *args, **kwargs):
                return {"event_name": "my_method_failed", "error": str(exception)}

        @observable
        async def my_observable_method(self, event_manager: EventManager, data: str):
            # ... method logic ...
            pass
    """

    async def check_event_manager(self, **kwargs):
        if "event_manager" not in kwargs or kwargs["event_manager"] is None:
            await logger.awarning(
                f"EventManager not available/provided, skipping observable event publishing "
                f"from {self.__class__.__name__}"
            )
            return False
        return True

    async def before_callback(self, *args, **kwargs):
        if not await check_event_manager(self, **kwargs):
            return

        if hasattr(self, "before_callback_event"):
            event_payload = self.before_callback_event(*args, **kwargs)
            event_payload = encoder.encode(event_payload)
            # TODO: Publish event per request, would required context based queues
        else:
            await logger.awarning(
                f"before_callback_event not implemented for {self.__class__.__name__}. Skipping event publishing."
            )

    async def after_callback(self, res: Any | None = None, *args, **kwargs):
        if not await check_event_manager(self, **kwargs):
            return
        if hasattr(self, "after_callback_event"):
            event_payload = self.after_callback_event(res, *args, **kwargs)
            event_payload = encoder.encode(event_payload)
            # TODO: Publish event per request, would required context based queues
        else:
            await logger.awarning(
                f"after_callback_event not implemented for {self.__class__.__name__}. Skipping event publishing."
            )

    @functools.wraps(observed_method)
    async def wrapper(self, *args, **kwargs):
        await before_callback(self, *args, **kwargs)
        result = None
        try:
            result = await observed_method(self, *args, **kwargs)
            await after_callback(self, result, *args, **kwargs)
        except Exception as e:
            await logger.aerror(f"Exception in {self.__class__.__name__}: {e}")
            if hasattr(self, "error_callback_event"):
                try:
                    event_payload = self.error_callback_event(e, *args, **kwargs)
                    event_payload = encoder.encode(event_payload)
                    # TODO: Publish event per request, would required context based queues
                except Exception as callback_e:  # noqa: BLE001
                    await logger.aerror(
                        f"Exception during error_callback_event for {self.__class__.__name__}: {callback_e}"
                    )
            raise
        return result

    return wrapper
