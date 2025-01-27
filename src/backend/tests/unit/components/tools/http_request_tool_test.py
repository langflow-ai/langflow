import pytest
from unittest.mock import patch, Mock
import json

from src.backend.base.langflow.components.tools import HttpRequestTool


@pytest.fixture
def api_request():
    # Esta fixture proporciona una instancia de HttpRequestTool
    return HttpRequestTool()


# Mocking una respuesta HTTP GET
@patch('requests.get')
def test_http_request_tool_get(mock_get, api_request):
    # Mockear la respuesta
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "value"}
    mock_response.headers = {"Content-Type": "application/json"}
    mock_get.return_value = mock_response

    # Cargar el valor curl
    api_request.curl = "curl --location 'https://example.com/api/test' --header 'Content-Type: application/json'"

    # Llamar al método make_request
    result = api_request.make_request()

    # Verificar que la respuesta mockeada sea la correcta
    assert result.text == json.dumps({
        "status_code": 200,
        "data": {"key": "value"}
    }, indent=4)


# Mocking una respuesta HTTP POST
@patch('requests.post')
def test_http_request_tool_post(mock_post, api_request):
    # Mockear la respuesta
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"created": True}
    mock_response.headers = {"Content-Type": "application/json"}
    mock_post.return_value = mock_response

    # Cargar el valor curl con --data para POST
    api_request.curl = "curl --location 'https://example.com/api/test' --header 'Content-Type: application/json' --data '{\"product_id\": \"123\"}'"

    # Llamar al método make_request
    result = api_request.make_request()

    # Verificar que la respuesta mockeada sea la correcta
    assert result.text == json.dumps({
        "status_code": 201,
        "data": {"created": True}
    }, indent=4)
