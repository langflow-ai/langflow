from unittest.mock import Mock, patch

import pytest
from lfx.components.data_source.url import URLComponent
from lfx.schema import DataFrame
from lfx.utils.ssrf_protection import SSRFProtectionError

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

    def test_url_component_text_format(self, mock_recursive_loader):
        """Test URLComponent with text format."""
        component = URLComponent()
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

    def test_url_component_html_format(self, mock_recursive_loader):
        """Test URLComponent with different format options."""
        component = URLComponent()

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

    def test_url_component_markdown_format(self, mock_recursive_loader):
        """Test URLComponent with Markdown format."""
        component = URLComponent()

        component.set_attributes({"urls": ["https://example.com"], "format": "Markdown"})
        mock_recursive_loader.return_value = [
            Mock(
                page_content="# Header\n\nParagraph with a [link](https://link.com).\n",
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
        assert data_frame.iloc[0]["text"] == "# Header\n\nParagraph with a [link](https://link.com).\n"
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


class TestURLComponentSSRFProtection:
    """Test SSRF protection in URLComponent."""

    def test_ssrf_validation_called_on_ensure_url(self):
        """Test that SSRF validation is called when ensuring URL."""
        component = URLComponent()

        with patch("lfx.components.data_source.url.validate_url_for_ssrf") as mock_validate:
            component.ensure_url("https://example.com")
            mock_validate.assert_called_once_with("https://example.com", warn_only=True)

    def test_ssrf_blocks_localhost(self):
        """Test that localhost is blocked when SSRF validation raises."""
        component = URLComponent()

        with patch("lfx.components.data_source.url.validate_url_for_ssrf") as mock_validate:
            mock_validate.side_effect = SSRFProtectionError("Access to IP address 127.0.0.1 is blocked")

            with pytest.raises(ValueError, match="SSRF Protection"):
                component.ensure_url("http://127.0.0.1:8080")

    def test_ssrf_blocks_private_ip(self):
        """Test that private IPs are blocked when SSRF validation raises."""
        component = URLComponent()

        with patch("lfx.components.data_source.url.validate_url_for_ssrf") as mock_validate:
            mock_validate.side_effect = SSRFProtectionError("Access to IP address 192.168.1.1 is blocked")

            with pytest.raises(ValueError, match="SSRF Protection"):
                component.ensure_url("http://192.168.1.1/admin")

    def test_ssrf_blocks_metadata_endpoint(self):
        """Test that cloud metadata endpoints are blocked when SSRF validation raises."""
        component = URLComponent()

        with patch("lfx.components.data_source.url.validate_url_for_ssrf") as mock_validate:
            mock_validate.side_effect = SSRFProtectionError("Access to IP address 169.254.169.254 is blocked")

            with pytest.raises(ValueError, match="SSRF Protection"):
                component.ensure_url("http://169.254.169.254/latest/meta-data/")

    def test_ssrf_allows_public_urls(self):
        """Test that public URLs are allowed when validation passes."""
        component = URLComponent()

        with patch("lfx.components.data_source.url.validate_url_for_ssrf") as mock_validate:
            mock_validate.return_value = None

            url = component.ensure_url("https://www.google.com")
            assert url == "https://www.google.com"
            mock_validate.assert_called_once()

    def test_ssrf_warn_only_mode(self):
        """Test that warn_only=True is passed to validation."""
        component = URLComponent()

        with patch("lfx.components.data_source.url.validate_url_for_ssrf") as mock_validate:
            component.ensure_url("https://example.com")

            # Verify warn_only=True is passed (current behavior for backwards compatibility)
            mock_validate.assert_called_with("https://example.com", warn_only=True)

    def test_ssrf_protection_in_fetch_content(self):
        """Test that SSRF protection is applied during fetch_content."""
        component = URLComponent()
        component.set_attributes({"urls": ["http://127.0.0.1:9999"]})

        with patch("lfx.components.data_source.url.validate_url_for_ssrf") as mock_validate:
            mock_validate.side_effect = SSRFProtectionError("Access to IP address 127.0.0.1 is blocked")

            with pytest.raises(ValueError, match="SSRF Protection"):
                component.fetch_content()
