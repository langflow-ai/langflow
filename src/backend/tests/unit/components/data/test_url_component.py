from unittest.mock import Mock, patch

import pytest
import respx
from httpx import Response
from langflow.components.data import URLComponent
from langflow.schema import DataFrame, Message

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
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return [
            {"version": "1.0.19", "module": "data", "file_name": "URL"},
            {"version": "1.1.0", "module": "data", "file_name": "url"},
            {"version": "1.1.1", "module": "data", "file_name": "url"},
        ]

    @pytest.fixture
    def mock_web_load(self):
        """Mock the WebBaseLoader.load method."""
        with patch("langchain_community.document_loaders.WebBaseLoader.load") as mock:
            yield mock

    def test_url_component(self, mock_web_load):
        """Test basic URL component functionality."""
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"]})

        mock_web_load.return_value = [Mock(page_content="test content", metadata={"source": "https://example.com"})]

        data_ = component.fetch_content()
        assert all(value.data for value in data_)
        assert all(value.text for value in data_)
        assert all(value.source for value in data_)

    # @pytest.mark.parametrize(
    #     ("format_type", "expected_content"),
    #     [
    #         ("Text", "test content"),
    #         ("Raw HTML", "<html>test content</html>"),
    #     ],
    # )
    # def test_url_component_formats(self, mock_web_load, format_type, expected_content):
    #     """Test URL component with different format types."""
    #     component = URLComponent()
    #     component.set_attributes({"urls": ["https://example.com"], "format": format_type})

    #     # Mock the loader response
    #     mock_web_load.return_value = [Mock(page_content=expected_content, metadata={"source": "https://example.com"})]

    #     # Test fetch_content - use sync version
    #     content = component.fetch_content()
    #     assert len(content) == 1
    #     assert content[0].text == expected_content
    #     assert content[0].source == "https://example.com"

    def test_url_component_as_dataframe(self, mock_web_load):
        """Test URL component's as_dataframe method."""
        component = URLComponent()
        urls = ["https://example1.com", "https://example2.com"]
        component.set_attributes({"urls": urls})

        # Mock the loader response
        mock_web_load.return_value = [
            Mock(page_content="content1", metadata={"source": urls[0]}),
            Mock(page_content="content2", metadata={"source": urls[1]}),
        ]

        # Test as_dataframe
        data_frame = component.as_dataframe()
        assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
        assert len(data_frame) == 2
        assert list(data_frame.columns) == ["text", "source"]
        assert data_frame.iloc[0]["text"] == "content1"
        assert data_frame.iloc[0]["source"] == urls[0]
        assert data_frame.iloc[1]["text"] == "content2"
        assert data_frame.iloc[1]["source"] == urls[1]

    def test_url_component_fetch_content_text(self, mock_web_load):
        """Test URL component's fetch_content_text method."""
        component = URLComponent()
        component.set_attributes({"urls": ["https://example.com"]})

        mock_web_load.return_value = [Mock(page_content="test content", metadata={"source": "https://example.com"})]

        # Test fetch_content_text
        message = component.fetch_content_text()
        assert isinstance(message, Message), "Expected Message instance"
        assert message.text == "test content"

    def test_url_component_invalid_urls(self):
        """Test URL component with invalid URLs."""
        component = URLComponent()
        component.set_attributes({"urls": ["not_a_valid_url"]})

        # Test that invalid URLs raise a ValueError
        with pytest.raises(ValueError, match="Invalid URL: http://not_a_valid_url"):
            component.fetch_content()

    def test_url_component_multiple_urls(self, mock_web_load):
        """Test URL component with multiple URLs."""
        component = URLComponent()
        urls = ["https://example1.com", "https://example2.com", "https://example3.com"]
        component.set_attributes({"urls": urls})

        mock_web_load.return_value = [
            Mock(page_content=f"content{i + 1}", metadata={"source": url}) for i, url in enumerate(urls)
        ]

        # Test fetch_content
        content = component.fetch_content()
        assert len(content) == 3, f"Expected 3 content items, got {len(content)}"

        for i, item in enumerate(content):
            url = urls[i]
            assert item.source == url, f"Expected '{url}', got '{item.source}'"
            assert item.text == f"content{i + 1}"

    @respx.mock
    async def test_url_request_success(self, mock_web_load):
        """Test successful URL request."""
        url = "https://example.com/api/test"
        respx.get(url).mock(return_value=Response(200, json={"success": True}))

        component = URLComponent()
        component.set_attributes({"urls": [url]})

        mock_web_load.return_value = [Mock(page_content="test content", metadata={"source": url})]

        result = component.fetch_content()
        assert len(result) == 1
        assert result[0].source == url
