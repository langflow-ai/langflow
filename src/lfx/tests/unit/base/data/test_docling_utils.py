"""Tests for docling_utils module."""

import time
from unittest.mock import MagicMock, patch

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


class TestDocumentConverterCaching:
    """Test DocumentConverter caching functionality."""

    def test_cached_converter_function_exists(self):
        """Test that _get_cached_converter function exists and is properly decorated."""
        from lfx.base.data.docling_utils import _get_cached_converter

        # Verify function exists
        assert callable(_get_cached_converter)

        # Verify it has cache_info method (indicates lru_cache decorator)
        assert hasattr(_get_cached_converter, "cache_info")
        assert callable(_get_cached_converter.cache_info)

    def test_cached_converter_cache_key(self):
        """Test that cache uses correct parameters as key."""
        from lfx.base.data.docling_utils import _get_cached_converter

        # Clear cache before test
        _get_cached_converter.cache_clear()

        # Mock the DocumentConverter creation to avoid heavy imports
        # Patch at import source since DocumentConverter is imported inside _get_cached_converter
        with patch("docling.document_converter.DocumentConverter") as mock_converter:
            mock_instance1 = MagicMock()
            mock_instance2 = MagicMock()
            mock_converter.side_effect = [mock_instance1, mock_instance2]

            # First call with specific parameters
            result1 = _get_cached_converter(
                pipeline="standard",
                ocr_engine="None",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )

            # Second call with same parameters should return cached result
            result2 = _get_cached_converter(
                pipeline="standard",
                ocr_engine="None",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )

            # Third call with different parameters should create new instance
            result3 = _get_cached_converter(
                pipeline="vlm",
                ocr_engine="None",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )

            # Verify caching behavior
            assert result1 is result2, "Same parameters should return cached instance"
            assert result1 is not result3, "Different parameters should return new instance"

            # Verify DocumentConverter was only called twice (not three times)
            assert mock_converter.call_count == 2

            # Verify cache statistics
            cache_info = _get_cached_converter.cache_info()
            assert cache_info.hits >= 1, "Should have at least one cache hit"
            assert cache_info.misses == 2, "Should have exactly two cache misses"

    def test_cached_converter_lru_eviction(self):
        """Test that LRU cache properly evicts old entries when maxsize is reached."""
        from lfx.base.data.docling_utils import _get_cached_converter

        # Clear cache before test
        _get_cached_converter.cache_clear()

        # Patch at import source since DocumentConverter is imported inside _get_cached_converter
        with patch("docling.document_converter.DocumentConverter") as mock_converter:
            mock_instances = [MagicMock() for _ in range(5)]
            mock_converter.side_effect = mock_instances

            # Create 5 different cache entries (maxsize=4, so one should be evicted)
            configs = [
                ("standard", "None", False, None),
                ("standard", "easyocr", False, None),
                ("vlm", "None", False, None),
                ("standard", "None", True, None),
                ("vlm", "easyocr", False, None),
            ]

            for pipeline, ocr, pic_class, pic_hash in configs:
                _get_cached_converter(
                    pipeline=pipeline,
                    ocr_engine=ocr,
                    do_picture_classification=pic_class,
                    pic_desc_config_hash=pic_hash,
                )

            # Cache size should be at most 4 (maxsize)
            cache_info = _get_cached_converter.cache_info()
            assert cache_info.currsize <= 4, "Cache size should not exceed maxsize"

    def test_cached_converter_performance_improvement(self):
        """Test that caching provides performance improvement."""
        from lfx.base.data.docling_utils import _get_cached_converter

        # Clear cache before test
        _get_cached_converter.cache_clear()

        # Patch at import source since DocumentConverter is imported inside _get_cached_converter
        with patch("docling.document_converter.DocumentConverter") as mock_converter:
            # Simulate slow converter creation
            def slow_creation(*args, **kwargs):  # noqa: ARG001
                time.sleep(0.05)  # 50ms delay
                return MagicMock()

            mock_converter.side_effect = slow_creation

            # First call (cache miss - should be slow)
            start_time = time.time()
            _get_cached_converter(
                pipeline="standard",
                ocr_engine="None",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )
            first_call_duration = time.time() - start_time

            # Second call (cache hit - should be fast)
            start_time = time.time()
            _get_cached_converter(
                pipeline="standard",
                ocr_engine="None",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )
            second_call_duration = time.time() - start_time

            # Cache hit should be significantly faster (at least 10x)
            assert second_call_duration < first_call_duration / 10, (
                f"Cache hit should be much faster: first={first_call_duration:.4f}s, second={second_call_duration:.4f}s"
            )

    def test_cache_clear(self):
        """Test that cache can be cleared."""
        from lfx.base.data.docling_utils import _get_cached_converter

        # Clear cache
        _get_cached_converter.cache_clear()

        # Patch at import source since DocumentConverter is imported inside _get_cached_converter
        with patch("docling.document_converter.DocumentConverter"):
            # Add something to cache
            _get_cached_converter(
                pipeline="standard",
                ocr_engine="None",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )

            # Verify cache has content
            cache_info = _get_cached_converter.cache_info()
            assert cache_info.currsize > 0

            # Clear cache
            _get_cached_converter.cache_clear()

            # Verify cache is empty
            cache_info = _get_cached_converter.cache_info()
            assert cache_info.currsize == 0
            assert cache_info.hits == 0
            assert cache_info.misses == 0

    def test_different_ocr_engines_create_different_caches(self):
        """Test that different OCR engines result in different cached converters."""
        from lfx.base.data.docling_utils import _get_cached_converter

        _get_cached_converter.cache_clear()

        # Patch at import source since DocumentConverter is imported inside _get_cached_converter
        with patch("docling.document_converter.DocumentConverter") as mock_converter:
            mock_instance1 = MagicMock()
            mock_instance2 = MagicMock()
            mock_converter.side_effect = [mock_instance1, mock_instance2]

            # Create converter with no OCR
            result1 = _get_cached_converter(
                pipeline="standard",
                ocr_engine="None",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )

            # Create converter with EasyOCR
            result2 = _get_cached_converter(
                pipeline="standard",
                ocr_engine="easyocr",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )

            # Should be different instances
            assert result1 is not result2
            assert mock_converter.call_count == 2

    def test_different_pipelines_create_different_caches(self):
        """Test that different pipelines result in different cached converters."""
        from lfx.base.data.docling_utils import _get_cached_converter

        _get_cached_converter.cache_clear()

        # Patch at import source since DocumentConverter is imported inside _get_cached_converter
        with patch("docling.document_converter.DocumentConverter") as mock_converter:
            mock_instance1 = MagicMock()
            mock_instance2 = MagicMock()
            mock_converter.side_effect = [mock_instance1, mock_instance2]

            # Create converter with standard pipeline
            result1 = _get_cached_converter(
                pipeline="standard",
                ocr_engine="None",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )

            # Create converter with VLM pipeline
            result2 = _get_cached_converter(
                pipeline="vlm",
                ocr_engine="None",
                do_picture_classification=False,
                pic_desc_config_hash=None,
            )

            # Should be different instances
            assert result1 is not result2
            assert mock_converter.call_count == 2
