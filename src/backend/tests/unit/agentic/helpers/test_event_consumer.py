"""Tests for event_consumer -- verify flow_preview events are forwarded."""

import asyncio
import json

from langflow.agentic.services.helpers.event_consumer import consume_streaming_events, parse_event_data


class TestParseEventData:
    def test_parse_token_event(self):
        data = json.dumps({"event": "token", "data": {"chunk": "hello"}}).encode()
        event_type, data_dict = parse_event_data(data)
        assert event_type == "token"
        assert data_dict["chunk"] == "hello"

    def test_parse_flow_preview_event(self):
        flow_data = {"flow": {"data": {"nodes": [], "edges": []}}, "name": "Test"}
        data = json.dumps({"event": "flow_preview", "data": flow_data}).encode()
        event_type, data_dict = parse_event_data(data)
        assert event_type == "flow_preview"
        assert data_dict["name"] == "Test"
        assert "flow" in data_dict

    def test_parse_empty_data(self):
        event_type, data_dict = parse_event_data(b"")
        assert event_type is None
        assert data_dict == {}


class TestConsumeStreamingEvents:
    async def test_forwards_flow_preview_events(self):
        queue: asyncio.Queue = asyncio.Queue()

        # Put a flow_preview event and a terminator
        flow_event = {
            "event": "flow_preview",
            "data": {"flow": {"data": {"nodes": []}}, "name": "Test Flow"},
        }
        event_str = json.dumps(flow_event) + "\n\n"
        queue.put_nowait(("flow_preview-1", event_str.encode(), 0.0))
        queue.put_nowait(None)  # terminator

        events = []
        async for event_type, data in consume_streaming_events(queue):
            events.append((event_type, data))

        assert len(events) == 1
        assert events[0][0] == "flow_preview"
        assert events[0][1]["name"] == "Test Flow"

    async def test_forwards_tokens_and_flow_preview(self):
        queue: asyncio.Queue = asyncio.Queue()

        # Token event
        token_event = json.dumps({"event": "token", "data": {"chunk": "Building..."}}) + "\n\n"
        queue.put_nowait(("token-1", token_event.encode(), 0.0))

        # Flow preview event
        flow_event = (
            json.dumps(
                {
                    "event": "flow_preview",
                    "data": {"flow": {}, "name": "My Flow", "node_count": 3, "edge_count": 2},
                }
            )
            + "\n\n"
        )
        queue.put_nowait(("flow-1", flow_event.encode(), 0.0))

        # End event
        end_event = json.dumps({"event": "end", "data": {}}) + "\n\n"
        queue.put_nowait(("end-1", end_event.encode(), 0.0))

        events = []
        async for event_type, data in consume_streaming_events(queue):
            events.append((event_type, data))

        assert events[0] == ("token", "Building...")
        assert events[1][0] == "flow_preview"
        assert events[1][1]["name"] == "My Flow"
        assert events[2] == ("end", "")
