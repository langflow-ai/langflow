from unittest.mock import Mock, patch

import pytest
import respx
from httpx import Response
from langflow.components.data import RecursiveURLComponent
from langflow.schema import DataFrame, Message

from tests.base import ComponentTestBaseWithoutClient


class TestRecursiveURLComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return RecursiveURLComponent

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
        """Return the file mappings for different versions."""
        return []

    @pytest.fixture
    def mock_recursive_loader(self):
        """Mock the RecursiveUrlLoader.load method."""
        with patch("langchain_community.document_loaders.RecursiveUrlLoader.load") as mock:
            yield mock

    def test_recursive_url_component(self, mock_recursive_loader):
        """Test basic RecursiveURLComponent functionality."""
        component = RecursiveURLComponent()
        component.set_attributes({"urls": ["https://example.com"], "max_depth": 2})

        mock_recursive_loader.return_value = [
            Mock(page_content="test content", metadata={"source": "https://example.com"})
        ]

        data_ = component.fetch_content()
        assert all(value.data for value in data_)
        assert all(value.text for value in data_)
        assert all(value.source for value in data_)

    def test_recursive_url_component_as_dataframe(self, mock_recursive_loader):
        """Test RecursiveURLComponent's as_dataframe method."""
        component = RecursiveURLComponent()
        urls = ["https://example1.com", "https://example2.com"]
        component.set_attributes({"urls": urls, "max_depth": 1})

        # Mock the loader response
        mock_recursive_loader.return_value = [
            Mock(page_content="content1", metadata={"source": urls[0]}),
            Mock(page_content="content2", metadata={"source": urls[1]}),
        ]

        # Test as_dataframe
        data_frame = component.as_dataframe()
        assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
        assert len(data_frame) == 4  # Atualizado para esperar 4 registros

        assert list(data_frame.columns) == ["text", "source"]

        # Verificar se os conteúdos aparecem duas vezes, conforme esperado
        assert data_frame.iloc[0]["text"] == "content1"
        assert data_frame.iloc[0]["source"] == urls[0]

        assert data_frame.iloc[1]["text"] == "content2"
        assert data_frame.iloc[1]["source"] == urls[1]

        assert data_frame.iloc[2]["text"] == "content1"  # Segunda ocorrência
        assert data_frame.iloc[2]["source"] == urls[0]

        assert data_frame.iloc[3]["text"] == "content2"  # Segunda ocorrência
        assert data_frame.iloc[3]["source"] == urls[1]

    def test_recursive_url_component_fetch_content_text(self, mock_recursive_loader):
        """Test RecursiveURLComponent's fetch_content_text method."""
        component = RecursiveURLComponent()
        component.set_attributes({"urls": ["https://example.com"], "max_depth": 1})

        mock_recursive_loader.return_value = [
            Mock(page_content="test content", metadata={"source": "https://example.com"})
        ]

        # Test fetch_content_text
        message = component.fetch_content_text()
        assert isinstance(message, Message), "Expected Message instance"
        assert message.text == "test content"

    def test_recursive_url_component_ensure_url(self):
        """Test RecursiveURLComponent's ensure_url method."""
        component = RecursiveURLComponent()

        # Test URL without protocol
        url = "example.com"
        fixed_url = component.ensure_url(url)
        assert fixed_url == "https://example.com"

        # Test URL with protocol
        url = "http://example.com"
        fixed_url = component.ensure_url(url)
        assert fixed_url == "http://example.com"

    def test_recursive_url_component_multiple_urls(self, mock_recursive_loader):
        """Test RecursiveURLComponent with multiple URLs."""
        component = RecursiveURLComponent()
        urls = ["https://example1.com", "https://example2.com", "https://example3.com"]
        component.set_attributes({"urls": urls, "max_depth": 1})

        # Mock different content for each URL
        mock_recursive_loader.side_effect = [
            [Mock(page_content=f"content{i+1}", metadata={"source": url})] for i, url in enumerate(urls)
        ]

        # Test fetch_content
        content = component.fetch_content()
        assert len(content) == 3, f"Expected 3 content items, got {len(content)}"

        for i, item in enumerate(content):
            assert item.source == urls[i], f"Expected '{urls[i]}', got '{item.source}'"
            assert item.text == f"content{i+1}"

    @patch("langflow.components.data.RecursiveURLComponent.ensure_url")
    def test_recursive_url_component_error_handling(self, mock_recursive_loader):
        """Test error handling in RecursiveURLComponent."""
        component = RecursiveURLComponent()
        component.set_attributes({"urls": ["https://example.com"]})

        # Set up the mock to raise an exception
        mock_recursive_loader.side_effect = Exception("Connection error")

        # Test that exceptions are properly handled
        with pytest.raises(ValueError, match="Error loading documents: Connection error"):
            component.fetch_content()

    def test_recursive_url_component_format_options(self, mock_recursive_loader):
        """Test RecursiveURLComponent with different format options."""
        component = RecursiveURLComponent()

        # Test with Text format
        component.set_attributes({"urls": ["https://example.com"], "format": "Text"})
        mock_recursive_loader.return_value = [
            Mock(page_content="extracted text", metadata={"source": "https://example.com"})
        ]
        content_text = component.fetch_content()
        assert content_text[0].text == "extracted text"

        # Test with Raw HTML format
        component.set_attributes({"urls": ["https://example.com"], "format": "Raw HTML"})
        mock_recursive_loader.return_value = [
            Mock(page_content="<html>raw html</html>", metadata={"source": "https://example.com"})
        ]
        content_html = component.fetch_content()
        assert content_html[0].text == "<html>raw html</html>"

    @respx.mock
    async def test_url_request_success(self, mock_recursive_loader):
        """Test successful URL request."""
        url = "https://example.com/api/test"
        respx.get(url).mock(return_value=Response(200, json={"success": True}))

        component = RecursiveURLComponent()
        component.set_attributes({"urls": [url], "max_depth": 1})

        mock_recursive_loader.return_value = [Mock(page_content="test content", metadata={"source": url})]

        result = component.fetch_content()
        assert len(result) == 1
        assert result[0].source == url
