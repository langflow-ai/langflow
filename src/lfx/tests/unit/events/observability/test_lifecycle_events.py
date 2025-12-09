import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the actual decorator we want to test
from lfx.events.observability.lifecycle_events import observable


# Mock classes for dependencies
class MockEventManager:
    """Mock for lfx.events.event_manager.EventManager."""

    def __init__(self):
        # We'll use AsyncMock for publish
        """Create a mock event manager with an asynchronous `publish` method.

        Initializes the instance by assigning `self.publish` to an `AsyncMock` so tests can await and assert calls to event publishing.
        """
        self.publish = AsyncMock()


class MockLogger:
    """Mock for lfx.log.logger.logger."""

    def __init__(self):
        """Initialize a mock logger with asynchronous warning and error callables.

        Creates two async-capable attributes used in tests:
        - `awarning`: mock for async warning calls.
        - `aerror`: mock for async error calls.
        """
        self.awarning = AsyncMock()
        self.aerror = AsyncMock()


# --- Pytest Fixtures ---


@pytest.fixture
def mock_dependencies():
    """Create and patch test doubles for the logger, event manager, and event encoder used by lifecycle_events.

    Patches lfx.events.observability.lifecycle_events.logger with a MockLogger instance and patches EventEncoder with a mock class that returns an encoder whose `encode` method returns {"encoded": True, "original_event": payload}. Yields a dictionary containing the prepared mocks:

    Yields:
        dict: A mapping with keys:
            - event_manager: MockEventManager instance used to simulate publishing.
            - logger: MockLogger instance with async warning/error methods.
            - encoder_cls: MagicMock that returns the mock encoder instance when called.
    """
    # 1. Logger Mock
    mock_logger_instance = MockLogger()

    # 2. EventManager Mock
    mock_event_manager = MockEventManager()

    # 3. Encoder Mock - create a mock instance with a mocked encode method
    mock_encoder_instance = MagicMock()
    mock_encoder_instance.encode = MagicMock(side_effect=lambda payload: {"encoded": True, "original_event": payload})

    # Mock the EventEncoder class to return our mock instance
    mock_encoder_cls = MagicMock(return_value=mock_encoder_instance)

    # Patch the actual imports in the lifecycle_events module
    with (
        patch("lfx.events.observability.lifecycle_events.logger", mock_logger_instance),
        patch("lfx.events.observability.lifecycle_events.EventEncoder", mock_encoder_cls),
    ):
        yield {
            "event_manager": mock_event_manager,
            "logger": mock_logger_instance,
            "encoder_cls": mock_encoder_cls,
        }


@pytest.fixture(autouse=True)
def reset_mocks(mock_dependencies):
    """Resets the state of the mocks before each test."""
    # Ensure all mocks are reset before test execution
    mock_dependencies["logger"].awarning.reset_mock()
    mock_dependencies["logger"].aerror.reset_mock()
    mock_dependencies["encoder_cls"].reset_mock()
    mock_dependencies["event_manager"].publish.reset_mock()


# --- Test Classes (remain largely the same, but now used by pytest functions) ---


class TestClassWithCallbacks:
    display_name = "ObservableTest"

    def before_callback_event(self, *args, **kwargs):
        """Builds a payload describing a "start" lifecycle event for the observable method.

        Parameters:
            *args: Positional arguments passed to the observable method.
            **kwargs: Keyword arguments passed to the observable method.

        Returns:
            dict: Payload with keys:
                - "lifecycle": "start"
                - "args_len": number of positional arguments
                - "kw_keys": list of keyword argument names
        """
        return {"lifecycle": "start", "args_len": len(args), "kw_keys": list(kwargs.keys())}

    def after_callback_event(self, result: Any, *args, **kwargs):  # noqa: ARG002
        """Create the "end" lifecycle event payload containing the method result and the names of keyword arguments.

        Parameters:
            result: The value returned by the wrapped method.
            *args: Positional arguments passed to the wrapped method (ignored in payload).
            **kwargs: Keyword arguments passed to the wrapped method; their keys are recorded.

        Returns:
            dict: Payload with keys:
                - "lifecycle": "end"
                - "result": the provided `result`
                - "kw_keys": list of keyword argument names from `kwargs`
        """
        return {"lifecycle": "end", "result": result, "kw_keys": list(kwargs.keys())}

    def error_callback_event(self, exception: Exception, *args, **kwargs):  # noqa: ARG002
        """Builds an "error" lifecycle payload from an exception and the provided keyword arguments.

        Parameters:
            exception (Exception): The exception to extract message and type from.
            *args: Ignored positional arguments.
            **kwargs: Keyword arguments whose keys will be included in the payload.

        Returns:
            dict: Payload with keys:
                - `lifecycle`: the string "error".
                - `error`: the exception message (string).
                - `error_type`: the exception class name (string).
                - `kw_keys`: list of keys from `kwargs`.
        """
        return {
            "lifecycle": "error",
            "error": str(exception),
            "error_type": type(exception).__name__,
            "kw_keys": list(kwargs.keys()),
        }

    # Mock observable method
    @observable
    async def run_success(self, event_manager: MockEventManager, data: str) -> str:  # noqa: ARG002
        """Process input data and return it prefixed with "Processed:".

        Returns:
            result (str): The input `data` formatted as "Processed:{data}".
        """
        await asyncio.sleep(0.001)
        return f"Processed:{data}"

    @observable
    async def run_exception(self, event_manager: MockEventManager, data: str) -> str:  # noqa: ARG002
        """Test helper that sleeps briefly then raises a ValueError.

        Raises:
            ValueError: Always raised after the brief delay.
        """
        await asyncio.sleep(0.001)
        raise ValueError


