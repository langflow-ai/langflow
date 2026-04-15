"""Tests for event consumer utilities.

Tests the streaming event consumption and parsing functionality.
"""

import asyncio

import pytest
from langflow.agentic.services.helpers.event_consumer import (
    consume_streaming_events,
    parse_event_data,
)


class TestParseEventData:
    """Tests for parse_event_data function."""

    def test_should_parse_token_event(self):
        """Should parse token event with chunk data."""
        data = b'{"event": "token", "data": {"chunk": "Hello"}}'

        event_type, event_data = parse_event_data(data)

        assert event_type == "token"
        assert event_data == {"chunk": "Hello"}

    def test_should_parse_end_event(self):
        """Should parse end event."""
        data = b'{"event": "end", "data": {"result": "complete"}}'

        event_type, event_data = parse_event_data(data)

        assert event_type == "end"
        assert event_data == {"result": "complete"}

    def test_should_return_none_for_empty_data(self):
        """Should return None event type for empty data."""
        event_type, event_data = parse_event_data(b"")

        assert event_type is None
        assert event_data == {}

    def test_should_return_none_for_whitespace(self):
        """Should return None for whitespace-only data."""
        event_type, event_data = parse_event_data(b"   \n\t  ")

        assert event_type is None
        assert event_data == {}

    def test_should_handle_event_without_data_field(self):
        """Should handle event without data field, returning empty dict."""
        data = b'{"event": "ping"}'

        event_type, event_data = parse_event_data(data)

        assert event_type == "ping"
        assert event_data == {}

    def test_should_handle_unicode_content(self):
        """Should handle Unicode content in event data."""
        data = '{"event": "token", "data": {"chunk": "こんにちは"}}'.encode()

        event_type, event_data = parse_event_data(data)

        assert event_type == "token"
        assert event_data["chunk"] == "こんにちは"

    def test_should_handle_nested_data(self):
        """Should handle nested data structures."""
        data = b'{"event": "result", "data": {"nested": {"key": "value"}, "list": [1, 2, 3]}}'

        event_type, event_data = parse_event_data(data)

        assert event_type == "result"
        assert event_data["nested"]["key"] == "value"
        assert event_data["list"] == [1, 2, 3]


