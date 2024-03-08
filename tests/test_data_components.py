import httpx
import pytest
import respx
from httpx import Response

from langflow.components import (
    data,
)  # Adjust the import according to your project structure


@pytest.fixture
def api_request():
    # This fixture provides an instance of APIRequest for each test case
    return data.APIRequest()


@pytest.mark.asyncio
@respx.mock
async def test_successful_get_request(api_request):
    # Mocking a successful GET request
    url = "https://example.com/api/test"
    method = "GET"
    mock_response = {"success": True}
    respx.get(url).mock(return_value=Response(200, json=mock_response))

    # Making the request
    result = await api_request.make_request(
        client=httpx.AsyncClient(), method=method, url=url
    )

    # Assertions
    assert result.data["status_code"] == 200
    assert result.data["result"] == mock_response


@pytest.mark.asyncio
@respx.mock
async def test_failed_request(api_request):
    # Mocking a failed GET request
    url = "https://example.com/api/test"
    method = "GET"
    respx.get(url).mock(return_value=Response(404))

    # Making the request
    result = await api_request.make_request(
        client=httpx.AsyncClient(), method=method, url=url
    )

    # Assertions
    assert result.data["status_code"] == 404


@pytest.mark.asyncio
@respx.mock
async def test_timeout(api_request):
    # Mocking a timeout
    url = "https://example.com/api/timeout"
    method = "GET"
    respx.get(url).mock(
        side_effect=httpx.TimeoutException(message="Timeout", request=None)
    )

    # Making the request
    result = await api_request.make_request(
        client=httpx.AsyncClient(), method=method, url=url, timeout=1
    )

    # Assertions
    assert result.data["status_code"] == 408
    assert result.data["error"] == "Request timed out"


@pytest.mark.asyncio
@respx.mock
async def test_build_with_multiple_urls(api_request):
    # This test depends on having a working internet connection and accessible URLs
    # It's better to mock these requests using respx or a similar library

    # Setup for multiple URLs
    method = "GET"
    urls = ["https://example.com/api/one", "https://example.com/api/two"]
    # You would mock these requests similarly to the single request tests
    for url in urls:
        respx.get(url).mock(return_value=Response(200, json={"success": True}))

    # Do I have to mock the async client?
    #

    # Execute the build method
    results = await api_request.build(method=method, urls=urls)

    # Assertions
    assert len(results) == len(urls)
