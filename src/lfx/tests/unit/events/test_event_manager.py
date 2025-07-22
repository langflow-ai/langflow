"""Unit tests for lfx.events.event_manager module."""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from lfx.events.event_manager import (
    EventManager,
    create_default_event_manager,
    create_stream_tokens_event_manager,
)


class TestEventManager:
    """Test cases for the EventManager class."""

    def test_event_manager_creation(self):
        """Test creating EventManager with queue."""
        queue = asyncio.Queue()
        manager = EventManager(queue)
        assert manager.queue == queue
        assert manager.events == {}

    def test_event_manager_creation_without_queue(self):
        """Test creating EventManager without queue."""
        manager = EventManager(None)
        assert manager.queue is None
        assert manager.events == {}

    def test_register_event_with_default_callback(self):
        """Test registering event with default callback."""
        queue = asyncio.Queue()
        manager = EventManager(queue)

        manager.register_event("on_test", "test_event")
        assert "on_test" in manager.events
        assert callable(manager.events["on_test"])

    def test_register_event_with_custom_callback(self):
        """Test registering event with custom callback."""
        queue = asyncio.Queue()
        manager = EventManager(queue)

        def custom_callback(*, manager, event_type, data):
            pass

        manager.register_event("on_custom", "custom_event", custom_callback)
        assert "on_custom" in manager.events
        assert callable(manager.events["on_custom"])

    def test_register_event_validation_empty_name(self):
        """Test event registration validation for empty name."""
        queue = asyncio.Queue()
        manager = EventManager(queue)

        with pytest.raises(ValueError, match="Event name cannot be empty"):
            manager.register_event("", "test_event")

    def test_register_event_validation_name_prefix(self):
        """Test event registration validation for name prefix."""
        queue = asyncio.Queue()
        manager = EventManager(queue)

        with pytest.raises(ValueError, match="Event name must start with 'on_'"):
            manager.register_event("invalid_name", "test_event")

    def test_validate_callback_not_callable(self):
        """Test callback validation for non-callable."""
        with pytest.raises(TypeError, match="Callback must be callable"):
            EventManager._validate_callback("not_callable")

    def test_validate_callback_wrong_parameters(self):
        """Test callback validation for wrong parameters."""

        def wrong_callback(param1, param2):
            pass

        with pytest.raises(ValueError, match="Callback must have exactly 3 parameters"):
            EventManager._validate_callback(wrong_callback)

    def test_validate_callback_wrong_parameter_names(self):
        """Test callback validation for wrong parameter names."""

        def wrong_names(wrong1, wrong2, wrong3):
            pass

        with pytest.raises(ValueError, match="Callback must have exactly 3 parameters: manager, event_type, and data"):
            EventManager._validate_callback(wrong_names)

    def test_send_event_with_queue(self):
        """Test sending event with queue available."""
        queue = MagicMock()
        manager = EventManager(queue)

        test_data = {"message": "test"}
        manager.send_event(event_type="test", data=test_data)

        # Verify queue.put_nowait was called
        queue.put_nowait.assert_called_once()
        call_args = queue.put_nowait.call_args[0][0]

        # Verify the event structure
        event_id, data_bytes, timestamp = call_args
        assert event_id.startswith("test-")
        assert isinstance(data_bytes, bytes)
        assert isinstance(timestamp, float)

        # Parse the data
        data_str = data_bytes.decode("utf-8").strip()
        parsed_data = json.loads(data_str)
        assert parsed_data["event"] == "test"
        assert parsed_data["data"] == test_data

    def test_send_event_without_queue(self):
        """Test sending event without queue (should not raise error)."""
        manager = EventManager(None)
        test_data = {"message": "test"}

        # Should not raise any exception
        manager.send_event(event_type="test", data=test_data)

    def test_send_event_queue_exception(self):
        """Test sending event when queue raises exception."""
        queue = MagicMock()
        queue.put_nowait.side_effect = Exception("Queue error")
        manager = EventManager(queue)

        test_data = {"message": "test"}
        # Should not raise exception, just log debug message
        manager.send_event(event_type="test", data=test_data)

    def test_noop_method(self):
        """Test noop method."""
        queue = asyncio.Queue()
        manager = EventManager(queue)

        # Should not raise any exception
        manager.noop(data={"test": "data"})

    def test_getattr_existing_event(self):
        """Test __getattr__ for existing event."""
        queue = asyncio.Queue()
        manager = EventManager(queue)
        manager.register_event("on_test", "test_event")

        event_callback = manager.on_test
        assert callable(event_callback)
        assert event_callback == manager.events["on_test"]

    def test_getattr_nonexistent_event(self):
        """Test __getattr__ for non-existent event returns noop."""
        queue = asyncio.Queue()
        manager = EventManager(queue)

        nonexistent_callback = manager.on_nonexistent
        assert callable(nonexistent_callback)
        assert nonexistent_callback == manager.noop

    def test_event_callback_execution(self):
        """Test that event callbacks can be executed."""
        queue = MagicMock()
        manager = EventManager(queue)
        manager.register_event("on_test", "test_event")

        # Execute the callback
        test_data = {"key": "value"}
        manager.on_test(data=test_data)

        # Verify queue was called (since it uses default send_event callback)
        queue.put_nowait.assert_called_once()

    def test_event_types_handling(self):
        """Test handling of different event types."""
        queue = MagicMock()
        manager = EventManager(queue)

        # Test different event types that should be processed
        event_types = ["message", "error", "warning", "info", "token"]

        for event_type in event_types:
            test_data = {"type": event_type, "content": f"test {event_type}"}
            manager.send_event(event_type=event_type, data=test_data)

        # Verify all events were sent
        assert queue.put_nowait.call_count == len(event_types)

    def test_event_data_serialization(self):
        """Test that event data is properly serialized."""
        queue = MagicMock()
        manager = EventManager(queue)

        # Complex data structure
        complex_data = {
            "string": "test",
            "number": 42,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
        }

        manager.send_event(event_type="complex", data=complex_data)

        # Get the serialized data
        call_args = queue.put_nowait.call_args[0][0]
        _, data_bytes, _ = call_args

        data_str = data_bytes.decode("utf-8").strip()
        parsed_data = json.loads(data_str)

        assert parsed_data["data"] == complex_data


