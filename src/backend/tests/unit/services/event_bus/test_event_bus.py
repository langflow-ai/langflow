import asyncio

import pytest
from langflow.services.event_bus.service import EventBusService


@pytest.fixture
async def event_bus_service():
    service = EventBusService()
    await service.connect()
    yield service
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
    await event_bus_service.publish(event_type, payload)

    # Give the consumer some time to process the message
    await asyncio.sleep(0.1)
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
    await event_bus_service.publish(event_type, payload)

    await asyncio.sleep(0.1)  # Allow time for processing
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
    await event_bus_service.publish(event_type1, payload1)
    await event_bus_service.publish(event_type2, payload2)

    await asyncio.sleep(0.1)  # Allow time for processing
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
        raise Exception(msg)  # noqa: TRY002

    # Use monkeypatch to replace the connect method
    monkeypatch.setattr(event_bus_service, "connect", mock_connect)

    with pytest.raises(Exception, match="Mock connection error"):
        await event_bus_service.connect()
