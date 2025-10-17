from unittest.mock import Mock, patch

import pytest
from lfx.components.data import URLComponent
from lfx.schema import DataFrame
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestURLComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return URLComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "urls": ["https://google.com"],
            "format": "Text",
            "max_depth": 1,
            "prevent_outside": True,
            "use_async": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return [
            {"version": "1.0.19", "module": "data", "file_name": "URL"},
            {"version": "1.1.0", "module": "data", "file_name": "url"},
            {"version": "1.1.1", "module": "data", "file_name": "url"},
            {"version": "1.2.0", "module": "data", "file_name": "url"},
        ]

    @pytest.fixture
    def mock_recursive_loader(self):
        """Mock the RecursiveUrlLoader.load method."""
        with patch("langchain_community.document_loaders.RecursiveUrlLoader.load") as mock:
            yield mock

    def test_url_component_basic_functionality(self, mock_recursive_loader):
        """Test basic URLComponent functionality."""
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"], "max_depth": 2})

        mock_doc = Mock(
            page_content="test content",
            metadata={
                "source": "https://example.com",
                "title": "Test Page",
                "description": "Test Description",
                "content_type": "text/html",
                "language": "en",
            },
        )
        mock_recursive_loader.return_value = [mock_doc]

        data_frame = component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        assert len(data_frame) == 1

        row = data_frame.iloc[0]
        assert row["text"] == "test content"
        assert row["url"] == "https://example.com"
        assert row["title"] == "Test Page"
        assert row["description"] == "Test Description"
        assert row["content_type"] == "text/html"
        assert row["language"] == "en"

    def test_url_component_multiple_urls(self, mock_recursive_loader):
        """Test URLComponent with multiple URL inputs."""
        # Setup component with multiple URLs
        component = URLComponent()
        urls = ["https://example1.com", "https://example2.com"]
        component.set_attributes({"urls": urls})

        # Create mock documents for each URL
        mock_docs = [
            Mock(
                page_content="Content from first URL",
                metadata={
                    "source": "https://example1.com",
                    "title": "First Page",
                    "description": "First Description",
                    "content_type": "text/html",
                    "language": "en",
                },
            ),
            Mock(
                page_content="Content from second URL",
                metadata={
                    "source": "https://example2.com",
                    "title": "Second Page",
                    "description": "Second Description",
                    "content_type": "text/html",
                    "language": "en",
                },
            ),
        ]

        # Configure mock to return both documents
        mock_recursive_loader.return_value = mock_docs

        # Execute component
        result = component.fetch_content()

        # Verify results
        assert isinstance(result, DataFrame)
        assert len(result) == 4

        # Verify first URL content
        first_row = result.iloc[0]
        assert first_row["text"] == "Content from first URL"
        assert first_row["url"] == "https://example1.com"
        assert first_row["title"] == "First Page"
        assert first_row["description"] == "First Description"

        # Verify second URL content
        second_row = result.iloc[1]
        assert second_row["text"] == "Content from second URL"
        assert second_row["url"] == "https://example2.com"
        assert second_row["title"] == "Second Page"
        assert second_row["description"] == "Second Description"

    def test_url_component_format_options(self, mock_recursive_loader):
        """Test URLComponent with different format options."""
        component = URLComponent()

        # Test with Text format
        component.set_attributes({"urls": ["https://example.com"], "format": "Text"})
        mock_recursive_loader.return_value = [
            Mock(
                page_content="extracted text",
                metadata={
                    "source": "https://example.com",
                    "title": "Test Page",
                    "description": "Test Description",
                    "content_type": "text/html",
                    "language": "en",
                },
            )
        ]
        data_frame = component.fetch_content()
        assert data_frame.iloc[0]["text"] == "extracted text"
        assert data_frame.iloc[0]["content_type"] == "text/html"

        # Test with HTML format
        component.set_attributes({"urls": ["https://example.com"], "format": "HTML"})
        mock_recursive_loader.return_value = [
            Mock(
                page_content="<html>raw html</html>",
                metadata={
                    "source": "https://example.com",
                    "title": "Test Page",
                    "description": "Test Description",
                    "content_type": "text/html",
                    "language": "en",
                },
            )
        ]
        data_frame = component.fetch_content()
        assert data_frame.iloc[0]["text"] == "<html>raw html</html>"
        assert data_frame.iloc[0]["content_type"] == "text/html"

    def test_url_component_missing_metadata(self, mock_recursive_loader):
        """Test URLComponent with missing metadata fields."""
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"]})

        mock_doc = Mock(
            page_content="test content",
            metadata={"source": "https://example.com"},  # Only source is provided
        )
        mock_recursive_loader.return_value = [mock_doc]

        data_frame = component.fetch_content()
        row = data_frame.iloc[0]
        assert row["text"] == "test content"
        assert row["url"] == "https://example.com"
        assert row["title"] == ""  # Default empty string
        assert row["description"] == ""  # Default empty string
        assert row["content_type"] == ""  # Default empty string
        assert row["language"] == ""  # Default empty string

    def test_url_component_error_handling(self, mock_recursive_loader):
        """Test error handling in URLComponent."""
        component = URLComponent()

        # Test empty URLs
        component.set_attributes({"urls": []})
        with pytest.raises(ValueError, match="Error loading documents:"):
            component.fetch_content()

        # Test request exception
        component.set_attributes({"urls": ["https://example.com"]})
        mock_recursive_loader.side_effect = Exception("Connection error")
        with pytest.raises(ValueError, match="Error loading documents:"):
            component.fetch_content()

        # Test no documents found
        mock_recursive_loader.side_effect = None
        mock_recursive_loader.return_value = []
        with pytest.raises(ValueError, match="Error loading documents:"):
            component.fetch_content()

    def test_url_component_ensure_url(self):
        """Test URLComponent's ensure_url method."""
        component = URLComponent()

        # Test URL without protocol
        url = "example.com"
        fixed_url = component.ensure_url(url)
        assert fixed_url == "https://example.com"

        # Test URL with protocol
        url = "https://example.com"
        fixed_url = component.ensure_url(url)
        assert fixed_url == "https://example.com"

        # Test URL with https protocol
        url = "https://example.com"
        fixed_url = component.ensure_url(url)
        assert fixed_url == "https://example.com"

        # Test invalid URL
        with pytest.raises(ValueError, match="Invalid URL"):
            component.ensure_url("not a url")

    def test_url_component_with_custom_headers(self, mock_recursive_loader):
        """Test URLComponent with custom headers."""
        component = URLComponent()
        custom_headers = [
            {"key": "User-Agent", "value": "CustomBot/1.0"},
            {"key": "Authorization", "value": "Bearer token123"},
        ]
        component.set_attributes({"urls": ["https://example.com"], "headers": custom_headers})

        mock_doc = Mock(
            page_content="test content",
            metadata={
                "source": "https://example.com",
                "title": "Test Page",
                "description": "Test Description",
                "content_type": "text/html",
                "language": "en",
            },
        )
        mock_recursive_loader.return_value = [mock_doc]

        data_frame = component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        assert len(data_frame) == 1

        # Verify the loader was called (headers are passed internally)
        mock_recursive_loader.assert_called()

    def test_url_component_with_timeout(self, mock_recursive_loader):
        """Test URLComponent with custom timeout."""
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"], "timeout": 60})

        mock_doc = Mock(
            page_content="test content",
            metadata={
                "source": "https://example.com",
                "title": "Test Page",
                "description": "Test Description",
                "content_type": "text/html",
                "language": "en",
            },
        )
        mock_recursive_loader.return_value = [mock_doc]

        data_frame = component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        assert component.timeout == 60

    def test_url_component_with_chunking(self, mock_recursive_loader):
        """Test URLComponent with chunking enabled."""
        component = URLComponent()
        component.set_attributes(
            {"urls": ["https://example.com"], "chunk_size": 100, "chunk_overlap": 20, "max_total_chars": 0}
        )

        # Create a document with content longer than chunk_size
        long_content = "This is a test. " * 50  # Create content > 100 chars
        mock_doc = Mock(
            page_content=long_content,
            metadata={
                "source": "https://example.com",
                "title": "Test Page",
                "description": "Test Description",
                "content_type": "text/html",
                "language": "en",
            },
        )
        mock_recursive_loader.return_value = [mock_doc]

        data_frame = component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        # Should have multiple chunks since content is longer than chunk_size
        assert len(data_frame) > 1
        # Verify chunk metadata exists
        first_row = data_frame.iloc[0]
        assert "chunk_index" in first_row
        assert "total_chunks" in first_row

    def test_url_component_without_chunking(self, mock_recursive_loader):
        """Test URLComponent with chunking disabled."""
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"], "chunk_size": 0})

        mock_doc = Mock(
            page_content="test content",
            metadata={
                "source": "https://example.com",
                "title": "Test Page",
                "description": "Test Description",
                "content_type": "text/html",
                "language": "en",
            },
        )
        mock_recursive_loader.return_value = [mock_doc]

        data_frame = component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        assert len(data_frame) == 1
        # Verify no chunk metadata
        first_row = data_frame.iloc[0]
        assert "chunk_index" not in first_row
        assert "total_chunks" not in first_row

    def test_url_component_max_total_chars(self, mock_recursive_loader):
        """Test URLComponent respects max_total_chars limit with chunking."""
        component = URLComponent()
        component.set_attributes(
            {"urls": ["https://example.com"], "max_total_chars": 150, "chunk_size": 50, "chunk_overlap": 0}
        )

        # Create documents with content longer than max_total_chars
        long_content = "a" * 200
        mock_doc = Mock(
            page_content=long_content,
            metadata={
                "source": "https://example.com",
                "title": "Test Page",
                "description": "Test Description",
                "content_type": "text/html",
                "language": "en",
            },
        )
        mock_recursive_loader.return_value = [mock_doc]

        data_frame = component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        # Content should be limited by max_total_chars when chunking is enabled
        total_chars = sum(len(row["text"]) for _, row in data_frame.iterrows())
        assert total_chars <= 150

    def test_url_component_continue_on_failure(self, mock_recursive_loader):
        """Test URLComponent continues on failure when enabled."""
        component = URLComponent()
        urls = ["https://example1.com", "https://example2.com"]
        component.set_attributes({"urls": urls, "continue_on_failure": True})

        # First URL fails, second succeeds
        mock_doc = Mock(
            page_content="Content from second URL",
            metadata={
                "source": "https://example2.com",
                "title": "Second Page",
                "description": "Second Description",
                "content_type": "text/html",
                "language": "en",
            },
        )

        # Mock to fail on first call with RequestException, succeed on second
        import requests

        mock_recursive_loader.side_effect = [requests.exceptions.RequestException("Connection error"), [mock_doc]]

        data_frame = component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        # Should have content from the second URL even though first failed
        assert len(data_frame) > 0

    def test_url_component_check_response_status(self, mock_recursive_loader):
        """Test URLComponent with check_response_status enabled."""
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"], "check_response_status": True})

        mock_doc = Mock(
            page_content="test content",
            metadata={
                "source": "https://example.com",
                "title": "Test Page",
                "description": "Test Description",
                "content_type": "text/html",
                "language": "en",
            },
        )
        mock_recursive_loader.return_value = [mock_doc]

        data_frame = component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        assert component.check_response_status is True

    def test_url_component_autoset_encoding(self, mock_recursive_loader):
        """Test URLComponent with autoset_encoding enabled."""
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"], "autoset_encoding": True})

        mock_doc = Mock(
            page_content="test content with special chars: \u00e9\u00e0\u00fc",
            metadata={
                "source": "https://example.com",
                "title": "Test Page",
                "description": "Test Description",
                "content_type": "text/html",
                "language": "en",
            },
        )
        mock_recursive_loader.return_value = [mock_doc]

        data_frame = component.fetch_content()
        assert isinstance(data_frame, DataFrame)
        assert component.autoset_encoding is True

    def test_url_component_fetch_content_as_message(self, mock_recursive_loader):
        """Test URLComponent's fetch_content_as_message method."""
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"]})

        mock_doc = Mock(
            page_content="test content",
            metadata={
                "source": "https://example.com",
                "title": "Test Page",
                "description": "Test Description",
                "content_type": "text/html",
                "language": "en",
            },
        )
        mock_recursive_loader.return_value = [mock_doc]

        message = component.fetch_content_as_message()
        assert isinstance(message, Message)
        assert "test content" in message.text
        assert "data" in message.data