class TestEventManagerFactories:
    """Test cases for EventManager factory functions."""

    def test_create_default_event_manager(self):
        """Test creating default event manager."""
        queue = asyncio.Queue()
        manager = create_default_event_manager(queue)

        assert isinstance(manager, EventManager)
        assert manager.queue == queue

        # Check that default events are registered
        expected_events = [
            "on_token",
            "on_vertices_sorted",
            "on_error",
            "on_end",
            "on_message",
            "on_remove_message",
            "on_end_vertex",
            "on_build_start",
            "on_build_end",
        ]

        for event_name in expected_events:
            assert event_name in manager.events
            assert callable(manager.events[event_name])

    def test_create_default_event_manager_without_queue(self):
        """Test creating default event manager without queue."""
        manager = create_default_event_manager()

        assert isinstance(manager, EventManager)
        assert manager.queue is None

        # Events should still be registered
        assert "on_token" in manager.events
        assert "on_error" in manager.events

    def test_create_stream_tokens_event_manager(self):
        """Test creating stream tokens event manager."""
        queue = asyncio.Queue()
        manager = create_stream_tokens_event_manager(queue)

        assert isinstance(manager, EventManager)
        assert manager.queue == queue

        # Check that stream-specific events are registered
        expected_events = ["on_message", "on_token", "on_end"]

        for event_name in expected_events:
            assert event_name in manager.events
            assert callable(manager.events[event_name])

    def test_create_stream_tokens_event_manager_without_queue(self):
        """Test creating stream tokens event manager without queue."""
        manager = create_stream_tokens_event_manager()

        assert isinstance(manager, EventManager)
        assert manager.queue is None

        # Events should still be registered
        assert "on_message" in manager.events
        assert "on_token" in manager.events
        assert "on_end" in manager.events

    def test_default_manager_event_execution(self):
        """Test that events in default manager can be executed."""
        queue = MagicMock()
        manager = create_default_event_manager(queue)

        # Test executing different events
        test_events = [
            ("on_token", {"chunk": "test"}),
            ("on_error", {"error": "test error"}),
            ("on_message", {"text": "test message"}),
        ]

        for event_name, data in test_events:
            event_callback = getattr(manager, event_name)
            event_callback(data=data)

        # Verify all events were sent to queue
        assert queue.put_nowait.call_count == len(test_events)

    def test_stream_manager_event_execution(self):
        """Test that events in stream manager can be executed."""
        queue = MagicMock()
        manager = create_stream_tokens_event_manager(queue)

        # Test executing stream-specific events
        manager.on_token(data={"chunk": "test token"})
        manager.on_message(data={"text": "test message"})
        manager.on_end(data={"status": "completed"})

        # Verify all events were sent to queue
        expected_call_count = 3
        assert queue.put_nowait.call_count == expected_call_count


@pytest.mark.asyncio
class TestEventManagerAsync:
    """Test async functionality related to EventManager."""

    @pytest.mark.asyncio
    async def test_event_manager_with_asyncio_queue(self):
        """Test EventManager with real asyncio queue."""
        queue = asyncio.Queue()
        manager = EventManager(queue)

        test_data = {"message": "async test"}
        manager.send_event(event_type="test", data=test_data)

        # Get item from queue
        item = await queue.get()
        event_id, data_bytes, timestamp = item

        assert event_id.startswith("test-")
        assert isinstance(data_bytes, bytes)
        assert isinstance(timestamp, float)

        # Parse the data
        data_str = data_bytes.decode("utf-8").strip()
        parsed_data = json.loads(data_str)
        assert parsed_data["event"] == "test"
        assert parsed_data["data"] == test_data

    @pytest.mark.asyncio
    async def test_multiple_events_with_queue(self):
        """Test sending multiple events to queue."""
        queue = asyncio.Queue()
        manager = create_default_event_manager(queue)

        # Send multiple events
        events_to_send = [("token", {"chunk": "hello"}), ("message", {"text": "world"}), ("end", {"status": "done"})]

        for event_type, data in events_to_send:
            manager.send_event(event_type=event_type, data=data)

        # Verify all events are in queue
        assert queue.qsize() == len(events_to_send)

        # Process all events
        received_events = []
        while not queue.empty():
            item = await queue.get()
            event_id, data_bytes, timestamp = item
            data_str = data_bytes.decode("utf-8").strip()
            parsed_data = json.loads(data_str)
            received_events.append((parsed_data["event"], parsed_data["data"]))

        # Verify all events were received correctly
        assert len(received_events) == len(events_to_send)
        for sent, received in zip(events_to_send, received_events, strict=False):
            assert sent[0] == received[0]  # event type
            assert sent[1] == received[1]  # data
