import pytest
import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Import the actual decorator we want to test
from lfx.events.observability.lifecycle_events import observable

# Mock classes for dependencies
class MockEventManager:
    """Mock for lfx.events.event_manager.EventManager."""
    def __init__(self):
        # We'll use AsyncMock for publish
        """
        Initialize the mock event manager with an asynchronous `publish` method.
        
        Sets `self.publish` to an AsyncMock so tests can await and assert calls to the publish coroutine.
        """
        self.publish = AsyncMock()

class MockLogger:
    """Mock for lfx.log.logger.logger."""
    def __init__(self):
        """
        Create a mock logger exposing awaitable `awarning` and `aerror` callables.
        
        The constructor initializes `awarning` and `aerror` as AsyncMock instances that can be awaited like asynchronous warning and error logging methods.
        """
        self.awarning = AsyncMock()
        self.aerror = AsyncMock()

# --- Pytest Fixtures ---

@pytest.fixture
def mock_dependencies():
    """
    Create and patch mocked external dependencies for tests.
    
    Yields:
        dict: A mapping with keys:
            - "event_manager": MockEventManager instance used to simulate event publishing.
            - "logger": MockLogger instance with async warning/error helpers.
            - "encoder_cls": A mock EventEncoder class whose instances provide an `encode` method that returns a dict with `encoded` and `original_event` keys.
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
    with patch('lfx.events.observability.lifecycle_events.logger', mock_logger_instance), \
         patch('lfx.events.observability.lifecycle_events.EventEncoder', mock_encoder_cls):
        
        yield {
            "event_manager": mock_event_manager,
            "logger": mock_logger_instance,
            "encoder_cls": mock_encoder_cls,
        }

@pytest.fixture(autouse=True)
def reset_mocks(mock_dependencies):
    """
    Reset mock objects used by tests to a clean state.
    
    Parameters:
        mock_dependencies (dict): Mapping of mocked test dependencies created by the fixture.
            Expected keys:
            - "logger": object with `awarning` and `aerror` AsyncMock attributes.
            - "encoder_cls": mock class whose instantiation should be reset.
            - "event_manager": object with `publish` AsyncMock attribute.
    """
    # Ensure all mocks are reset before test execution
    mock_dependencies["logger"].awarning.reset_mock()
    mock_dependencies["logger"].aerror.reset_mock()
    mock_dependencies["encoder_cls"].reset_mock()
    mock_dependencies["event_manager"].publish.reset_mock()


# --- Test Classes (remain largely the same, but now used by pytest functions) ---

class TestClassWithCallbacks:
    display_name = "ObservableTest"
    
    def before_callback_event(self, *args, **kwargs):
        """
        Construct the payload for a 'start' lifecycle observable event.
        
        Parameters:
            *args: Positional arguments passed to the observed method; only the count is used.
            **kwargs: Keyword arguments passed to the observed method; only the set of keys is used.
        
        Returns:
            dict: Payload containing:
                - `lifecycle` (str): fixed value "start".
                - `args_len` (int): number of positional arguments.
                - `kw_keys` (list[str]): list of keyword argument names.
        """
        return {"lifecycle": "start", "args_len": len(args), "kw_keys": list(kwargs.keys())}
    
    def after_callback_event(self, result: Any, *args, **kwargs):   # noqa: ARG002
        """
        Produce an event payload for the post-execution lifecycle including the call result and the names of keyword arguments.
        
        Parameters:
            result: The value returned by the observed function.
            *args: Positional arguments passed to the observed function (ignored).
            **kwargs: Keyword arguments passed to the observed function; their keys are captured.
        
        Returns:
            dict: A mapping containing:
                - `lifecycle`: the string `"end"`.
                - `result`: the provided `result` value.
                - `kw_keys`: list of keyword argument names present in `kwargs`.
        """
        return {"lifecycle": "end", "result": result, "kw_keys": list(kwargs.keys())}
    
    def error_callback_event(self, exception: Exception, *args, **kwargs): # noqa: ARG002
        """
        Builds an error lifecycle payload describing an exception.
        
        Parameters:
            exception (Exception): The exception that occurred.
            *args: Positional arguments passed to the original call (ignored in the payload).
            **kwargs: Keyword arguments passed to the original call; their keys are included in the payload.
        
        Returns:
            dict: A payload with the following keys:
                - `lifecycle`: the string "error".
                - `error`: the exception message (`str(exception)`).
                - `error_type`: the exception class name.
                - `kw_keys`: list of keyword argument names present in `kwargs`.
        """
        return {"lifecycle": "error", "error": str(exception), "error_type": type(exception).__name__, "kw_keys": list(kwargs.keys())}
    
    # Mock observable method
    @observable
    async def run_success(self, event_manager: MockEventManager, data: str) -> str: # noqa: ARG002
        """
        Produce a processed string by prefixing the input with "Processed:".
        
        Parameters:
        	data (str): Input payload to be processed.
        
        Returns:
        	processed (str): The resulting string in the form "Processed:<data>".
        """
        await asyncio.sleep(0.001)
        return f"Processed:{data}"

    @observable
    async def run_exception(self, event_manager: MockEventManager, data: str) -> str: # noqa: ARG002
        """
        Simulates asynchronous work then raises a ValueError to trigger error handling.
        
        Raises:
            ValueError: Always raised to simulate a failure during execution.
        """
        await asyncio.sleep(0.001)
        err_msg = 'Simulated failure'
        raise ValueError()

class TestClassWithoutCallbacks:
    display_name = "NonObservableTest"
    
    @observable
    async def run_success(self, event_manager: MockEventManager, data: str) -> str: # noqa: ARG002
        """
        Produce a processed string by prefixing the input with "Processed:".
        
        Parameters:
        	data (str): Input payload to be processed.
        
        Returns:
        	processed (str): The resulting string in the form "Processed:<data>".
        """
        await asyncio.sleep(0.001)
        return f"Processed:{data}"

# --- Pytest Test Functions ---

# Use pytest.mark.asyncio for running async functions
@pytest.mark.asyncio
async def test_successful_run_with_callbacks(mock_dependencies):
    """
    Verify that when an observable-decorated method with lifecycle callbacks completes successfully, the encoder is invoked for BOTH the BEFORE and AFTER events with correct payloads and no warnings/errors are logged.
    
    Parameters:
        mock_dependencies (dict): Fixture providing mocks: `logger` (with `awarning`/`aerror`), `event_manager`, `encoder_cls` (mocked encoder class whose `return_value` is the encoder instance with an `encode` method).
    
    """
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
    assert before_payload['lifecycle'] == 'start'
    assert before_payload['args_len'] == 0
    assert 'event_manager' in before_payload['kw_keys']
    assert 'data' in before_payload['kw_keys']
    
    # Second call should be the AFTER event
    after_payload = encode_calls[1][0][0]
    assert after_payload['lifecycle'] == 'end'
    assert after_payload['result'] == f"Processed:{data}"
    assert 'event_manager' in after_payload['kw_keys']
    assert 'data' in after_payload['kw_keys']
    
    # 4. Assert no warnings or errors were logged
    mock_dependencies["logger"].awarning.assert_not_called()
    mock_dependencies["logger"].aerror.assert_not_called()

@pytest.mark.asyncio
async def test_exception_run_with_callbacks(mock_dependencies):
    """
    Verify that when an observable-wrapped method raises an exception, the decorator logs the error, encodes both the start and error lifecycle events, and re-raises the exception.
    
    Asserts:
    - A ValueError is raised by the wrapped method.
    - logger.aerror was called once with the message "Exception in TestClassWithCallbacks: ".
    - The EventEncoder class was instantiated twice and its instance `encode` was called twice.
    - The first encoded payload has `lifecycle` == 'start'.
    - The second encoded payload has `lifecycle` == 'error', `error` == '', and `error_type` == 'ValueError'.
    - No warning logs were emitted via logger.awarning.
    
    Parameters:
        mock_dependencies (dict): Fixture-provided mocks; expected keys include "logger", "event_manager", and "encoder_cls".
    """
    instance = TestClassWithCallbacks()
    
    event_manager = mock_dependencies["event_manager"]
    
    # The decorator now re-raises the exception after logging and encoding the error event
    with pytest.raises(ValueError, match=""):
        await instance.run_exception(event_manager=event_manager, data="fail_data")
    
    # 1. Assert error was logged
    mock_dependencies["logger"].aerror.assert_called_once()
    mock_dependencies["logger"].aerror.assert_called_with(
        "Exception in TestClassWithCallbacks: "
    )
    
    # 2. Assert encoder was called twice (once for BEFORE event, once for ERROR event)
    assert mock_dependencies["encoder_cls"].call_count == 2
    
    # 3. Verify the encoder was called with the correct payloads
    encoder_instance = mock_dependencies["encoder_cls"].return_value
    assert encoder_instance.encode.call_count == 2
    
    # Get the actual calls to encode
    encode_calls = encoder_instance.encode.call_args_list
    
    # First call should be the BEFORE event
    before_payload = encode_calls[0][0][0]
    assert before_payload['lifecycle'] == 'start'
    
    # Second call should be the ERROR event
    error_payload = encode_calls[1][0][0]
    assert error_payload['lifecycle'] == 'error'
    assert error_payload['error'] == ''
    assert error_payload['error_type'] == 'ValueError'
    
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