"""Tests for Azure Document Intelligence Component."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path

from langflow.components.models.document_intelligence import AzureDocumentIntelligenceComponent
from langflow.schema.data import Data


class TestAzureDocumentIntelligenceComponent:
    """Test cases for Azure Document Intelligence Component."""

    def test_component_initialization(self):
        """Test that the component initializes correctly."""
        component = AzureDocumentIntelligenceComponent()

        assert component.display_name == "Azure Document Intelligence"
        assert component.name == "AzureDocumentIntelligence"
        assert component.category == "models"
        assert component.model_type == "prebuilt-document"
        assert component.extract_tables is True
        assert component.extract_key_value_pairs is True
        assert component.include_confidence is False

    def test_model_options(self):
        """Test that model options are available."""
        component = AzureDocumentIntelligenceComponent()

        expected_models = [
            "prebuilt-document",
            "prebuilt-read",
            "prebuilt-layout",
            "prebuilt-businessCard",
            "prebuilt-idDocument",
            "prebuilt-invoice",
            "prebuilt-receipt",
            "prebuilt-tax.us.w2",
            "prebuilt-healthInsuranceCard.us"
        ]

        assert component.MODEL_OPTIONS == expected_models

    def test_extract_filename_from_url(self):
        """Test URL filename extraction."""
        component = AzureDocumentIntelligenceComponent()

        # Test simple URL with filename
        url = "https://example.com/document.pdf"
        filename = component._extract_filename_from_url(url)
        assert filename == "document.pdf"

        # Test fallback to default
        with patch('requests.head') as mock_head:
            mock_head.side_effect = Exception("Network error")
            filename = component._extract_filename_from_url("https://example.com/")
            assert filename == "downloaded.pdf"

    def test_extract_url_from_input_string(self):
        """Test URL extraction from string input."""
        component = AzureDocumentIntelligenceComponent()

        url = "https://example.com/document.pdf"
        result = component._extract_url_from_input(url)
        assert result == url

    def test_extract_url_from_input_data_object(self):
        """Test URL extraction from Data object."""
        component = AzureDocumentIntelligenceComponent()

        data = Data(data={"file_path": "https://example.com/document.pdf"})
        result = component._extract_url_from_input(data)
        assert result == "https://example.com/document.pdf"

    def test_extract_url_from_input_list(self):
        """Test URL extraction from list of Data objects."""
        component = AzureDocumentIntelligenceComponent()

        data_list = [Data(data={"file_path": "https://example.com/document.pdf"})]
        result = component._extract_url_from_input(data_list)
        assert result == "https://example.com/document.pdf"

    @patch('tempfile.mkdtemp')
    def test_component_cleanup(self, mock_mkdtemp):
        """Test that component cleans up temporary files."""
        mock_mkdtemp.return_value = "/tmp/test_dir"

        with patch('os.path.exists') as mock_exists, \
             patch('os.unlink') as mock_unlink, \
             patch('os.rmdir') as mock_rmdir:

            mock_exists.return_value = True

            component = AzureDocumentIntelligenceComponent()
            component._downloaded_files = {"/tmp/test_file.pdf": "/tmp/test_file.pdf"}

            # Simulate cleanup
            component.__del__()

            mock_unlink.assert_called_once()
            mock_rmdir.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_file_with_mock_service(self):
        """Test file processing with mocked Document Intelligence service."""
        component = AzureDocumentIntelligenceComponent()

        # Mock the service manager and service
        mock_service = AsyncMock()
        mock_service.process_document.return_value = (
            [{"page_number": 1, "text": "Sample text", "tables": [], "form": []}],
            "Sample text"
        )

        with patch('langflow.services.manager.service_manager') as mock_manager:
            mock_manager.get.return_value = mock_service

            # Mock file reading
            with patch('builtins.open', mock_open_file(b"fake pdf content")):
                result, plain_text = await component.process_file("/fake/path.pdf")

                assert isinstance(result, Data)
                assert plain_text == "Sample text"
                assert result.text == "Sample text"
                assert "result" in result.data

    def test_valid_extensions(self):
        """Test that valid file extensions are defined."""
        component = AzureDocumentIntelligenceComponent()

        expected_extensions = ["pdf", "jpg", "jpeg", "png", "bmp", "tiff", "tif"]
        assert component.VALID_EXTENSIONS == expected_extensions

    @pytest.mark.asyncio
    async def test_process_documents_no_files(self):
        """Test processing when no files are provided."""
        component = AzureDocumentIntelligenceComponent()
        component.silent_errors = True

        # Mock _validate_and_resolve_paths to return empty list
        with patch.object(component, '_validate_and_resolve_paths', return_value=[]):
            result = await component.process_documents()

            assert isinstance(result, Data)
            assert "error" in result.value
            assert "No valid files" in result.value["error"]

    def test_build_method(self):
        """Test that build method returns the correct function."""
        component = AzureDocumentIntelligenceComponent()
        build_func = component.build()

        assert build_func == component.process_documents


def mock_open_file(content):
    """Helper function to mock file opening with specific content."""
    mock_file = MagicMock()
    mock_file.read.return_value = content
    mock_file.__enter__.return_value = mock_file
    return MagicMock(return_value=mock_file)