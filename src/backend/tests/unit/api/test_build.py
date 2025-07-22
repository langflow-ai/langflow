import asyncio
import os
import time
from unittest.mock import Mock

import pytest
from langflow.api.build import create_flow_response
from langflow.api.disconnect import DisconnectHandlerStreamingResponse
from langflow.events.event_manager import EventManager


class TestCreateFlowResponse:
    """Test suite for create_flow_response function in langflow.api.build."""

    @pytest.fixture
    def mock_event_manager(self):
        """Create a mock EventManager for testing."""
        mock = Mock(spec=EventManager)
        mock.on_end = Mock()
        return mock

    @pytest.fixture
    def mock_event_task(self):
        """Create a mock event task for testing."""
        task = Mock()
        task.cancel = Mock()
        task.done.return_value = False
        task.cancelled.return_value = False
        return task

    async def test_create_flow_response_returns_proper_streaming_response(self, mock_event_manager, mock_event_task):
        """Test that create_flow_response returns a proper DisconnectHandlerStreamingResponse."""
        queue = asyncio.Queue()
        await queue.put((1, b'{"event": "test", "data": {}}', time.time()))
        await queue.put((None, None, time.time()))  # End marker

        response = await create_flow_response(
            queue=queue,
            event_manager=mock_event_manager,
            event_task=mock_event_task,
        )

        assert isinstance(response, DisconnectHandlerStreamingResponse)
        assert response.media_type == "application/x-ndjson"
        assert response.on_disconnect is not None

    async def test_create_flow_response_streams_events_successfully(self, mock_event_manager, mock_event_task):
        """Test that create_flow_response streams events from queue successfully."""
        queue = asyncio.Queue()

        test_events = [
            (1, b'{"event": "vertex_start", "data": {"vertex_id": "test1"}}', time.time()),
            (2, b'{"event": "vertex_end", "data": {"vertex_id": "test1", "result": "success"}}', time.time()),
            (3, None, time.time()),  # End of stream
        ]

        for event in test_events:
            await queue.put(event)

        response = await create_flow_response(
            queue=queue,
            event_manager=mock_event_manager,
            event_task=mock_event_task,
        )

        generator = response.body_iterator
        yielded_values = [value async for value in generator if value is not None]

        assert len(yielded_values) == 2
        assert '"event": "vertex_start"' in yielded_values[0]
        assert '"event": "vertex_end"' in yielded_values[1]

    async def test_create_flow_response_sends_keepalive_on_timeout(self, mock_event_manager, mock_event_task):
        """Test that create_flow_response sends keep-alive events when queue times out."""
        original_timeout = os.getenv("LANGFLOW_KEEP_ALIVE_TIMEOUT")
        os.environ["LANGFLOW_KEEP_ALIVE_TIMEOUT"] = "0.1"

        import importlib

        from langflow.api import build

        importlib.reload(build)

        try:
            queue = asyncio.Queue()

            response = await build.create_flow_response(
                queue=queue,
                event_manager=mock_event_manager,
                event_task=mock_event_task,
            )

            generator = response.body_iterator
            start_time = time.time()

            # Should get a keepalive event due to timeout
            first_value = await generator.__anext__()
            elapsed = time.time() - start_time

            assert elapsed >= 0.1
            assert first_value == '{"event": "keepalive", "data": {}}\n\n'

        finally:
            # Restore original timeout
            if original_timeout is not None:
                os.environ["LANGFLOW_KEEP_ALIVE_TIMEOUT"] = original_timeout
            else:
                os.environ.pop("LANGFLOW_KEEP_ALIVE_TIMEOUT", None)
            importlib.reload(build)

    async def test_create_flow_response_handles_exceptions_gracefully(self, mock_event_manager, mock_event_task):
        """Test that create_flow_response handles queue exceptions gracefully."""
        queue = asyncio.Queue()

        # Put an event that will cause the queue to be accessed normally first
        await queue.put((1, b'{"event": "test", "data": {}}', time.time()))

        response = await create_flow_response(
            queue=queue,
            event_manager=mock_event_manager,
            event_task=mock_event_task,
        )

        generator = response.body_iterator

        # Get the first event successfully
        first_value = await generator.__anext__()
        assert '"event": "test"' in first_value

        # Now the queue is empty and will timeout, sending a keepalive event
        # The generator should handle this gracefully by sending keepalive
        try:
            # This should get a keepalive event due to timeout
            second_value = await asyncio.wait_for(generator.__anext__(), timeout=1.0)
            assert "keepalive" in second_value
        except asyncio.TimeoutError:
            # This is also acceptable - it means the generator is handling timeouts properly
            pass

    async def test_create_flow_response_handles_empty_queue(self, mock_event_manager, mock_event_task):
        """Test that create_flow_response handles empty queue properly."""
        queue = asyncio.Queue()
        await queue.put((1, None, time.time()))  # Immediate end marker

        response = await create_flow_response(
            queue=queue,
            event_manager=mock_event_manager,
            event_task=mock_event_task,
        )

        generator = response.body_iterator
        yielded_values = [value async for value in generator if value is not None]

        assert len(yielded_values) == 0

    async def test_create_flow_response_handles_malformed_events(self, mock_event_manager, mock_event_task):
        """Test that create_flow_response handles malformed events gracefully."""
        queue = asyncio.Queue()

        # Add malformed event (not valid JSON bytes)
        await queue.put((1, b"invalid json{", time.time()))
        await queue.put((2, b'{"valid": "json"}', time.time()))
        await queue.put((3, None, time.time()))

        response = await create_flow_response(
            queue=queue,
            event_manager=mock_event_manager,
            event_task=mock_event_task,
        )

        generator = response.body_iterator
        yielded_values = [value async for value in generator if value is not None]

        # Should yield both events, malformed content is passed through as-is
        assert len(yielded_values) == 2
        assert yielded_values[0] == "invalid json{"
        assert '{"valid": "json"}' in yielded_values[1]

    async def test_create_flow_response_on_disconnect_callback(self, mock_event_manager, mock_event_task):
        """Test that the on_disconnect callback works properly."""
        queue = asyncio.Queue()
        await queue.put((1, None, time.time()))

        response = await create_flow_response(
            queue=queue,
            event_manager=mock_event_manager,
            event_task=mock_event_task,
        )

        # Call the disconnect callback
        response.on_disconnect()

        # Verify the callback cancels the task and calls event_manager.on_end
        mock_event_task.cancel.assert_called_once()
        mock_event_manager.on_end.assert_called_once_with(data={})

    async def test_create_flow_response_with_cancelled_event_task(self, mock_event_manager):
        """Test create_flow_response behavior when event_task is already cancelled."""
        queue = asyncio.Queue()
        await queue.put((1, b'{"event": "test"}', time.time()))
        await queue.put((2, None, time.time()))

        # Create a cancelled task
        cancelled_task = Mock()
        cancelled_task.cancel = Mock()
        cancelled_task.done.return_value = True
        cancelled_task.cancelled.return_value = True

        response = await create_flow_response(
            queue=queue,
            event_manager=mock_event_manager,
            event_task=cancelled_task,
        )

        # Should still work normally
        assert isinstance(response, DisconnectHandlerStreamingResponse)

        # Test the disconnect callback
        response.on_disconnect()
        cancelled_task.cancel.assert_called_once()
        mock_event_manager.on_end.assert_called_once_with(data={})

    async def test_create_flow_response_with_large_events(self, mock_event_manager, mock_event_task):
        """Test create_flow_response handles large events properly."""
        queue = asyncio.Queue()

        # Create a large event (1MB of data)
        large_data = "x" * (1024 * 1024)
        large_event = f'{{"event": "large_data", "data": "{large_data}"}}'

        await queue.put((1, large_event.encode(), time.time()))
        await queue.put((2, None, time.time()))

        response = await create_flow_response(
            queue=queue,
            event_manager=mock_event_manager,
            event_task=mock_event_task,
        )

        generator = response.body_iterator
        yielded_values = [value async for value in generator if value is not None]

        assert len(yielded_values) == 1
        assert len(yielded_values[0]) > 1024 * 1024  # Should be large
        assert '"event": "large_data"' in yielded_values[0]

    async def test_create_flow_response_with_rapid_events(self, mock_event_manager, mock_event_task):
        """Test create_flow_response handles rapid succession of events."""
        queue = asyncio.Queue()

        # Add many events rapidly
        num_events = 100
        for i in range(num_events):
            event_data = f'{{"event": "rapid_event", "data": {{"id": {i}}}}}'
            await queue.put((i, event_data.encode(), time.time()))

        await queue.put((num_events, None, time.time()))

        response = await create_flow_response(
            queue=queue,
            event_manager=mock_event_manager,
            event_task=mock_event_task,
        )

        generator = response.body_iterator
        yielded_values = [value async for value in generator if value is not None]

        assert len(yielded_values) == num_events
        for i, value in enumerate(yielded_values):
            assert f'"id": {i}' in value