class TestClassWithoutCallbacks:
    display_name = "NonObservableTest"

    @observable
    async def run_success(self, event_manager: MockEventManager, data: str) -> str:  # noqa: ARG002
        """Process input data and return it prefixed with "Processed:".

        Returns:
            result (str): The input `data` formatted as "Processed:{data}".
        """
        await asyncio.sleep(0.001)
        return f"Processed:{data}"


# --- Pytest Test Functions ---


# Use pytest.mark.asyncio for running async functions
@pytest.mark.asyncio
async def test_successful_run_with_callbacks(mock_dependencies):
    instance = TestClassWithCallbacks()
    data = "test_data"

    event_manager = mock_dependencies["event_manager"]

    result = await instance.run_success(event_manager=event_manager, data=data)

    # 1. Assert result
    assert result == f"Processed:{data}"

    # 2. Assert encoder was called twice (once for BEFORE, once for AFTER)
    assert mock_dependencies["encoder_cls"].call_count == 2

    # 3. Verify the encoder was called with the correct payloads
    encoder_instance = mock_dependencies["encoder_cls"].return_value
    assert encoder_instance.encode.call_count == 2

    # Get the actual calls to encode
    encode_calls = encoder_instance.encode.call_args_list

    # First call should be the BEFORE event
    before_payload = encode_calls[0][0][0]
    assert before_payload["lifecycle"] == "start"
    assert before_payload["args_len"] == 0
    assert "event_manager" in before_payload["kw_keys"]
    assert "data" in before_payload["kw_keys"]

    # Second call should be the AFTER event
    after_payload = encode_calls[1][0][0]
    assert after_payload["lifecycle"] == "end"
    assert after_payload["result"] == f"Processed:{data}"
    assert "event_manager" in after_payload["kw_keys"]
    assert "data" in after_payload["kw_keys"]

    # 4. Assert no warnings or errors were logged
    mock_dependencies["logger"].awarning.assert_not_called()
    mock_dependencies["logger"].aerror.assert_not_called()


@pytest.mark.asyncio
async def test_exception_run_with_callbacks(mock_dependencies):
    instance = TestClassWithCallbacks()

    event_manager = mock_dependencies["event_manager"]

    # The decorator now re-raises the exception after logging and encoding the error event
    with pytest.raises(ValueError):
        await instance.run_exception(event_manager=event_manager, data="fail_data")

    # 1. Assert error was logged
    mock_dependencies["logger"].aerror.assert_called_once()
    mock_dependencies["logger"].aerror.assert_called_with("Exception in TestClassWithCallbacks: ")

    # 2. Assert encoder was called twice (once for BEFORE event, once for ERROR event)
    assert mock_dependencies["encoder_cls"].call_count == 2

    # 3. Verify the encoder was called with the correct payloads
    encoder_instance = mock_dependencies["encoder_cls"].return_value
    assert encoder_instance.encode.call_count == 2

    # Get the actual calls to encode
    encode_calls = encoder_instance.encode.call_args_list

    # First call should be the BEFORE event
    before_payload = encode_calls[0][0][0]
    assert before_payload["lifecycle"] == "start"

    # Second call should be the ERROR event
    error_payload = encode_calls[1][0][0]
    assert error_payload["lifecycle"] == "error"
    assert error_payload["error"] == ""
    assert error_payload["error_type"] == "ValueError"

    # 4. Assert no warnings were logged
    mock_dependencies["logger"].awarning.assert_not_called()


@pytest.mark.asyncio
async def test_run_without_event_manager(mock_dependencies):
    """Run TestClassWithCallbacks.run_success with no EventManager and verify behavior.

    Parameters:
        mock_dependencies (dict): Fixture-provided mocks including 'logger', 'event_manager', and 'encoder_cls'.

    Details:
        - Calls run_success with event_manager set to None and verifies the method returns the expected processed string.
        - Verifies the logger.awarning was called twice with a message indicating the EventManager is not available.
    """
    instance = TestClassWithCallbacks()
    data = "no_manager"

    # No event_manager passed (or explicitly passed as None)
    result = await instance.run_success(event_manager=None, data=data)

    # 1. Assert result is correct
    assert result == f"Processed:{data}"

    # 2. Assert warning for missing EventManager was logged twice (once for before, once for after)
    assert mock_dependencies["logger"].awarning.call_count == 2
    mock_dependencies["logger"].awarning.assert_any_call(
        "EventManager not available/provided, skipping observable event publishing from TestClassWithCallbacks"
    )


@pytest.mark.asyncio
async def test_run_without_callbacks(mock_dependencies):
    """Verify behavior when an observable-decorated method is called on a class that does not implement lifecycle callbacks.

    Checks that the method returns its expected result, that two warning messages are logged for the missing `before_callback_event` and `after_callback_event` callbacks, and that no error logs are emitted.
    """
    instance = TestClassWithoutCallbacks()
    data = "no_callbacks"

    event_manager = mock_dependencies["event_manager"]

    # Run the method with a manager
    result = await instance.run_success(event_manager=event_manager, data=data)

    # 1. Assert result is correct
    assert result == f"Processed:{data}"

    # 2. Assert warnings for missing callbacks were logged
    assert mock_dependencies["logger"].awarning.call_count == 2
    mock_dependencies["logger"].awarning.assert_any_call(
        "before_callback_event not implemented for TestClassWithoutCallbacks. Skipping event publishing."
    )
    mock_dependencies["logger"].awarning.assert_any_call(
        "after_callback_event not implemented for TestClassWithoutCallbacks. Skipping event publishing."
    )

    # 3. Assert no errors were logged
    mock_dependencies["logger"].aerror.assert_not_called()
