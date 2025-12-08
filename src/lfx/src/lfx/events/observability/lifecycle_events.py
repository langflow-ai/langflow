import functools
from lfx.events.event_manager import EventManager
from typing import Callable, Awaitable
from ag_ui.encoder import EventEncoder
from lfx.log.logger import logger

from typing import Any

AsyncMethod = Callable[..., Awaitable[Any]]

def observable(observed_method: AsyncMethod) -> AsyncMethod:
    """
    Make an async method emit lifecycle events by invoking optional callback hooks on the hosting instance.
    
    The hosting class may implement the following optional hooks to produce event payloads:
    - before_callback_event(*args, **kwargs) -> dict: called before the decorated method runs.
    - after_callback_event(result, *args, **kwargs) -> dict: called after the decorated method completes successfully.
    - error_callback_event(exception, *args, **kwargs) -> dict: called if the decorated method raises an exception.
    
    If a hook is implemented, its returned dictionary will be encoded via EventEncoder and prepared for publishing; if a hook is absent, the corresponding event is skipped. Payloads may include custom metrics under the 'langflow' key inside a 'raw_events' dictionary.
    
    Returns:
        The wrapped async function that preserves the original method's behavior while invoking lifecycle hooks when available.
    """

    async def check_event_manager(self, **kwargs):
        """
        Check whether an EventManager instance is present in the provided keyword arguments.
        
        Parameters:
            kwargs: Expects an 'event_manager' key whose value is the EventManager used for publishing lifecycle events.
        
        Returns:
            `True` if 'event_manager' exists in kwargs and is not None, `False` otherwise.
        """
        if 'event_manager' not in kwargs or kwargs['event_manager'] is None:
            await logger.awarning(
                f"EventManager not available/provided, skipping observable event publishing "
                f"from {self.__class__.__name__}"
            )
            return False
        return True

    async def before_callback(self, *args, **kwargs):
        """
        Invoke the instance's pre-execution lifecycle hook to produce and encode an event payload.
        
        Checks for a valid `event_manager` in `kwargs`; if absent the function returns without action.
        If the hosting instance implements `before_callback_event(*args, **kwargs)`, calls it to obtain a payload,
        encodes the payload with EventEncoder (and prepares it for publishing). If the hook is not implemented,
        logs a warning and skips publishing.
        """
        if not await check_event_manager(self, **kwargs):
            return
        
        if hasattr(self, 'before_callback_event'):
            event_payload = self.before_callback_event(*args, **kwargs)
            encoder = EventEncoder()
            event_payload = encoder.encode(event_payload)
            # TODO: Publish event
        else:
            await logger.awarning(
                f"before_callback_event not implemented for {self.__class__.__name__}. "
                f"Skipping event publishing.")

    async def after_callback(self, res: Any | None = None, *args, **kwargs):    # noqa: ARG002
        """
        Invoke the instance's after_callback_event to produce and encode a post-execution event payload when an EventManager is provided.
        
        Parameters:
            res (Any | None): The result produced by the observed method; forwarded to `after_callback_event`.
            *args: Positional arguments forwarded to `after_callback_event`.
            **kwargs: Keyword arguments forwarded to `after_callback_event`. May include `event_manager` required to publish events; if no valid `event_manager` is present, the function returns without encoding or publishing.
        """
        if not await check_event_manager(self, **kwargs):
            return
        if hasattr(self, 'after_callback_event'):
            event_payload = self.after_callback_event(res, *args, **kwargs)
            encoder = EventEncoder()
            event_payload = encoder.encode(event_payload)
            # TODO: Publish event
        else:
            await logger.awarning(
                f"after_callback_event not implemented for {self.__class__.__name__}. "
                f"Skipping event publishing.")

    @functools.wraps(observed_method)
    async def wrapper(self, *args, **kwargs):    # noqa: ARG002
        """
        Wraps the observed async method to emit lifecycle events before execution, after successful completion, and on error.
        
        Calls the hosting instance's before_callback and after_callback helpers to produce and encode event payloads when available; if an exception occurs, encodes an error payload using the instance's error_callback_event when present, then re-raises the exception.
        
        Returns:
            The value returned by the wrapped observed method.
        
        Raises:
            Exception: Propagates any exception raised by the observed method after encoding the error event (if available).
        """
        await before_callback(self, *args, **kwargs)
        result = None
        try:
            result = await observed_method(self, *args, **kwargs)
            await after_callback(self, result, *args, **kwargs)
        except Exception as e:
            await logger.aerror(f"Exception in {self.__class__.__name__}: {e}")
            if hasattr(self, "error_callback_event"):
                error_payload = self.error_callback_event(e, *args, **kwargs)
                encoder = EventEncoder()
                encoder.encode(error_payload)
                # TODO: Publish error event
            raise
        return result
    return wrapper