class TestConsumeStreamingEvents:
    """Tests for consume_streaming_events function."""

    @pytest.mark.asyncio
    async def test_should_yield_token_events(self):
        """Should yield token events from queue."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()

        # Add token events to queue
        await queue.put(("id1", b'{"event": "token", "data": {"chunk": "Hello"}}', 1.0))
        await queue.put(("id2", b'{"event": "token", "data": {"chunk": " World"}}', 2.0))
        await queue.put(None)  # Signal end

        events = []
        async for event_type, data in consume_streaming_events(queue):
            events.append((event_type, data))

        assert len(events) == 2
        assert events[0] == ("token", "Hello")
        assert events[1] == ("token", " World")

    @pytest.mark.asyncio
    async def test_should_yield_end_event_and_stop(self):
        """Should yield end event and stop consuming."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()

        await queue.put(("id1", b'{"event": "token", "data": {"chunk": "test"}}', 1.0))
        await queue.put(("id2", b'{"event": "end"}', 2.0))
        await queue.put(("id3", b'{"event": "token", "data": {"chunk": "ignored"}}', 3.0))

        events = []
        async for event_type, data in consume_streaming_events(queue):
            events.append((event_type, data))

        assert len(events) == 2
        assert events[0] == ("token", "test")
        assert events[1] == ("end", "")

    @pytest.mark.asyncio
    async def test_should_stop_on_none_sentinel(self):
        """Should stop when None is received from queue."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()

        await queue.put(("id1", b'{"event": "token", "data": {"chunk": "test"}}', 1.0))
        await queue.put(None)

        events = []
        async for event_type, data in consume_streaming_events(queue):
            events.append((event_type, data))

        assert len(events) == 1
        assert events[0] == ("token", "test")

    @pytest.mark.asyncio
    async def test_should_yield_cancelled_on_cancel_event(self):
        """Should yield cancelled event when cancel_event is set."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()
        cancel_event = asyncio.Event()

        # Set cancel event before consuming
        cancel_event.set()

        events = []
        async for event_type, data in consume_streaming_events(queue, cancel_event=cancel_event):
            events.append((event_type, data))

        assert len(events) == 1
        assert events[0] == ("cancelled", "")

    @pytest.mark.asyncio
    async def test_should_check_cancel_during_timeout(self):
        """Should check cancel event during queue timeout."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()
        cancel_event = asyncio.Event()

        async def set_cancel_after_delay():
            await asyncio.sleep(0.1)
            cancel_event.set()

        task = asyncio.create_task(set_cancel_after_delay())

        events = []
        async for event_type, data in consume_streaming_events(queue, cancel_event=cancel_event):
            events.append((event_type, data))

        await task  # Ensure task completes

        assert len(events) == 1
        assert events[0] == ("cancelled", "")

    @pytest.mark.asyncio
    async def test_should_check_disconnection_callback(self):
        """Should check disconnection callback during timeout."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()

        call_count = 0

        async def is_disconnected():
            nonlocal call_count
            call_count += 1
            return call_count >= 2  # Disconnect on second check

        events = []
        async for event_type, data in consume_streaming_events(queue, is_disconnected=is_disconnected):
            events.append((event_type, data))

        assert len(events) == 1
        assert events[0] == ("cancelled", "")

    @pytest.mark.asyncio
    async def test_should_ignore_disconnection_check_errors(self):
        """Should ignore errors from disconnection check callback."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()

        check_count = 0

        async def flaky_is_disconnected():
            nonlocal check_count
            check_count += 1
            if check_count == 1:
                msg = "Connection check failed"
                raise RuntimeError(msg)
            return True  # Disconnect on second check

        events = []
        async for event_type, data in consume_streaming_events(queue, is_disconnected=flaky_is_disconnected):
            events.append((event_type, data))

        # Should have recovered from first error and caught second check
        assert events[-1] == ("cancelled", "")

    @pytest.mark.asyncio
    async def test_should_skip_malformed_json_events(self):
        """Should skip events with malformed JSON."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()

        await queue.put(("id1", b'{"event": "token", "data": {"chunk": "good"}}', 1.0))
        await queue.put(("id2", b"not valid json", 2.0))
        await queue.put(("id3", b'{"event": "token", "data": {"chunk": "also good"}}', 3.0))
        await queue.put(None)

        events = []
        async for event_type, data in consume_streaming_events(queue):
            events.append((event_type, data))

        assert len(events) == 2
        assert events[0] == ("token", "good")
        assert events[1] == ("token", "also good")

    @pytest.mark.asyncio
    async def test_should_skip_events_with_empty_chunk(self):
        """Should not yield token events with empty chunk."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()

        await queue.put(("id1", b'{"event": "token", "data": {"chunk": ""}}', 1.0))
        await queue.put(("id2", b'{"event": "token", "data": {"chunk": "real"}}', 2.0))
        await queue.put(None)

        events = []
        async for event_type, data in consume_streaming_events(queue):
            events.append((event_type, data))

        assert len(events) == 1
        assert events[0] == ("token", "real")

    @pytest.mark.asyncio
    async def test_should_handle_unicode_decode_errors(self):
        """Should skip events with Unicode decode errors."""
        queue: asyncio.Queue[tuple[str, bytes, float] | None] = asyncio.Queue()

        await queue.put(("id1", b'{"event": "token", "data": {"chunk": "good"}}', 1.0))
        await queue.put(("id2", b"\xff\xfe", 2.0))  # Invalid UTF-8
        await queue.put(("id3", b'{"event": "token", "data": {"chunk": "fine"}}', 3.0))
        await queue.put(None)

        events = []
        async for event_type, data in consume_streaming_events(queue):
            events.append((event_type, data))

        assert len(events) == 2
        assert events[0] == ("token", "good")
        assert events[1] == ("token", "fine")
