import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, ANY

import httpx
import pytest
import respx
from httpx import Response

from langflow.components import data


@pytest.fixture
def api_request():
    # This fixture provides an instance of APIRequest for each test case
    return data.APIRequestComponent()


@pytest.mark.asyncio
@respx.mock
async def test_successful_get_request(api_request):
    # Mocking a successful GET request
    url = "https://example.com/api/test"
    method = "GET"
    mock_response = {"success": True}
    respx.get(url).mock(return_value=Response(200, json=mock_response))

    # Making the request
    result = await api_request.make_request(client=httpx.AsyncClient(), method=method, url=url)

    # Assertions
    assert result.data["status_code"] == 200
    assert result.data["result"] == mock_response


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
    assert new_build_config["headers"]["value"] == {"Content-Type": "application/json"}
    assert new_build_config["body"]["value"] == {"key": "value"}


@pytest.mark.asyncio
@respx.mock
async def test_failed_request(api_request):
    # Mocking a failed GET request
    url = "https://example.com/api/test"
    method = "GET"
    respx.get(url).mock(return_value=Response(404))

    # Making the request
    result = await api_request.make_request(client=httpx.AsyncClient(), method=method, url=url)

    # Assertions
    assert result.data["status_code"] == 404


@pytest.mark.asyncio
@respx.mock
async def test_timeout(api_request):
    # Mocking a timeout
    url = "https://example.com/api/timeout"
    method = "GET"
    respx.get(url).mock(side_effect=httpx.TimeoutException(message="Timeout", request=None))

    # Making the request
    result = await api_request.make_request(client=httpx.AsyncClient(), method=method, url=url, timeout=1)

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
    api_request.set_attributes(
        {
            "method": method,
            "urls": urls,
        }
    )
    results = await api_request.make_requests()

    # Assertions
    assert len(results) == len(urls)


@patch("langflow.components.data.Directory.parallel_load_data")
@patch("langflow.components.data.Directory.retrieve_file_paths")
@patch("langflow.components.data.DirectoryComponent.resolve_path")
def test_directory_component_build_with_multithreading(
    mock_resolve_path, mock_retrieve_file_paths, mock_parallel_load_data
):
    # Arrange
    directory_component = data.DirectoryComponent()
    path = Path(__file__).resolve().parent
    depth = 1
    max_concurrency = 2
    load_hidden = False
    recursive = True
    silent_errors = False
    use_multithreading = True

    mock_resolve_path.return_value = str(path)

    mock_retrieve_file_paths.return_value = [str(p) for p in path.iterdir() if p.suffix == ".py"]
    mock_parallel_load_data.return_value = [Mock()]

    # Act
    directory_component.set_attributes(
        {
            "path": str(path),
            "depth": depth,
            "max_concurrency": max_concurrency,
            "load_hidden": load_hidden,
            "recursive": recursive,
            "silent_errors": silent_errors,
            "use_multithreading": use_multithreading,
        }
    )
    directory_component.load_directory()

    # Assert
    mock_resolve_path.assert_called_once_with(str(path))
    mock_retrieve_file_paths.assert_called_once_with(
        str(path), load_hidden=load_hidden, recursive=recursive, depth=depth, types=ANY
    )
    mock_parallel_load_data.assert_called_once_with(
        mock_retrieve_file_paths.return_value, silent_errors=silent_errors, max_concurrency=max_concurrency
    )


def test_directory_without_mocks():
    directory_component = data.DirectoryComponent()

    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "test.txt").write_text("test")
        # also add a json file
        (Path(temp_dir) / "test.json").write_text('{"test": "test"}')

        directory_component.set_attributes({"path": str(temp_dir), "use_multithreading": False})
        results = directory_component.load_directory()
        assert len(results) == 2
        values = ["test", '{"test":"test"}']
        assert all(result.text in values for result in results), [
            (len(result.text), len(val)) for result, val in zip(results, values)
        ]

    # in ../docs/docs/components there are many mdx files
    # check if the directory component can load them
    # just check if the number of results is the same as the number of files
    directory_component = data.DirectoryComponent()
    docs_path = Path(__file__).parent.parent.parent.parent.parent / "docs" / "docs" / "Components"
    directory_component.set_attributes({"path": str(docs_path), "use_multithreading": False})
    results = directory_component.load_directory()
    docs_files = list(docs_path.glob("*.md")) + list(docs_path.glob("*.json"))
    assert len(results) == len(docs_files)


def test_url_component():
    url_component = data.URLComponent()
    url_component.set_attributes({"urls": ["https://langflow.org"]})
    # the url component can be used to load the contents of a website
    _data = url_component.fetch_content()
    assert all(value.data for value in _data)
    assert all(value.text for value in _data)
    assert all(value.source for value in _data)
