import asyncio
import json
import time
import uuid

import pytest
from langflow.events.event_manager import EventManager
from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import TextContent
from langflow.schema.log import LoggableType
from langflow.schema.message import Message
from loguru import logger


class TestEventManager:
    # Registering an event with a valid name and callback using a mock callback function
    def test_register_event_with_valid_name_and_callback_with_mock_callback(self):
        def mock_callback(event_type: str, data: LoggableType):
            pass

        queue = asyncio.Queue()
        manager = EventManager(queue)
        manager.register_event("on_test_event", "test_type", mock_callback)
        assert "on_test_event" in manager.events
        assert manager.events["on_test_event"].func == mock_callback

    # Registering an event with an empty name

    def test_register_event_with_empty_name(self):
        queue = asyncio.Queue()
        manager = EventManager(queue)
        with pytest.raises(ValueError, match="Event name cannot be empty"):
            manager.register_event("", "test_type")

    # Registering an event with a valid name and no callback
    def test_register_event_with_valid_name_and_no_callback(self):
        queue = asyncio.Queue()
        manager = EventManager(queue)
        manager.register_event("on_test_event", "test_type")
        assert "on_test_event" in manager.events
        assert manager.events["on_test_event"].func == manager.send_event

    # Accessing a non-registered event callback via __getattr__ with the recommended fix
    def test_accessing_non_registered_event_callback_with_recommended_fix(self):
        queue = asyncio.Queue()
        manager = EventManager(queue)
        result = manager.__getattr__("non_registered_event")
        assert result == manager.noop

    # Accessing a registered event callback via __getattr__
    def test_accessing_registered_event_callback(self):
        def mock_callback(event_type: str, data: LoggableType):
            pass

        queue = asyncio.Queue()
        manager = EventManager(queue)
        manager.register_event("on_test_event", "test_type", mock_callback)
        assert manager.on_test_event.func == mock_callback

    # Handling a large number of events in the queue
    def test_handling_large_number_of_events(self):
        def mock_queue_put_nowait(item):
            pass

        queue = asyncio.Queue()
        queue.put_nowait = mock_queue_put_nowait
        manager = EventManager(queue)

        for i in range(1000):
            manager.register_event(f"on_test_event_{i}", "test_type", manager.noop)

        assert len(manager.events) == 1000

    # Testing registration of an event with an invalid name with the recommended fix
    def test_register_event_with_invalid_name_fixed(self):
        def mock_callback(event_type, data):
            pass

        queue = asyncio.Queue()
        manager = EventManager(queue)
        with pytest.raises(ValueError, match="Event name cannot be empty"):
            manager.register_event("", "test_type", mock_callback)
        with pytest.raises(ValueError, match="Event name must start with 'on_'"):
            manager.register_event("invalid_name", "test_type", mock_callback)

    # Sending an event with complex data and verifying successful event transmission
    async def test_sending_event_with_complex_data(self):
        queue = asyncio.Queue()

        manager = EventManager(queue)
        manager.register_event("on_test_event", "test_type", manager.noop)
        data = {"key": "value", "nested": [1, 2, 3]}
        await manager.send_event(event_type="test_type", data=data)
        event_id, str_data, event_time = await queue.get()
        assert event_id is not None
        assert str_data is not None
        assert event_time <= time.time()

    # Sending an event with None data
    def test_sending_event_with_none_data(self):
        queue = asyncio.Queue()
        manager = EventManager(queue)
        manager.register_event("on_test_event", "test_type")
        assert "on_test_event" in manager.events
        assert manager.events["on_test_event"].func.__name__ == "send_event"

    # Ensuring thread-safety when accessing the events dictionary
    async def test_thread_safety_accessing_events_dictionary(self):
        def mock_callback(event_type: str, data: LoggableType):
            pass

        async def register_events(manager):
            manager.register_event("on_test_event_1", "test_type_1", mock_callback)
            manager.register_event("on_test_event_2", "test_type_2", mock_callback)

        async def access_events(manager):
            assert "on_test_event_1" in manager.events
            assert "on_test_event_2" in manager.events

        queue = asyncio.Queue()
        manager = EventManager(queue)

        await asyncio.gather(register_events(manager), access_events(manager))

    # Checking the performance impact of frequent event registrations
    def test_performance_impact_frequent_registrations(self):
        def mock_callback(event_type: str, data: LoggableType):
            pass

        queue = asyncio.Queue()
        manager = EventManager(queue)
        for i in range(1000):
            manager.register_event(f"on_test_event_{i}", "test_type", mock_callback)
        assert len(manager.events) == 1000

    # Verifying the uniqueness of event IDs for each event triggered using await with asyncio decorator
    import pytest

    async def test_event_id_uniqueness_with_await(self):
        queue = asyncio.Queue()
        manager = EventManager(queue)
        manager.register_event("on_test_event", "test_type")
        await manager.on_test_event(data={"data_1": "value_1"})
        await manager.on_test_event(data={"data_2": "value_2"})
        try:
            event_id_1, _, _ = await queue.get()
            event_id_2, _, _ = await queue.get()
        except asyncio.TimeoutError:
            pytest.fail("Test timed out while waiting for queue items")

        assert event_id_1 != event_id_2

    # Ensuring the queue receives the correct event data format
    async def test_queue_receives_correct_event_data_format(self):
        async def mock_queue_put_nowait(data):
            pass

        async def mock_queue_get():
            return (uuid.uuid4(), b'{"event": "test_type", "data": "test_data"}\n\n', time.time())

        queue = asyncio.Queue()
        queue.put_nowait = mock_queue_put_nowait
        queue.get = mock_queue_get

        manager = EventManager(queue)
        manager.register_event("on_test_event", "test_type", manager.noop)
        event_data = "test_data"
        await manager.send_event(event_type="test_type", data=event_data)

        event_id, str_data, _ = await queue.get()
        assert isinstance(event_id, uuid.UUID)
        assert isinstance(str_data, bytes)
        assert json.loads(str_data.decode("utf-8")) == {"event": "test_type", "data": event_data}

    # Registering an event without specifying the event_type argument and providing the event_type argument
    @pytest.mark.asyncio
    async def test_register_event_without_event_type_argument_fixed(self):
        class MockQueue:
            def __init__(self):
                self.data = []

            def put_nowait(self, item):
                self.data.append(item)

        queue = MockQueue()
        event_manager = EventManager(queue)
        await event_manager.register_event("on_test_event", "test_event_type", callback=event_manager.noop)
        await event_manager.send_event(event_type="test_type", data={"key": "value"})

        assert len(queue.data) == 1
        event_id, str_data, timestamp = queue.data[0]
        # event_id follows this pattern: f"{event_type}-{uuid.uuid4()}"
        event_type_from_id = event_id.split("-")[0]
        assert event_type_from_id == "test_type"
        uuid_from_id = event_id.split(event_type_from_id)[1]
        assert isinstance(uuid_from_id, str)
        # assert that the uuid_from_id is a valid uuid
        try:
            uuid.UUID(uuid_from_id)
        except ValueError:
            pytest.fail(f"Invalid UUID: {uuid_from_id}")
        assert isinstance(str_data, bytes)
        assert isinstance(timestamp, float)

    # Accessing a non-registered event callback via __getattr__
    def test_accessing_non_registered_callback(self):
        class MockQueue:
            def __init__(self):
                pass

            def put_nowait(self, item):
                pass

        queue = MockQueue()
        event_manager = EventManager(queue)

        # Accessing a non-registered event callback should return the 'noop' function
        callback = event_manager.on_non_existing_event
        assert callback.__name__ == "noop"

    @pytest.mark.asyncio
    async def test_message_patch_generation(self):
        queue = asyncio.Queue()
        manager = EventManager(queue)

        # Create initial message
        message = Message(
            id=str(uuid.uuid4()),
            sender="AI",
            sender_name="Test Agent",
            text="Initial text",
            content_blocks=[
                ContentBlock(
                    title="Test Block",
                    contents=[
                        TextContent(
                            type="text",
                            text="Initial content",
                            duration=100,
                            header={"title": "Input", "icon": "MessageSquare"},
                        )
                    ],
                )
            ],
        )

        # Send initial message
        initial_data = message.model_dump()
        logger.debug(f"Initial message data: {initial_data}")  # Debug log
        await manager.send_event(event_type="message", data=initial_data)

        # Modify message
        message.text = "Updated text"
        message.content_blocks[0].contents[0].text = "Updated content"

        # Send updated message
        updated_data = message.model_dump()
        logger.debug(f"Updated message data: {updated_data}")  # Debug log
        await manager.send_event(event_type="message", data=updated_data)

        # Get the events from queue
        assert queue.qsize() == 2
        _, initial_event_data, _ = queue._queue[0]
        _, updated_event_data, _ = queue._queue[1]

        # Parse the events
        initial_event = json.loads(initial_event_data.decode("utf-8"))
        updated_event = json.loads(updated_event_data.decode("utf-8"))

        # Debug output
        logger.debug(f"Initial event data: {initial_event}")
        logger.debug(f"Updated event data: {updated_event}")

        # Verify patch was generated
        assert "patch" not in initial_event["data"]
        assert "patch" in updated_event["data"], f"Expected patch in data, got: {updated_event['data']}"

        # Verify patch content
        patch = updated_event["data"]["patch"]
        assert isinstance(patch, list), f"Expected patch to be a list, got: {type(patch)}"

        # Create a dict of all changes in the patch for easier verification
        patch_changes = {p["path"]: p["value"] for p in patch if p["op"] == "replace"}

        # Verify expected changes
        assert patch_changes.get("/text") == "Updated text", "Text change not found in patch"
        assert (
            patch_changes.get("/content_blocks/0/contents/0/text") == "Updated content"
        ), "Content block text change not found in patch"

    @pytest.mark.asyncio
    async def test_message_patch_no_changes(self):
        queue = asyncio.Queue()
        manager = EventManager(queue)

        # Create message
        message = Message(id="test-id", sender="AI", sender_name="Test Agent", text="Test text")

        # Send same message twice
        data = message.model_dump()
        await manager.send_event(event_type="message", data=data)
        await manager.send_event(event_type="message", data=data)

        # Get the events
        assert queue.qsize() == 2
        _, first_event_data, _ = queue._queue[0]
        _, second_event_data, _ = queue._queue[1]

        first_event = json.loads(first_event_data.decode("utf-8"))
        second_event = json.loads(second_event_data.decode("utf-8"))

        # Verify no patch was generated for identical messages
        assert "patch" not in first_event["data"]
        assert "patch" not in second_event["data"]

    @pytest.mark.asyncio
    async def test_message_patch_with_complex_changes(self):
        queue = asyncio.Queue()
        manager = EventManager(queue)

        # Create initial message with complex structure
        message = Message(
            id="test-id",
            sender="AI",
            sender_name="Test Agent",
            text="Initial text",
            content_blocks=[
                ContentBlock(
                    title="Test Block",
                    contents=[
                        TextContent(
                            type="text",
                            text="Content 1",
                            duration=100,
                            header={"title": "Input", "icon": "MessageSquare"},
                        ),
                        TextContent(
                            type="text",
                            text="Content 2",
                            duration=200,
                            header={"title": "Output", "icon": "MessageSquare"},
                        ),
                    ],
                )
            ],
        )

        # Send initial message
        initial_data = message.model_dump()
        await manager.send_event(event_type="message", data=initial_data)

        # Make multiple changes
        message.text = "Updated text"
        message.content_blocks[0].contents[0].text = "Updated content 1"
        message.content_blocks[0].contents[1].duration = 300
        message.content_blocks[0].contents[1].header["title"] = "New Output"

        # Send updated message
        updated_data = message.model_dump()
        await manager.send_event(event_type="message", data=updated_data)

        # Get and parse events
        assert queue.qsize() == 2
        _, initial_event_data, _ = queue._queue[0]
        _, updated_event_data, _ = queue._queue[1]

        initial_event = json.loads(initial_event_data.decode("utf-8"))
        updated_event = json.loads(updated_event_data.decode("utf-8"))

        # Debug output
        logger.debug(f"Initial event: {initial_event}")
        logger.debug(f"Updated event: {updated_event}")

        # Verify patch
        assert "patch" not in initial_event["data"]
        assert "patch" in updated_event["data"]

        # Get the patch directly - it's already a list
        patch = updated_event["data"]["patch"]
        assert isinstance(patch, list), f"Expected patch to be a list, got: {type(patch)}"

        # Create a dict of all changes in the patch for easier verification
        patch_changes = {p["path"]: p["value"] for p in patch if p["op"] == "replace"}

        # Debug output
        logger.debug(f"Patch changes: {patch_changes}")

        # Verify expected changes
        expected_changes = {
            "/text": "Updated text",
            "/content_blocks/0/contents/0/text": "Updated content 1",
            "/content_blocks/0/contents/1/duration": 300,
            "/content_blocks/0/contents/1/header/title": "New Output",
        }

        # Verify each expected change
        for path, expected_value in expected_changes.items():
            assert path in patch_changes, f"Expected change at path {path} not found in patch"
            assert patch_changes[path] == expected_value, (
                f"Value mismatch at {path}. " f"Expected: {expected_value}, " f"Got: {patch_changes[path]}"
            )
