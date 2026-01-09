import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ag_ui.core import CustomEvent, StepFinishedEvent, StepStartedEvent

# Import the actual decorator we want to test
from lfx.events.observability.lifecycle_events import observable


# Mock classes for dependencies
class MockEventManager:
    """Mock for lfx.events.event_manager.EventManager."""

    def __init__(self):
        # We'll use AsyncMock for publish
        self.publish = AsyncMock()


class MockLogger:
    """Mock for lfx.log.logger.logger."""

    def __init__(self):
        self.awarning = AsyncMock()
        self.aerror = AsyncMock()


# --- Pytest Fixtures ---


@pytest.fixture
def mock_dependencies():
    """Provides mocked instances of external dependencies and patches them."""
    # 1. Logger Mock
    mock_logger_instance = MockLogger()

    # 2. EventManager Mock
    mock_event_manager = MockEventManager()

    # 3. Encoder Mock - create a mock instance with a mocked encode method
    mock_encoder_instance = MagicMock()
    # The encode method should return a string (SSE format)
    mock_encoder_instance.encode = MagicMock(side_effect=lambda payload: f"data: {payload}\n\n")

    # Patch the actual imports in the lifecycle_events module
    with (
        patch("lfx.events.observability.lifecycle_events.logger", mock_logger_instance),
        patch("lfx.events.observability.lifecycle_events.encoder", mock_encoder_instance),
    ):
        yield {
            "event_manager": mock_event_manager,
            "logger": mock_logger_instance,
            "encoder": mock_encoder_instance,
        }


@pytest.fixture(autouse=True)
def reset_mocks(mock_dependencies):
    """Resets the state of the mocks before each test."""
    # Ensure all mocks are reset before test execution
    mock_dependencies["logger"].awarning.reset_mock()
    mock_dependencies["logger"].aerror.reset_mock()
    mock_dependencies["encoder"].encode.reset_mock()


# --- Test Classes (remain largely the same, but now used by pytest functions) ---


class TestClassWithCallbacks:
    display_name = "ObservableTest"

    def before_callback_event(self, *args, **kwargs):
        return StepStartedEvent(
            step_name=self.display_name,
            raw_event={"lifecycle": "start", "args_len": len(args), "kw_keys": list(kwargs.keys())},
        )

    def after_callback_event(self, result: Any, *args, **kwargs):  # noqa: ARG002
        return StepFinishedEvent(
            step_name=self.display_name,
            raw_event={"lifecycle": "end", "result": result, "kw_keys": list(kwargs.keys())},
        )

    def error_callback_event(self, exception: Exception, *args, **kwargs):  # noqa: ARG002
        return CustomEvent(
            name="error",
            value={
                "error": str(exception),
                "error_type": type(exception).__name__,
            },
            raw_event={"lifecycle": "error", "kw_keys": list(kwargs.keys())},
        )

    # Mock observable method
    @observable
    async def run_success(self, event_manager: MockEventManager, data: str) -> str:  # noqa: ARG002
        await asyncio.sleep(0.001)
        return f"Processed:{data}"

    @observable
    async def run_exception(self, event_manager: MockEventManager, data: str) -> str:  # noqa: ARG002
        await asyncio.sleep(0.001)
        raise ValueError


class TestClassWithoutCallbacks:
    display_name = "NonObservableTest"

    @observable
    async def run_success(self, event_manager: MockEventManager, data: str) -> str:  # noqa: ARG002
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
    assert mock_dependencies["encoder"].encode.call_count == 2

    # 3. Verify the encoder was called with the correct payloads
    encoder_instance = mock_dependencies["encoder"]
    assert encoder_instance.encode.call_count == 2

    # Get the actual calls to encode
    encode_calls = encoder_instance.encode.call_args_list

    # First call should be the BEFORE event (StepStartedEvent)
    before_event = encode_calls[0][0][0]
    assert isinstance(before_event, StepStartedEvent)
    assert before_event.step_name == "ObservableTest"
    assert before_event.raw_event["lifecycle"] == "start"
    assert before_event.raw_event["args_len"] == 0
    assert "event_manager" in before_event.raw_event["kw_keys"]
    assert "data" in before_event.raw_event["kw_keys"]

    # Second call should be the AFTER event (StepFinishedEvent)
    after_event = encode_calls[1][0][0]
    assert isinstance(after_event, StepFinishedEvent)
    assert after_event.step_name == "ObservableTest"
    assert after_event.raw_event["lifecycle"] == "end"
    assert after_event.raw_event["result"] == f"Processed:{data}"
    assert "event_manager" in after_event.raw_event["kw_keys"]
    assert "data" in after_event.raw_event["kw_keys"]

    # 4. Assert no warnings or errors were logged
    mock_dependencies["logger"].awarning.assert_not_called()
    mock_dependencies["logger"].aerror.assert_not_called()


@pytest.mark.asyncio
async def test_exception_run_with_callbacks(mock_dependencies):
    instance = TestClassWithCallbacks()

    event_manager = mock_dependencies["event_manager"]

    # The decorator now re-raises the exception after logging and encoding the error event
    with pytest.raises(ValueError):  # noqa: PT011
        await instance.run_exception(event_manager=event_manager, data="fail_data")

    # 1. Assert error was logged
    mock_dependencies["logger"].aerror.assert_called_once()
    mock_dependencies["logger"].aerror.assert_called_with("Exception in TestClassWithCallbacks: ")

    # 2. Assert encoder was called twice (once for BEFORE event, once for ERROR event)
    assert mock_dependencies["encoder"].encode.call_count == 2

    # 3. Verify the encoder was called with the correct payloads
    encoder_instance = mock_dependencies["encoder"]
    assert encoder_instance.encode.call_count == 2

    # Get the actual calls to encode
    encode_calls = encoder_instance.encode.call_args_list

    # First call should be the BEFORE event (StepStartedEvent)
    before_event = encode_calls[0][0][0]
    assert isinstance(before_event, StepStartedEvent)
    assert before_event.raw_event["lifecycle"] == "start"

    # Second call should be the ERROR event (CustomEvent)
    error_event = encode_calls[1][0][0]
    assert isinstance(error_event, CustomEvent)
    assert error_event.name == "error"
    assert error_event.value["error"] == ""
    assert error_event.value["error_type"] == "ValueError"
    assert error_event.raw_event["lifecycle"] == "error"

    # 4. Assert no warnings were logged
    mock_dependencies["logger"].awarning.assert_not_called()


@pytest.mark.asyncio
async def test_run_without_event_manager(mock_dependencies):
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
