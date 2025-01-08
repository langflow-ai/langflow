import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest
import respx
from httpx import Response
from langflow.components import data
from langflow.schema import DataFrame, Message
from langflow.schema.data import Data


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
            "types": ["py"],  # Add file types without dots
        }
    )
    directory_component.load_directory()

    # Assert
    mock_resolve_path.assert_called_once_with(str(path))
    mock_retrieve_file_paths.assert_called_once_with(
        mock_resolve_path.return_value,
        depth=depth,
        recursive=recursive,
        types=["py"],
        load_hidden=load_hidden,
    )
    mock_parallel_load_data.assert_called_once_with(
        mock_retrieve_file_paths.return_value,
        max_concurrency=max_concurrency,
        silent_errors=silent_errors,
    )


def test_directory_without_mocks():
    directory_component = data.DirectoryComponent()

    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / "test.txt").write_text("test", encoding="utf-8")
        # also add a json file
        (Path(temp_dir) / "test.json").write_text('{"test": "test"}', encoding="utf-8")

        directory_component.set_attributes(
            {
                "path": str(temp_dir),
                "use_multithreading": False,
                "silent_errors": False,  # Add silent_errors parameter
                "types": ["txt", "json"],  # Add file types without dots
            }
        )
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
    directory_component.set_attributes(
        {
            "path": str(docs_path),
            "use_multithreading": False,
            "silent_errors": False,  # Add silent_errors parameter
            "types": ["md", "json"],  # Add file types without dots
        }
    )
    results = directory_component.load_directory()
    docs_files = list(docs_path.glob("*.md")) + list(docs_path.glob("*.json"))
    assert len(results) == len(docs_files)


def test_directory_as_dataframe():
    """Test DirectoryComponent's as_dataframe method."""
    directory_component = data.DirectoryComponent()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files with different content
        files_content = {
            "file1.txt": "content1",
            "file2.json": '{"key": "content2"}',
            "file3.md": "# content3",
        }

        for filename, content in files_content.items():
            (Path(temp_dir) / filename).write_text(content, encoding="utf-8")

        directory_component.set_attributes(
            {
                "path": str(temp_dir),
                "use_multithreading": False,
                "types": ["txt", "json", "md"],
                "silent_errors": False,
            }
        )

        # Test as_dataframe
        data_frame = directory_component.as_dataframe()

        # Verify DataFrame structure
        assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
        assert len(data_frame) == 3, f"Expected DataFrame with 3 rows, got {len(data_frame)}"

        # Check column names
        expected_columns = ["text", "file_path"]
        actual_columns = list(data_frame.columns)
        assert set(expected_columns).issubset(
            set(actual_columns)
        ), f"Missing required columns. Expected at least {expected_columns}, got {actual_columns}"

        # Verify content matches input files
        texts = data_frame["text"].tolist()
        # For JSON files, the content is parsed and re-serialized
        expected_content = {
            "file1.txt": "content1",
            "file2.json": '{"key":"content2"}',  # JSON is re-serialized without spaces
            "file3.md": "# content3",
        }
        missing_content = [content for content in expected_content.values() if content not in texts]
        assert not missing_content, f"Missing expected content in DataFrame: {missing_content}"

        # Verify file paths are correct
        file_paths = data_frame["file_path"].tolist()
        expected_paths = [str(Path(temp_dir) / filename) for filename in files_content]
        missing_paths = [path for path in expected_paths if not any(path in fp for fp in file_paths)]
        assert not missing_paths, f"Missing expected file paths in DataFrame: {missing_paths}"


def test_directory_with_depth():
    """Test DirectoryComponent with different depth settings."""
    directory_component = data.DirectoryComponent()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a nested directory structure
        base_dir = Path(temp_dir)
        (base_dir / "level1").mkdir()
        (base_dir / "level1" / "level2").mkdir()

        # Create files at different levels
        (base_dir / "root.txt").write_text("root", encoding="utf-8")
        (base_dir / "level1" / "level1.txt").write_text("level1", encoding="utf-8")
        (base_dir / "level1" / "level2" / "level2.txt").write_text("level2", encoding="utf-8")

        # Test non-recursive (only root)
        directory_component.set_attributes(
            {
                "path": str(temp_dir),
                "recursive": False,  # Set recursive to False to get only root files
                "use_multithreading": False,
                "silent_errors": False,
                "types": ["txt"],
            }
        )
        results_root = directory_component.load_directory()
        assert len(results_root) == 1, (
            "With recursive=False, expected 1 file (root.txt),"
            f" got {len(results_root)} files: {[d.data['file_path'] for d in results_root]}"
        )
        assert results_root[0].text == "root", f"Expected root file content 'root', got '{results_root[0].text}'"

        # Test recursive with all files
        directory_component.set_attributes(
            {
                "path": str(temp_dir),
                "recursive": True,
                "use_multithreading": False,
                "silent_errors": False,
                "types": ["txt"],
            }
        )
        results_all = directory_component.load_directory()
        assert len(results_all) == 3, (
            "With recursive=True, expected 3 files (all files), "
            f"got {len(results_all)} files: {[d.data['file_path'] for d in results_all]}"
        )
        texts = sorted([r.text for r in results_all])
        expected_texts = sorted(["root", "level1", "level2"])
        assert texts == expected_texts, f"Expected texts {expected_texts}, got {texts}"


