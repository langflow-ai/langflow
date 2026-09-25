from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.store.service import StoreService


# Fixture for the mocked settings_service
@pytest.fixture
def mock_settings_service():
    service = MagicMock()
    # Start with the webhook defined (happy path)
    service.settings.store_url = "http://fake.store.url"
    service.settings.download_webhook_url = "http://fake.webhook.url"
    return service


# Fixture for the StoreService with mocked dependencies
@pytest.fixture
def store_service(mock_settings_service):
    service = StoreService(mock_settings_service)

    # Mock (simulate) the external functions that 'download' calls
    # We don't want to test 'get' or 'call_webhook', just the 'download' logic
    service.get = AsyncMock()
    service.call_webhook = AsyncMock()

    # Simulate the 'process_component_data' function so it doesn't execute
    with patch("langflow.services.store.service.process_component_data") as mock_process:
        mock_process.return_value = {"processed": True}
        # Pass the mock so we can verify it in the tests
        service.mock_process_component_data = mock_process
        yield service


# Fake data to simulate the component return from the DB
def get_mock_component(metadata, data):
    return {
        "id": str(uuid4()),
        "name": "Test Component",
        "description": "A component for testing",
        "data": data,
        "is_component": True,
        "metadata": metadata,
    }


@pytest.mark.asyncio
async def test_download_fails_without_webhook_url(store_service):
    """Test that download raises ValueError when download_webhook_url is not configured.

    Covers MC/DC Decision D1 (True): download_webhook_url check fails.
    """
    # CT1: Covers D1 (T)
    # Configure the service to fail on the first decision
    store_service.download_webhook_url = None  # C1 = True

    with pytest.raises(ValueError, match="DOWNLOAD_WEBHOOK_URL is not set"):
        await store_service.download(api_key="fake_key", component_id=uuid4())


@pytest.mark.asyncio
async def test_download_fails_with_multiple_components(store_service):
    """Test that download raises ValueError when multiple components are returned.

    Covers MC/DC Decision D1 (False) and D2 (True): webhook URL exists but
    multiple components returned from store API.
    """
    # CT2: Covers D1 (F) and D2 (T)

    # D1 (C1=F) is the fixture default (webhook_url exists)

    # D2 (C2=T)
    mock_comp1 = get_mock_component({}, {"nodes": []})
    mock_comp2 = get_mock_component({}, {"nodes": []})
    store_service.get.return_value = ([mock_comp1, mock_comp2], {})  # len(component) > 1

    with pytest.raises(ValueError, match="Something went wrong"):
        await store_service.download(api_key="fake_key", component_id=uuid4())

    store_service.call_webhook.assert_called_once()  # Ensures D1 was False


@pytest.mark.asyncio
async def test_download_success_generates_metadata(store_service):
    """Test that download generates metadata when metadata is empty and data is present.

    Covers MC/DC Decision D1 (False), D2 (False), and D3 Row 1 (True, True):
    webhook configured, single component returned, empty metadata with data present.
    Verifies that process_component_data is called and metadata is populated.
    """
    # CT3: Covers D1(F), D2(F), D3:Row 1 (T,T)

    # D3 (C3=T, C4=T)
    mock_data = {"nodes": ["node1"]}  # C4 = True
    mock_metadata = {}  # C3 = True

    mock_comp = get_mock_component(mock_metadata, mock_data)
    store_service.get.return_value = ([mock_comp], {})  # D2 (C2=F)

    component = await store_service.download(api_key="fake_key", component_id=uuid4())

    # Check if D3 (if) was executed
    store_service.mock_process_component_data.assert_called_once_with(["node1"])
    assert component.metadata == {"processed": True}


@pytest.mark.asyncio
async def test_download_success_with_no_data(store_service):
    """Test that download skips metadata generation when data is None.

    Covers MC/DC Decision D1 (False), D2 (False), and D3 Row 2 (True, False):
    webhook configured, single component returned, empty metadata but no data.
    Verifies that process_component_data is not called and metadata remains unchanged.
    """
    # CT4: Covers D1(F), D2(F), D3:Row 2 (T,F)

    # D3 (C3=T, C4=F)
    mock_data = None  # C4 = False
    mock_metadata = {}  # C3 = True

    mock_comp = get_mock_component(mock_metadata, mock_data)
    store_service.get.return_value = ([mock_comp], {})  # D2 (C2=F)

    component = await store_service.download(api_key="fake_key", component_id=uuid4())

    # Check if D3 (if) was NOT executed
    store_service.mock_process_component_data.assert_not_called()
    assert component.metadata == {}  # Kept the original


@pytest.mark.asyncio
async def test_download_success_with_existing_metadata(store_service):
    """Test that download preserves existing metadata even when data is present.

    Covers MC/DC Decision D1 (False), D2 (False), and D3 Row 3 (False, True):
    webhook configured, single component returned, existing metadata with data present.
    Verifies that process_component_data is not called and metadata is preserved.
    """
    # CT5: Covers D1(F), D2(F), D3:Row 3 (F,T)

    # D3 (C3=F, C4=T)
    mock_data = {"nodes": ["node1"]}  # C4 = True
    mock_metadata = {"key": "value"}  # C3 = False

    mock_comp = get_mock_component(mock_metadata, mock_data)
    store_service.get.return_value = ([mock_comp], {})  # D2 (C2=F)

    component = await store_service.download(api_key="fake_key", component_id=uuid4())

    # Check if D3 (if) was NOT executed
    store_service.mock_process_component_data.assert_not_called()
    assert component.metadata == {"key": "value"}  # Kept the original
