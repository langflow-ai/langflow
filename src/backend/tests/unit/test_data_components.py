import tempfile
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import httpx
import pytest
import respx
from httpx import Response
from langflow.components import data
from langflow.schema import DataFrame, Message


@pytest.fixture
def api_request():
    # This fixture provides an instance of APIRequest for each test case
    return data.APIRequestComponent()


@respx.mock
async def test_successful_get_request(api_request):
    # Mocking a successful GET request
    url = "https://example.com/api/test"
    method = "GET"
    mock_response = {"success": True}
    respx.get(url).mock(return_value=Response(200, json=mock_response))

    # Making the request
    result = await api_request.make_request(
        client=httpx.AsyncClient(),
        method=method,
        url=url,
        include_httpx_metadata=True,
    )

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


@respx.mock
async def test_failed_request(api_request):
    # Mocking a failed GET request
    url = "https://example.com/api/test"
    method = "GET"
    respx.get(url).mock(return_value=Response(404))

    # Making the request
    result = await api_request.make_request(
        client=httpx.AsyncClient(), method=method, url=url, include_httpx_metadata=True
    )

    # Assertions
    assert result.data["status_code"] == 404


@respx.mock
async def test_timeout(api_request):
    # Mocking a timeout
    url = "https://example.com/api/timeout"
    method = "GET"
    respx.get(url).mock(side_effect=httpx.TimeoutException(message="Timeout", request=None))

    # Making the request
    result = await api_request.make_request(
        client=httpx.AsyncClient(), method=method, url=url, timeout=1, include_httpx_metadata=True
    )

    # Assertions
    assert result.data["status_code"] == 408
    assert result.data["error"] == "Request timed out"


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


@patch("langflow.components.data.directory.parallel_load_data")
@patch("langflow.components.data.directory.retrieve_file_paths")
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
        (Path(temp_dir) / "test.txt").write_text("test", encoding="utf-8")
        # also add a json file
        (Path(temp_dir) / "test.json").write_text('{"test": "test"}', encoding="utf-8")

        directory_component.set_attributes({"path": str(temp_dir), "use_multithreading": False})
        results = directory_component.load_directory()
        assert len(results) == 2
        values = ["test", '{"test":"test"}']
        assert all(result.text in values for result in results), [
            (len(result.text), len(val)) for result, val in zip(results, values, strict=True)
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
    data_ = url_component.fetch_content()
    assert all(value.data for value in data_)
    assert all(value.text for value in data_)
    assert all(value.source for value in data_)


@pytest.mark.parametrize(
    ("format_type", "expected_content"),
    [
        ("Text", "test content"),
        ("Raw HTML", "<html>test content</html>"),
    ],
)
@patch("langchain_community.document_loaders.AsyncHtmlLoader.load")
@patch("langchain_community.document_loaders.WebBaseLoader.load")
def test_url_component_formats(mock_web_load, mock_html_load, format_type, expected_content):
    """Test URL component with different format types."""
    url_component = data.URLComponent()
    url_component.set_attributes({"urls": ["https://example.com"], "format": format_type})

    # Mock the appropriate loader based on format
    if format_type == "Raw HTML":
        mock_html_load.return_value = [Mock(page_content=expected_content, metadata={"source": "https://example.com"})]
        mock_web_load.assert_not_called()
    else:
        mock_web_load.return_value = [Mock(page_content=expected_content, metadata={"source": "https://example.com"})]
        mock_html_load.assert_not_called()

    # Test fetch_content
    content = url_component.fetch_content()
    assert len(content) == 1
    assert content[0].text == expected_content
    assert content[0].source == "https://example.com"


@patch("langchain_community.document_loaders.WebBaseLoader.load")
def test_url_component_as_dataframe(mock_web_load):
    """Test URL component's as_dataframe method."""
    url_component = data.URLComponent()
    urls = ["https://example1.com", "https://example2.com"]
    url_component.set_attributes({"urls": urls})

    # Mock the loader response
    mock_web_load.return_value = [
        Mock(page_content="content1", metadata={"source": urls[0]}),
        Mock(page_content="content2", metadata={"source": urls[1]}),
    ]

    # Test as_dataframe
    data_frame = url_component.as_dataframe()
    assert isinstance(data_frame, DataFrame)
    assert len(data_frame) == 2
    assert list(data_frame.columns) == ["text", "source"]
    assert data_frame.iloc[0]["text"] == "content1"
    assert data_frame.iloc[0]["source"] == urls[0]
    assert data_frame.iloc[1]["text"] == "content2"
    assert data_frame.iloc[1]["source"] == urls[1]


def test_url_component_invalid_url():
    """Test URL component with invalid URLs."""
    url_component = data.URLComponent()
    url_component.set_attributes({"urls": ["not_a_valid_url"]})
    with pytest.raises(ValueError, match="Invalid URL"):
        url_component.fetch_content()


@patch("langchain_community.document_loaders.WebBaseLoader.load")
def test_url_component_fetch_content_text(mock_web_load):
    """Test URL component's fetch_content_text method."""
    url_component = data.URLComponent()
    url_component.set_attributes({"urls": ["https://example.com"]})

    # Mock the loader response
    mock_web_load.return_value = [Mock(page_content="test content", metadata={"source": "https://example.com"})]

    # Test fetch_content_text
    message = url_component.fetch_content_text()
    assert isinstance(message, Message)
    assert message.text == "test content"


@patch("langchain_community.document_loaders.WebBaseLoader.load")
def test_url_component_multiple_urls(mock_web_load):
    """Test URL component with multiple URLs."""
    url_component = data.URLComponent()
    urls = ["https://example1.com", "https://example2.com", "https://example3.com"]
    url_component.set_attributes({"urls": urls})

    # Mock the loader response
    mock_web_load.return_value = [
        Mock(page_content=f"content{i}", metadata={"source": url}) for i, url in enumerate(urls, 1)
    ]

    # Test fetch_content
    content = url_component.fetch_content()
    assert len(content) == 3
    for i, (item, url) in enumerate(zip(content, urls, strict=False)):
        assert item.text == f"content{i+1}"
        assert item.source == url
