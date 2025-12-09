import functools
from collections.abc import Awaitable, Callable
from typing import Any

from ag_ui.encoder import EventEncoder

from lfx.log.logger import logger

AsyncMethod = Callable[..., Awaitable[Any]]


def observable(observed_method: AsyncMethod) -> AsyncMethod:
    """Make an async method emit lifecycle events by invoking optional lifecycle hooks on its host before execution, after successful completion, and on exceptions.

    If implemented on the host object, the following hooks will be called to produce event payloads:
    - before_callback_event(*args, **kwargs): called before the observed method executes.
    - after_callback_event(result, *args, **kwargs): called after the observed method completes successfully; receives the method result as the first argument.
    - error_callback_event(exception, *args, **kwargs): called if the observed method raises an exception; receives the exception as the first argument.

    Event publishing is skipped if an "event_manager" keyword argument is not provided or is None. Payloads produced by the hooks are encoded with EventEncoder; payloads may include custom metrics under the 'langflow' key within 'raw_events'. Missing hook implementations are ignored (no error).

    Returns:
        A wrapper async function that preserves the original method's metadata, invokes the described lifecycle hooks at the appropriate times, and returns the original method's result.
    """

    async def check_event_manager(self, **kwargs):
        """Verify that an EventManager is provided in the call's keyword arguments.

        Parameters:
            **kwargs: Keyword arguments from the observed method call; expected to include an `event_manager` entry.

        Returns:
            bool: `true` if an `event_manager` keyword with a non-None value is present, `false` otherwise.

        Notes:
            Logs a warning when the `event_manager` is missing or None.
        """
        if "event_manager" not in kwargs or kwargs["event_manager"] is None:
            await logger.awarning(
                f"EventManager not available/provided, skipping observable event publishing "
                f"from {self.__class__.__name__}"
            )
            return False
        return True

    async def before_callback(self, *args, **kwargs):
        """Invoke the instance's `before_callback_event` hook (if implemented), encode its returned payload, and prepare it for publishing.

        Checks that a non-None `event_manager` is present in `kwargs` before proceeding; if absent, the function logs a warning and returns without action. If `before_callback_event` exists on the instance, calls it with `*args` and `**kwargs`, encodes the resulting payload with `EventEncoder`, and leaves the payload ready to be published (publishing is not implemented here). If the hook is not implemented, logs a warning and skips publishing.

        Parameters:
            *args: Positional arguments forwarded to `before_callback_event`.
            **kwargs: Keyword arguments forwarded to `before_callback_event` (must include `event_manager` to enable publishing).
        """
        if not await check_event_manager(self, **kwargs):
            return

        if hasattr(self, "before_callback_event"):
            event_payload = self.before_callback_event(*args, **kwargs)
            encoder = EventEncoder()
            event_payload = encoder.encode(event_payload)
            # TODO: Publish event
        else:
            await logger.awarning(
                f"before_callback_event not implemented for {self.__class__.__name__}. Skipping event publishing."
            )

    async def after_callback(self, res: Any | None = None, *args, **kwargs):
        """Handle the post-execution lifecycle event by encoding and publishing the payload produced by the host's `after_callback_event` hook.

        If an `event_manager` is not present in kwargs, the function does nothing. If the hosting object defines `after_callback_event`, that hook is called with the method result and any forwarded arguments; its returned payload is encoded via EventEncoder and prepared for publishing (actual publish is TODO). If `after_callback_event` is not implemented, a warning is logged and no event is published.

        Parameters:
            res (Any | None): The result returned by the observed method; may be None.
            *args: Positional arguments forwarded to the host's `after_callback_event` hook.
            **kwargs: Keyword arguments forwarded to the host's `after_callback_event` hook; used to locate `event_manager`.
        """
        if not await check_event_manager(self, **kwargs):
            return
        if hasattr(self, "after_callback_event"):
            event_payload = self.after_callback_event(res, *args, **kwargs)
            encoder = EventEncoder()
            event_payload = encoder.encode(event_payload)
            # TODO: Publish event
        else:
            await logger.awarning(
                f"after_callback_event not implemented for {self.__class__.__name__}. Skipping event publishing."
            )

    @functools.wraps(observed_method)
    async def wrapper(self, *args, **kwargs):
        """Wraps the original async method to emit lifecycle events before execution, after successful completion, and on error.

        The wrapper calls a before callback (if implemented) prior to invoking the original method, an after callback (if implemented) after a successful call, and an error callback (if implemented) when the wrapped method raises. Event payloads produced by these callbacks are encoded via EventEncoder; publishing is performed elsewhere.

        Parameters:
            *args: Positional arguments forwarded to the before/after/error callbacks and the wrapped method.
            **kwargs: Keyword arguments forwarded to the before/after/error callbacks and the wrapped method.

        Returns:
            The result returned by the wrapped async method.

        Raises:
            Exception: Re-raises any exception thrown by the wrapped method after attempting to handle and encode an error event.
        """
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
                    encoder = EventEncoder()
                    event_payload = encoder.encode(event_payload)
                    # TODO: Publish error event
                except Exception as callback_e:
                    await logger.aerror(
                        f"Exception during error_callback_event for {self.__class__.__name__}: {callback_e}"
                    )
            raise e
        return result

    return wrapper
