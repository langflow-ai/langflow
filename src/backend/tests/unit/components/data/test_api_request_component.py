import tempfile
from pathlib import Path
from unittest.mock import Mock

import aiofiles
import aiofiles.os
import httpx
import pytest
import respx
from httpx import Response
from langflow.components import data


@pytest.fixture
def api_request():
    # This fixture provides an instance of APIRequest for each test case
    return data.APIRequestComponent()


def test_parse_curl(api_request):
    # Arrange
    field_value = (
        "curl -X GET https://example.com/api/test -H 'Content-Type: application/json' -d '{\"key\": \"value\"}'"
    )
    build_config = {
        "method": {"value": ""},
        "urls": {"value": []},
        "headers": {},
        "body": {},
    }
    # Act
    new_build_config = api_request.parse_curl(field_value, build_config.copy())

    # Assert
    assert new_build_config["method"]["value"] == "GET"
    assert new_build_config["urls"]["value"] == ["https://example.com/api/test"]
    assert new_build_config["headers"]["value"] == [{"key": "Content-Type", "value": "application/json"}]
    assert new_build_config["body"]["value"] == [{"key": "key", "value": "value"}]


# HTTPx Metadata testing
@pytest.mark.parametrize(
    ("include_metadata", "expected_properties"),
    [
        (False, {"source", "result"}),
        (True, {"source", "result", "headers", "status_code", "response_headers", "redirection_history"}),
    ],
)
@respx.mock
async def test_httpx_metadata_behavior(api_request, include_metadata, expected_properties):
    # Mocking a successful GET request with headers and a redirection
    url = "https://example.com/api/test"
    redirected_url = "https://example.com/api/redirect"
    response_content = {"key": "value"}
    respx.get(url).mock(return_value=Response(303, headers={"Location": redirected_url}))
    respx.get(redirected_url).mock(
        return_value=Response(200, json=response_content, headers={"Custom-Header": "HeaderValue"})
    )

    # Make the request
    result = await api_request.make_request(
        client=httpx.AsyncClient(),
        method="GET",
        url=url,
        save_to_file=False,
        include_httpx_metadata=include_metadata,
    )

    # Check returned metadata
    metadata = result.data
    assert set(metadata.keys()) == expected_properties, f"Unexpected properties: {set(metadata.keys())}"

    if include_metadata:
        # Validate individual fields
        assert metadata["source"] == url
        assert metadata["headers"] is None
        assert metadata["status_code"] == 200
        assert metadata["response_headers"]["custom-header"] == "HeaderValue"

        # Validate redirection history
        assert metadata["redirection_history"] == [{"url": redirected_url, "status_code": 303}], (
            "Redirection history is incorrect"
        )

        # Validate result
        assert metadata["result"] == response_content, "Response content mismatch"


# Save to File testing
@pytest.mark.parametrize(
    ("save_to_file", "expected_properties"),
    [
        (False, {"source", "result"}),
        (True, {"source", "file_path"}),
    ],
)
@respx.mock
async def test_save_to_file_behavior(api_request, save_to_file, expected_properties):
    # Mocking a successful GET request with a response body
    url = "https://example.com/api/test"
    response_content = "Test response content"
    respx.get(url).mock(return_value=Response(200, content=response_content))

    # Make the request
    result = await api_request.make_request(
        client=httpx.AsyncClient(),
        method="GET",
        url=url,
        save_to_file=save_to_file,
    )

    # Check returned metadata
    metadata = result.data
    assert set(metadata.keys()) == expected_properties, (
        f"Unexpected properties: {set(metadata.keys())}. Raw result: {result.data}"
    )

    if save_to_file:
        # Validate that file_path exists in metadata
        assert "file_path" in metadata, "file_path is missing in metadata"
        file_path = metadata["file_path"]

        # Validate that the file exists and its content matches the response
        assert await aiofiles.os.path.exists(file_path), "Saved file does not exist"
        async with aiofiles.open(file_path) as f:
            file_content = await f.read()
        assert file_content == response_content, "File content does not match response content"

        # Cleanup the file
        await aiofiles.os.remove(file_path)
    else:
        # Validate that result exists in metadata
        assert "result" in metadata, "result is missing in metadata"
        assert metadata["result"] == response_content.encode("utf-8"), "Response content mismatch in metadata"


async def test_response_info_binary_content(api_request):
    response = Mock()
    response.headers = {"Content-Type": "application/octet-stream"}
    is_binary, file_path = await api_request._response_info(response, with_file_path=False)
    assert is_binary is True
    assert file_path is None


async def test_response_info_non_binary_content(api_request):
    response = Mock()
    response.headers = {"Content-Type": "text/plain"}
    is_binary, file_path = await api_request._response_info(response, with_file_path=False)
    assert is_binary is False
    assert file_path is None


async def test_response_info_filename_from_content_disposition(api_request):
    response = Mock()
    response.headers = {
        "Content-Disposition": 'attachment; filename="thisfile.txt"',
        "Content-Type": "text/plain",
    }
    response.request = Mock()
    response.request.url = "https://example.com/testfile"

    is_binary, file_path = await api_request._response_info(response, with_file_path=True)

    assert is_binary is False
    assert file_path.parent == Path(tempfile.gettempdir()) / "APIRequestComponent"
    assert file_path.name.endswith("thisfile.txt")


async def test_response_info_default_filename(api_request):
    response = Mock()
    response.headers = {"Content-Type": "text/plain"}
    response.request = Mock()
    response.request.url = "https://example.com/testfile"

    is_binary, file_path = await api_request._response_info(response, with_file_path=True)

    assert is_binary is False
    assert file_path.parent == Path(tempfile.gettempdir()) / "APIRequestComponent"
    assert file_path.name.endswith("testfile.txt")
