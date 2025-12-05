"""Tests for docling_utils module."""

import pytest

try:
    from docling_core.types.doc import DoclingDocument

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    # Skip entire module if docling not available
    pytest.skip("docling_core not installed", allow_module_level=True)

from lfx.base.data.docling_utils import extract_docling_documents
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class TestExtractDoclingDocuments:
    """Test extract_docling_documents function."""

    def test_extract_from_data_with_correct_key(self):
        """Test extracting DoclingDocument from Data with correct key."""
        # Create a mock DoclingDocument
        doc = DoclingDocument(name="test_doc")
        data = Data(data={"doc": doc, "file_path": "test.pdf"})

        # Extract documents
        result, warning = extract_docling_documents(data, "doc")

        # Verify
        assert len(result) == 1
        assert isinstance(result[0], DoclingDocument)
        assert result[0].name == "test_doc"
        assert warning is None

    def test_extract_from_data_with_wrong_key(self):
        """Test extracting DoclingDocument from Data with wrong key raises error."""
        doc = DoclingDocument(name="test_doc")
        data = Data(data={"doc": doc, "file_path": "test.pdf"})

        # Should raise TypeError when key is not found
        with pytest.raises(TypeError, match="'wrong_key' field not available"):
            extract_docling_documents(data, "wrong_key")

    def test_extract_from_list_of_data(self):
        """Test extracting DoclingDocument from list of Data objects."""
        doc1 = DoclingDocument(name="test_doc1")
        doc2 = DoclingDocument(name="test_doc2")
        data_list = [
            Data(data={"doc": doc1, "file_path": "test1.pdf"}),
            Data(data={"doc": doc2, "file_path": "test2.pdf"}),
        ]

        # Extract documents
        result, warning = extract_docling_documents(data_list, "doc")

        # Verify
        assert len(result) == 2
        assert all(isinstance(d, DoclingDocument) for d in result)
        assert result[0].name == "test_doc1"
        assert result[1].name == "test_doc2"
        assert warning is None

    def test_extract_from_dataframe_with_correct_column(self):
        """Test extracting DoclingDocument from DataFrame with correct column name."""
        doc1 = DoclingDocument(name="test_doc1")
        doc2 = DoclingDocument(name="test_doc2")

        # Create DataFrame with 'doc' column
        df = DataFrame([{"doc": doc1, "file_path": "test1.pdf"}, {"doc": doc2, "file_path": "test2.pdf"}])

        # Extract documents
        result, warning = extract_docling_documents(df, "doc")

        # Verify
        assert len(result) == 2
        assert all(isinstance(d, DoclingDocument) for d in result)
        assert warning is None

    def test_extract_from_dataframe_with_fallback_column(self):
        """Test extracting DoclingDocument from DataFrame when exact column name not found.

        But DoclingDocument exists.
        """
        doc1 = DoclingDocument(name="test_doc1")
        doc2 = DoclingDocument(name="test_doc2")

        # Create DataFrame where DoclingDocument is in a different column
        # Simulate the case where pandas doesn't preserve the 'doc' column name
        df = DataFrame([{"document": doc1, "file_path": "test1.pdf"}, {"document": doc2, "file_path": "test2.pdf"}])

        # Extract documents - should find 'document' column as fallback
        result, warning = extract_docling_documents(df, "doc")

        # Verify
        assert len(result) == 2
        assert all(isinstance(d, DoclingDocument) for d in result)
        # Verify warning is present since we used fallback column
        assert warning is not None
        assert "Column 'doc' not found" in warning
        assert "found DoclingDocument objects in column 'document'" in warning
        assert "Consider updating the 'Doc Key' parameter" in warning

    def test_extract_from_dataframe_no_docling_column(self):
        """Test extracting DoclingDocument from DataFrame with no DoclingDocument column raises helpful error."""
        # Create DataFrame without any DoclingDocument objects
        df = DataFrame([{"text": "hello", "file_path": "test1.pdf"}, {"text": "world", "file_path": "test2.pdf"}])

        # Should raise TypeError with helpful message
        with pytest.raises(TypeError) as exc_info:
            extract_docling_documents(df, "doc")

        # Verify error message contains helpful information
        error_msg = str(exc_info.value)
        assert "Column 'doc' not found in DataFrame" in error_msg
        assert "Available columns:" in error_msg
        assert "Possible solutions:" in error_msg
        assert "Use the 'Data' output" in error_msg

    def test_extract_from_empty_dataframe(self):
        """Test extracting from empty DataFrame raises error."""
        df = DataFrame([])

        with pytest.raises(TypeError, match="DataFrame is empty"):
            extract_docling_documents(df, "doc")

    def test_extract_from_empty_data_list(self):
        """Test extracting from empty list raises error."""
        with pytest.raises(TypeError, match="No data inputs provided"):
            extract_docling_documents([], "doc")

    def test_extract_from_none(self):
        """Test extracting from None raises error."""
        with pytest.raises(TypeError, match="No data inputs provided"):
            extract_docling_documents(None, "doc")
