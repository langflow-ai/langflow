import os
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest
import respx
from dictdiffer import diff
from httpx import Response

from langflow.components import data


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
    results = await api_request.build(method=method, urls=urls)

    # Assertions
    assert len(results) == len(urls)


@patch("langflow.components.data.Directory.parallel_load_records")
@patch("langflow.components.data.Directory.retrieve_file_paths")
@patch("langflow.components.data.DirectoryComponent.resolve_path")
def test_directory_component_build_with_multithreading(
    mock_resolve_path, mock_retrieve_file_paths, mock_parallel_load_records
):
    # Arrange
    directory_component = data.DirectoryComponent()
    path = os.path.dirname(os.path.abspath(__file__))
    depth = 1
    max_concurrency = 2
    load_hidden = False
    recursive = True
    silent_errors = False
    use_multithreading = True

    mock_resolve_path.return_value = path
    mock_retrieve_file_paths.return_value = [
        os.path.join(path, file) for file in os.listdir(path) if file.endswith(".py")
    ]
    mock_parallel_load_records.return_value = [Mock()]

    # Act
    directory_component.build(
        path,
        depth,
        max_concurrency,
        load_hidden,
        recursive,
        silent_errors,
        use_multithreading,
    )

    # Assert
    mock_resolve_path.assert_called_once_with(path)
    mock_retrieve_file_paths.assert_called_once_with(path, load_hidden, recursive, depth)
    mock_parallel_load_records.assert_called_once_with(
        mock_retrieve_file_paths.return_value, silent_errors, max_concurrency
    )


def test_directory_without_mocks():
    directory_component = data.DirectoryComponent()
    from langflow.initial_setup import setup
    from langflow.initial_setup.setup import load_starter_projects

    _, projects = zip(*load_starter_projects())
    # the setup module has a folder where the projects are stored
    # the contents of that folder are in the projects variable
    # the directory component can be used to load the projects
    # and we can validate if the contents are the same as the projects variable
    setup_path = Path(setup.__file__).parent / "starter_projects"
    results = directory_component.build(str(setup_path), use_multithreading=False)
    assert len(results) == len(projects)
    # each result is a Record that contains the content attribute
    # each are dict that are exactly the same as one of the projects
    for i, result in enumerate(results):
        assert result.text in projects, list(diff(result.text, projects[i]))

    # in ../docs/docs/components there are many mdx files
    # check if the directory component can load them
    # just check if the number of results is the same as the number of files
    docs_path = Path(__file__).parent.parent / "docs" / "docs" / "components"
    results = directory_component.build(str(docs_path), use_multithreading=False)
    docs_files = list(docs_path.glob("*.mdx"))
    assert len(results) == len(docs_files)


def test_url_component():
    url_component = data.URLComponent()
    # the url component can be used to load the contents of a website
    records = url_component.build(["https://langflow.org"])
    assert all(record.data for record in records)
    assert all(record.text for record in records)
    assert all(record.source for record in records)
