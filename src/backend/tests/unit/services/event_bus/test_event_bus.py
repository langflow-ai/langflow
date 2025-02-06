import asyncio
import json

import fakeredis
import pytest
from langflow.services.event_bus.service import EventBusService
from redis import asyncio as redis


# Create a mock settings service for testing
class MockSettingsService:
    class MockSettings:
        def __init__(self):
            self.redis_url = "redis://localhost:6379"  # Use a default URL

    def __init__(self):
        self.settings = self.MockSettings()


@pytest.fixture
async def event_bus_service():
    # Use fakeredis for testing
    settings_service = MockSettingsService()
    # Override the redis_url to use fakeredis
    settings_service.settings.redis_url = "redis://localhost"
    service = EventBusService(settings_service)
    # Set stream ID to read from beginning for tests
    service.set_stream_id("0-0")
    # Create a FakeRedis instance
    fake_redis = fakeredis.aioredis.FakeRedis()
    # Replace the redis client with our fake one
    service.redis_client = fake_redis
    # Create the stream and consumer group
    init_message = json.dumps({"event_type": "init", "data": "init"}).encode()
    await fake_redis.xadd(
        service.stream_name, {"data": init_message}
    )  # Initialize stream with a properly encoded message
    yield service
    # Cleanup: Cancel all running tasks
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await service.disconnect()


@pytest.mark.asyncio
async def test_publish_subscribe(event_bus_service):
    received_payload = None

    async def callback(payload):
        nonlocal received_payload
        received_payload = payload

    event_type = "test_event"
    payload = {"message": "Hello, world!"}

    await event_bus_service.subscribe(event_type, callback)
    # Give the consumer some time to start
    await asyncio.sleep(0.1)
    await event_bus_service.publish(event_type, payload)

    # Give the consumer some time to process the message
    await asyncio.sleep(0.2)
    assert received_payload == payload, "Payload not received correctly"


@pytest.mark.asyncio
async def test_unsubscribe(event_bus_service):
    received_payload = None

    async def callback(payload):
        nonlocal received_payload
        received_payload = payload

    event_type = "test_event"
    payload = {"message": "Hello, world!"}

    await event_bus_service.subscribe(event_type, callback)
    await event_bus_service.unsubscribe(event_type, callback)
    await event_bus_service.publish(event_type, payload)

    await asyncio.sleep(0.1)  # Allow time for processing
    assert received_payload is None, "Received message after unsubscribe"


@pytest.mark.asyncio
async def test_multiple_subscribers(event_bus_service):
    received_payloads = []

    async def callback1(payload):
        received_payloads.append(payload)

    async def callback2(payload):
        received_payloads.append(payload)

    event_type = "test_event"
    payload = {"message": "Hello, world!"}

    await event_bus_service.subscribe(event_type, callback1)
    await event_bus_service.subscribe(event_type, callback2)
    # Give the consumers some time to start
    await asyncio.sleep(0.1)
    await event_bus_service.publish(event_type, payload)

    await asyncio.sleep(0.2)  # Allow time for processing
    assert len(received_payloads) == 2, "Incorrect number of payloads received"
    assert all(p == payload for p in received_payloads), "Payloads not received correctly"


@pytest.mark.asyncio
async def test_different_event_types(event_bus_service):
    received_payload1 = None
    received_payload2 = None

    async def callback1(payload):
        nonlocal received_payload1
        received_payload1 = payload

    async def callback2(payload):
        nonlocal received_payload2
        received_payload2 = payload

    event_type1 = "event_type1"
    event_type2 = "event_type2"
    payload1 = {"message": "Hello from event 1"}
    payload2 = {"message": "Hello from event 2"}

    await event_bus_service.subscribe(event_type1, callback1)
    await event_bus_service.subscribe(event_type2, callback2)
    # Give the consumers some time to start
    await asyncio.sleep(0.1)
    await event_bus_service.publish(event_type1, payload1)
    await event_bus_service.publish(event_type2, payload2)

    await asyncio.sleep(0.2)  # Allow time for processing
    assert received_payload1 == payload1, "Payload 1 not received correctly"
    assert received_payload2 == payload2, "Payload 2 not received correctly"


@pytest.mark.asyncio
async def test_no_subscribers(event_bus_service):
    # Test that publishing an event with no subscribers doesn't cause errors
    event_type = "unsubscribed_event"
    payload = {"message": "This should not be received"}
    await event_bus_service.publish(event_type, payload)
    await asyncio.sleep(0.1)  # Allow time for processing (or lack thereof)


@pytest.mark.asyncio
async def test_connection_error(event_bus_service, monkeypatch):
    async def mock_connect(*args, **kwargs):  # noqa: ARG001
        msg = "Mock connection error"
        raise redis.ConnectionError(msg)

    # Use monkeypatch to replace the connect method
    monkeypatch.setattr(event_bus_service, "connect", mock_connect)

    with pytest.raises(redis.ConnectionError, match="Mock connection error"):
        await event_bus_service.connect()