def test_directory_with_types():
    """Test DirectoryComponent with different file type filters."""
    directory_component = data.DirectoryComponent()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create files with different extensions
        files = {
            "test.txt": "text content",
            "test.json": '{"key": "value"}',
            "test.md": "# markdown",
            "test.csv": "col1,col2\nval1,val2",
        }

        for filename, content in files.items():
            (Path(temp_dir) / filename).write_text(content, encoding="utf-8")

        # Test with specific file types
        for file_types in (["txt"], ["json", "md"], ["csv"]):
            directory_component.set_attributes(
                {
                    "path": str(temp_dir),
                    "types": file_types,
                    "use_multithreading": False,
                    "silent_errors": False,  # Add silent_errors parameter
                }
            )
            results = directory_component.load_directory()

            # Verify only files of specified types are loaded
            assert len(results) == len([f for f in files if any(f.endswith(f".{t}") for t in file_types)])
            for result in results:
                assert any(result.data["file_path"].endswith(f".{t}") for t in file_types)


def test_directory_with_hidden_files():
    """Test DirectoryComponent with hidden files."""
    directory_component = data.DirectoryComponent()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create regular and hidden files
        (Path(temp_dir) / "regular.txt").write_text("regular", encoding="utf-8")
        (Path(temp_dir) / ".hidden.txt").write_text("hidden", encoding="utf-8")

        # Test without loading hidden files
        directory_component.set_attributes(
            {
                "path": str(temp_dir),
                "load_hidden": False,
                "use_multithreading": False,
                "silent_errors": False,  # Add silent_errors parameter
                "types": ["txt"],  # Add file types without dots
            }
        )
        results = directory_component.load_directory()
        assert len(results) == 1
        assert results[0].text == "regular"

        # Test with loading hidden files
        directory_component.set_attributes({"load_hidden": True})
        results = directory_component.load_directory()
        assert len(results) == 2
        texts = [r.text for r in results]
        assert "regular" in texts
        assert "hidden" in texts


@patch("langflow.components.data.directory.parallel_load_data")
def test_directory_with_multithreading(mock_parallel_load):
    """Test DirectoryComponent with multithreading enabled."""
    directory_component = data.DirectoryComponent()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        (Path(temp_dir) / "test1.txt").write_text("content1", encoding="utf-8")
        (Path(temp_dir) / "test2.txt").write_text("content2", encoding="utf-8")

        # Mock parallel_load_data to return some test data
        mock_data = [
            Data(text="content1", data={"file_path": str(Path(temp_dir) / "test1.txt")}),
            Data(text="content2", data={"file_path": str(Path(temp_dir) / "test2.txt")}),
        ]
        mock_parallel_load.return_value = mock_data

        # Test with multithreading enabled
        directory_component.set_attributes(
            {
                "path": str(temp_dir),
                "use_multithreading": True,
                "max_concurrency": 2,
                "types": ["txt"],  # Specify file types to ensure files are found
                "recursive": True,  # Enable recursive search
                "silent_errors": False,  # Add silent_errors parameter
            }
        )
        results = directory_component.load_directory()

        # Verify parallel_load_data was called with correct parameters
        (
            mock_parallel_load.assert_called_once(),
            "parallel_load_data should be called exactly once when multithreading is enabled",
        )
        call_args = mock_parallel_load.call_args[1]
        assert call_args["max_concurrency"] == 2, f"Expected max_concurrency=2, got {call_args.get('max_concurrency')}"
        assert (
            call_args["silent_errors"] is False
        ), f"Expected silent_errors=False, got {call_args.get('silent_errors')}"

        # Verify results
        assert len(results) == 2, f"Expected 2 results, got {len(results)}: {[r.data['file_path'] for r in results]}"
        assert all(
            isinstance(r, Data) for r in results
        ), f"All results should be Data objects, got types: {[type(r) for r in results]}"

        actual_texts = [r.text for r in results]
        expected_texts = ["content1", "content2"]
        assert actual_texts == expected_texts, f"Expected texts {expected_texts}, got {actual_texts}"


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
