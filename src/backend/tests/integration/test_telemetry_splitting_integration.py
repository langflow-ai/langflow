"""Integration tests for telemetry service splitting."""

from unittest.mock import MagicMock

import pytest
from langflow.services.telemetry.schema import ComponentInputsPayload
from langflow.services.telemetry.service import TelemetryService


@pytest.mark.asyncio
async def test_service_splits_large_payload(mock_settings_service):
    """Test that service splits large payload and queues multiple chunks."""
    service = TelemetryService(mock_settings_service)

    # Create large payload with dict[str, Any] type
    large_inputs = {f"input_{i}": "x" * 100 for i in range(50)}

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=large_inputs,
    )

    # Track queued events
    queued_events = []

    async def mock_queue_event(event):
        queued_events.append(event)

    service._queue_event = mock_queue_event

    # Log the payload
    await service.log_package_component_inputs(payload)

    # Should have queued multiple chunks
    assert len(queued_events) > 1

    # Each queued event should be a tuple (func, payload, path)
    for event in queued_events:
        assert isinstance(event, tuple)
        assert len(event) == 3


@pytest.mark.asyncio
async def test_service_no_split_for_small_payload(mock_settings_service):
    """Test that service doesn't split small payload."""
    service = TelemetryService(mock_settings_service)

    # Create small payload with dict[str, Any] type
    small_inputs = {"input1": "value1"}

    payload = ComponentInputsPayload(
        component_run_id="test-run-id",
        component_id="test-comp-id",
        component_name="TestComponent",
        component_inputs=small_inputs,
    )

    # Track queued events
    queued_events = []

    async def mock_queue_event(event):
        queued_events.append(event)

    service._queue_event = mock_queue_event

    # Log the payload
    await service.log_package_component_inputs(payload)

    # Should have queued only one event
    assert len(queued_events) == 1


@pytest.fixture
def mock_settings_service():
    """Mock settings service for testing."""
    settings_service = MagicMock()
    settings_service.settings.telemetry_base_url = "https://api.scarf.sh/v1/pixel"
    settings_service.settings.do_not_track = False
    settings_service.settings.prometheus_enabled = False
    settings_service.auth_settings.AUTO_LOGIN = False

    return settings_service
