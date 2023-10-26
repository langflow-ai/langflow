# FILEPATH: /Users/ogabrielluiz/Projects/langflow2/tests/test_store_service.py

from datetime import datetime
from unittest.mock import patch, Mock

from langflow.services.deps import get_store_service


@patch("langflow.services.store.service.httpx")
def test_search_components(mock_httpx: Mock, client):
    # Mock the response from the HTTP GET request
    from langflow.services.store.schema import ComponentResponse

    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [
            {
                "id": "1",
                "name": "Test Component 1",
                "description": "This is a test component.",
                "tags": ["test"],
                "status": "published",
                "date_updated": datetime.now().isoformat(),
                "is_component": False,
            },
            {
                "id": "2",
                "name": "Test Component 2",
                "description": "This is another test component.",
                "tags": ["test"],
                "status": "published",
                "date_updated": datetime.now().isoformat(),
                "is_component": True,
            },
        ]
    }
    mock_httpx.get.return_value = mock_response

    # Create an instance of the StoreService class and call the search method
    store_service = get_store_service()
    components = store_service.search(api_key=None, query="test", limit=5)

    # Assert that the HTTP GET request was made with the correct parameters
    mock_httpx.get.assert_called_once_with(
        store_service.components_url,
        headers={},
        params={
            "filter[name][_like]": "test",
            "page": 1,
            "limit": 5,
            "sort": "count(liked_by)",
        },
    )

    # Assert that the search method returns a list of ComponentResponse objects
    assert len(components) == 2
    assert all(isinstance(component, ComponentResponse) for component in components)
