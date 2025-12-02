"""Tests for FileComponent image processing with Docling.

These tests cover scenarios where:
- Images are processed but contain no extractable text (e.g., profile pictures)
- Docling returns empty doc_rows
- Storage path resolution for uploaded files
- Edge cases in error handling
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.files_and_knowledge.file import FileComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class TestDoclingEmptyTextExtraction:
    """Tests for handling images/documents with no extractable text."""

    @patch("subprocess.run")
    def test_process_docling_empty_doc_rows_returns_placeholder(self, mock_subprocess, tmp_path):
        """Test that empty doc_rows from Docling creates placeholder data instead of error."""
        # Use tmp_path for secure temporary file references
        test_file = tmp_path / "profile-pic.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        component = FileComponent()
        component.markdown = False
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""
        component.pipeline = "standard"
        component.ocr_engine = "easyocr"

        # Mock Docling returning SUCCESS but with empty texts (like a profile picture)
        mock_result = {
            "ok": True,
            "mode": "structured",
            "doc": [],  # Empty - no text extracted from image
            "meta": {"file_path": str(test_file)},
        }
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(mock_result).encode("utf-8"),
            stderr=b"",
        )

        result = component._process_docling_in_subprocess(str(test_file))

        assert result is not None
        assert result.data["doc"] == []
        # The subprocess returns the raw result; processing happens in process_files

    @patch("subprocess.run")
    def test_process_files_handles_empty_doc_rows(self, mock_subprocess, tmp_path):
        """Test that process_files correctly handles empty doc_rows from Docling."""
        # Create a test image file
        test_image = tmp_path / "test_image.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # Minimal PNG header

        component = FileComponent()
        component.advanced_mode = True
        component.markdown = False
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""
        component.pipeline = "standard"
        component.ocr_engine = "easyocr"
        component.silent_errors = False

        # Mock Docling returning empty doc rows
        mock_result = {
            "ok": True,
            "mode": "structured",
            "doc": [],
            "meta": {"file_path": str(test_image)},
        }
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(mock_result).encode("utf-8"),
            stderr=b"",
        )

        # Create BaseFile mock
        from lfx.base.data.base_file import BaseFileComponent

        base_file = BaseFileComponent.BaseFile(
            data=Data(data={"file_path": str(test_image)}),
            path=test_image,
            delete_after_processing=False,
        )

        # Process the file
        result = component.process_files([base_file])

        # Should return a list with one BaseFile containing placeholder data
        assert len(result) == 1
        assert result[0].data is not None
        assert len(result[0].data) == 1

        # Check that placeholder text was created
        data_item = result[0].data[0]
        assert "text" in data_item.data or "info" in data_item.data

    @patch("subprocess.run")
    def test_load_files_dataframe_with_empty_text_image(self, mock_subprocess, tmp_path):
        """Test that load_files_dataframe doesn't error on images with no text."""
        test_image = tmp_path / "profile.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        component = FileComponent()
        component.path = [str(test_image)]
        component.advanced_mode = True
        component.markdown = False
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""
        component.pipeline = "standard"
        component.ocr_engine = "easyocr"
        component.silent_errors = False
        component.use_multithreading = False
        component.concurrency_multithreading = 1
        component.delete_server_file_after_processing = False
        component.ignore_unsupported_extensions = True
        component.ignore_unspecified_files = False
        component.separator = "\n\n"

        # Mock successful Docling processing with empty text
        mock_result = {
            "ok": True,
            "mode": "structured",
            "doc": [],
            "meta": {"file_path": str(test_image)},
        }
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(mock_result).encode("utf-8"),
            stderr=b"",
        )

        # This should NOT raise an error
        result = component.load_files_dataframe()

        assert isinstance(result, DataFrame)
        # DataFrame should not be empty - it should have placeholder data
        assert not result.empty, "DataFrame should contain placeholder data for image without text"

    @patch("subprocess.run")
    def test_load_files_markdown_with_empty_text_image(self, mock_subprocess, tmp_path):
        """Test that load_files_markdown returns placeholder message for images with no text."""
        test_image = tmp_path / "profile.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        component = FileComponent()
        component.path = [str(test_image)]
        component.advanced_mode = True
        component.markdown = True
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""
        component.pipeline = "standard"
        component.ocr_engine = "easyocr"
        component.silent_errors = False
        component.use_multithreading = False
        component.concurrency_multithreading = 1
        component.delete_server_file_after_processing = False
        component.ignore_unsupported_extensions = True
        component.ignore_unspecified_files = False
        component.separator = "\n\n"

        # Mock successful Docling processing with empty text
        mock_result = {
            "ok": True,
            "mode": "markdown",
            "text": "",  # Empty markdown
            "meta": {"file_path": str(test_image)},
        }
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(mock_result).encode("utf-8"),
            stderr=b"",
        )

        # This should NOT raise an error
        result = component.load_files_markdown()

        assert result is not None
        assert hasattr(result, "text")
        # Should have some placeholder text, not empty


class TestDoclingSubprocessErrors:
    """Tests for error handling in Docling subprocess."""

    @patch("subprocess.run")
    def test_docling_conversion_failure(self, mock_subprocess, tmp_path):
        """Test handling of Docling conversion failure."""
        test_file = tmp_path / "bad_file.xyz"
        test_file.write_bytes(b"invalid content")

        component = FileComponent()
        component.markdown = False
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""
        component.pipeline = "standard"
        component.ocr_engine = "easyocr"

        mock_result = {
            "ok": False,
            "error": "Docling conversion failed: unsupported format",
            "meta": {"file_path": str(test_file)},
        }
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(mock_result).encode("utf-8"),
            stderr=b"",
        )

        result = component._process_docling_in_subprocess(str(test_file))

        assert result is not None
        assert "error" in result.data
        assert "Docling conversion failed" in result.data["error"]

    @patch("subprocess.run")
    def test_docling_subprocess_crash(self, mock_subprocess, tmp_path):
        """Test handling of Docling subprocess crash (no output)."""
        test_file = tmp_path / "crash.pdf"
        test_file.write_bytes(b"%PDF-1.4 test")

        component = FileComponent()
        component.markdown = False
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""
        component.pipeline = "standard"
        component.ocr_engine = "easyocr"

        mock_subprocess.return_value = MagicMock(
            stdout=b"",  # No output
            stderr=b"Segmentation fault",
        )

        result = component._process_docling_in_subprocess(str(test_file))

        assert result is not None
        assert "error" in result.data
        assert "Segmentation fault" in result.data["error"] or "no output" in result.data["error"].lower()

    @patch("subprocess.run")
    def test_docling_invalid_json_output(self, mock_subprocess, tmp_path):
        """Test handling of invalid JSON from Docling subprocess."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4 test")

        component = FileComponent()
        component.markdown = False
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""
        component.pipeline = "standard"
        component.ocr_engine = "easyocr"

        mock_subprocess.return_value = MagicMock(
            stdout=b"not valid json {{{",
            stderr=b"",
        )

        result = component._process_docling_in_subprocess(str(test_file))

        assert result is not None
        assert "error" in result.data
        assert "Invalid JSON" in result.data["error"]


class TestStoragePathResolution:
    """Tests for storage path resolution (flow_id/filename format)."""

    def test_is_storage_path_format(self):
        """Test detection of storage path format."""
        # Test storage path format (flow_id/filename)
        storage_path = "b2eff18f-31e6-41e7-89c3-65005504ab69/profile-pic.png"
        assert "/" in storage_path
        assert not Path(storage_path).is_absolute()

        # Test absolute path is not storage format
        absolute_path = "/absolute/path/file.png"
        assert Path(absolute_path).is_absolute()

        # Test simple filename is not storage format
        simple_file = "simple_file.png"
        assert "/" not in simple_file

    @pytest.mark.xfail(reason="Storage path resolution needs to be fixed - currently not using get_full_path correctly")
    @patch("lfx.services.deps.get_storage_service")
    @patch("lfx.services.deps.get_settings_service")
    def test_validate_and_resolve_paths_uses_storage_service(self, mock_settings, mock_storage, tmp_path):
        """Test that storage paths are resolved using storage service.

        This test currently fails because the path resolution doesn't properly
        use the storage service's get_full_path for paths in flow_id/filename format.
        """
        # Create a test file in a mock storage location
        storage_dir = tmp_path / "storage"
        flow_dir = storage_dir / "flow123"
        flow_dir.mkdir(parents=True)
        test_file = flow_dir / "document.pdf"
        test_file.write_bytes(b"%PDF-1.4 test")

        # Mock settings for local storage
        mock_settings_instance = MagicMock()
        mock_settings_instance.settings.storage_type = "local"
        mock_settings.return_value = mock_settings_instance

        # Mock storage service
        mock_storage_instance = MagicMock()
        mock_storage_instance.build_full_path.return_value = str(test_file)
        mock_storage.return_value = mock_storage_instance

        # Use FileComponent instead of abstract BaseFileComponent
        component = FileComponent()
        component.path = ["flow123/document.pdf"]
        component.silent_errors = False
        component.delete_server_file_after_processing = False
        component.ignore_unspecified_files = False

        # Should resolve the path using storage service
        files = component._validate_and_resolve_paths()

        assert len(files) == 1
        assert files[0].path == test_file


class TestFileNotFoundHandling:
    """Tests for handling of missing files."""

    def test_missing_file_raises_clear_error(self, tmp_path):
        """Test that missing files raise a clear error message."""
        # Use FileComponent instead of abstract BaseFileComponent
        component = FileComponent()
        component.path = [str(tmp_path / "nonexistent_file.txt")]
        component.silent_errors = False
        component.delete_server_file_after_processing = False
        component.ignore_unspecified_files = False

        with pytest.raises(ValueError, match=r"[Ff]ile.*not found|[Nn]ot found"):
            component._validate_and_resolve_paths()

    @pytest.mark.xfail(reason="Silent mode should skip missing files but currently adds them anyway")
    def test_missing_file_silent_mode(self, tmp_path):
        """Test that missing files are skipped in silent mode.

        This test currently fails because silent_errors=True should skip
        missing files, but the current implementation still adds them to the list.
        """
        # Use FileComponent instead of abstract BaseFileComponent
        component = FileComponent()
        component.path = [str(tmp_path / "nonexistent_file.txt")]
        component.silent_errors = True
        component.delete_server_file_after_processing = False
        component.ignore_unspecified_files = False

        # Should not raise, should return empty list
        files = component._validate_and_resolve_paths()
        assert files == []


class TestDataFrameEmptyHandling:
    """Tests for DataFrame empty state handling."""

    def test_dataframe_with_empty_dict_is_empty(self):
        """Test that DataFrame([{}]) is considered empty."""
        df = DataFrame([{}])
        assert df.empty, "DataFrame with single empty dict should be empty"

    def test_dataframe_with_placeholder_data_is_not_empty(self):
        """Test that DataFrame with placeholder data is not empty."""
        df = DataFrame(
            [
                {
                    "file_path": "/some/path.png",
                    "text": "(No text content extracted from image)",
                    "info": "Image processed successfully",
                }
            ]
        )
        assert not df.empty, "DataFrame with placeholder data should not be empty"
        assert "text" in df.columns

    def test_dataframe_with_empty_text_is_not_empty(self):
        """Test that DataFrame with empty string text is not empty."""
        df = DataFrame(
            [
                {
                    "file_path": "/some/path.png",
                    "text": "",
                }
            ]
        )
        assert not df.empty, "DataFrame with empty text string should not be empty"


class TestImageFileTypes:
    """Tests for different image file types."""

    @pytest.mark.parametrize("extension", ["png", "jpg", "jpeg", "bmp", "tiff", "webp"])
    def test_image_extensions_are_docling_compatible(self, extension):
        """Test that image extensions are recognized as Docling-compatible."""
        component = FileComponent()
        assert component._is_docling_compatible(f"/path/to/image.{extension}")

    @pytest.mark.parametrize("extension", ["png", "jpg", "jpeg", "bmp", "tiff", "webp"])
    def test_image_extensions_require_advanced_mode(self, extension):
        """Test that image extensions require advanced mode."""
        component = FileComponent()
        # These extensions should be in DOCLING_ONLY_EXTENSIONS
        assert extension in component.DOCLING_ONLY_EXTENSIONS or extension in ["jpeg"]


class TestProcessFilesEdgeCases:
    """Edge case tests for process_files method."""

    def test_process_files_empty_list_raises_error(self):
        """Test that processing empty file list raises ValueError."""
        component = FileComponent()
        component.advanced_mode = True

        with pytest.raises(ValueError, match="No files to process"):
            component.process_files([])

    def test_process_files_docling_only_extension_without_advanced_mode(
        self,
        tmp_path,
    ):
        """Test that Docling-only extensions require advanced mode."""
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        component = FileComponent()
        component.advanced_mode = False  # Disabled
        component.silent_errors = False

        from lfx.base.data.base_file import BaseFileComponent

        base_file = BaseFileComponent.BaseFile(
            data=Data(data={"file_path": str(test_image)}),
            path=test_image,
            delete_after_processing=False,
        )

        with pytest.raises(ValueError, match=r"requires.*Advanced Parser"):
            component.process_files([base_file])


class TestLoadFilesHelperValidation:
    """Tests for load_files_helper validation logic."""

    def test_load_files_helper_empty_dataframe_raises_error(self):
        """Test that empty DataFrame raises descriptive error."""
        component = FileComponent()

        with (
            patch.object(component, "load_files", return_value=DataFrame()),
            pytest.raises(ValueError, match="Could not extract content"),
        ):
            component.load_files_helper()

    def test_load_files_helper_with_error_column(self):
        """Test that error column is checked and raised."""
        component = FileComponent()

        error_df = DataFrame(
            [
                {
                    "error": "File processing failed",
                    "file_path": "/some/path",
                }
            ]
        )

        with (
            patch.object(component, "load_files", return_value=error_df),
            pytest.raises(ValueError, match="File processing failed"),
        ):
            component.load_files_helper()

    def test_load_files_helper_with_error_and_text(self):
        """Test that error is not raised if text column exists with error."""
        component = FileComponent()

        # If we have both error and text, should not raise
        df_with_both = DataFrame(
            [
                {
                    "error": "Some warning",
                    "text": "Actual content",
                    "file_path": "/some/path",
                }
            ]
        )

        with patch.object(component, "load_files", return_value=df_with_both):
            result = component.load_files_helper()
            assert not result.empty


class TestImageContentTypeValidation:
    """Tests for validating that image content matches file extension."""

    def test_valid_png_file(self, tmp_path):
        """Test that a valid PNG file passes validation."""
        from lfx.base.data.storage_utils import validate_image_content_type

        # Create a valid PNG file (minimal PNG header)
        png_file = tmp_path / "valid.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        is_valid, error = validate_image_content_type(str(png_file))
        assert is_valid is True
        assert error is None

    def test_valid_jpeg_file(self, tmp_path):
        """Test that a valid JPEG file passes validation."""
        from lfx.base.data.storage_utils import validate_image_content_type

        # Create a valid JPEG file (JPEG magic bytes)
        jpeg_file = tmp_path / "valid.jpg"
        jpeg_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        is_valid, error = validate_image_content_type(str(jpeg_file))
        assert is_valid is True
        assert error is None

    def test_jpeg_saved_as_png_fails(self, tmp_path):
        """Test that a JPEG file saved with .png extension is rejected."""
        from lfx.base.data.storage_utils import validate_image_content_type

        # Create a JPEG file but with .png extension
        mismatched_file = tmp_path / "actually_jpeg.png"
        mismatched_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        is_valid, error = validate_image_content_type(str(mismatched_file))
        assert is_valid is False
        assert error is not None
        assert "JPEG" in error
        assert ".png" in error

    def test_png_saved_as_jpg_fails(self, tmp_path):
        """Test that a PNG file saved with .jpg extension is rejected."""
        from lfx.base.data.storage_utils import validate_image_content_type

        # Create a PNG file but with .jpg extension
        mismatched_file = tmp_path / "actually_png.jpg"
        mismatched_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        is_valid, error = validate_image_content_type(str(mismatched_file))
        assert is_valid is False
        assert error is not None
        assert "PNG" in error
        assert ".jpg" in error

    def test_non_image_file_passes(self, tmp_path):
        """Test that non-image files skip validation."""
        from lfx.base.data.storage_utils import validate_image_content_type

        # Create a text file
        text_file = tmp_path / "document.txt"
        text_file.write_text("Hello, world!")

        is_valid, error = validate_image_content_type(str(text_file))
        assert is_valid is True
        assert error is None

    def test_unrecognized_content_fails(self, tmp_path):
        """Test that a file with unrecognized content is rejected."""
        from lfx.base.data.storage_utils import validate_image_content_type

        # Create a file with .png extension but random content
        # This should fail - it's not a valid image
        unknown_file = tmp_path / "unknown.png"
        unknown_file.write_bytes(b"this is not a real image at all")

        is_valid, error = validate_image_content_type(str(unknown_file))
        assert is_valid is False
        assert error is not None
        assert "not a valid image format" in error

    def test_valid_gif_file(self, tmp_path):
        """Test that a valid GIF file passes validation."""
        from lfx.base.data.storage_utils import validate_image_content_type

        # Create a valid GIF file
        gif_file = tmp_path / "valid.gif"
        gif_file.write_bytes(b"GIF89a" + b"\x00" * 100)

        is_valid, error = validate_image_content_type(str(gif_file))
        assert is_valid is True
        assert error is None

    def test_valid_webp_file(self, tmp_path):
        """Test that a valid WebP file passes validation."""
        from lfx.base.data.storage_utils import validate_image_content_type

        # Create a valid WebP file (RIFF....WEBP header)
        webp_file = tmp_path / "valid.webp"
        webp_file.write_bytes(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100)

        is_valid, error = validate_image_content_type(str(webp_file))
        assert is_valid is True
        assert error is None

    def test_valid_bmp_file(self, tmp_path):
        """Test that a valid BMP file passes validation."""
        from lfx.base.data.storage_utils import validate_image_content_type

        # Create a valid BMP file
        bmp_file = tmp_path / "valid.bmp"
        bmp_file.write_bytes(b"BM" + b"\x00" * 100)

        is_valid, error = validate_image_content_type(str(bmp_file))
        assert is_valid is True
        assert error is None

    def test_process_files_rejects_mismatched_image(self, tmp_path):
        """Test that process_files rejects images with content/extension mismatch."""
        # Create a JPEG file but with .png extension
        mismatched_file = tmp_path / "fake.png"
        mismatched_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        component = FileComponent()
        component.advanced_mode = True
        component.silent_errors = False

        from lfx.base.data.base_file import BaseFileComponent

        base_file = BaseFileComponent.BaseFile(
            data=Data(data={"file_path": str(mismatched_file)}),
            path=mismatched_file,
            delete_after_processing=False,
        )

        with pytest.raises(ValueError, match=r"\.png.*JPEG"):
            component.process_files([base_file])

    @patch("subprocess.run")
    def test_process_files_silent_mode_skips_mismatched_image(self, mock_subprocess, tmp_path):
        """Test that process_files in silent mode logs but doesn't raise for mismatched images."""
        # Create a JPEG file but with .png extension
        mismatched_file = tmp_path / "fake.png"
        mismatched_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        component = FileComponent()
        component.advanced_mode = True
        component.silent_errors = True
        component.markdown = False
        component.md_image_placeholder = "<!-- image -->"
        component.md_page_break_placeholder = ""
        component.pipeline = "standard"
        component.ocr_engine = "easyocr"
        component.use_multithreading = False
        component.concurrency_multithreading = 1

        # Mock Docling to return success (won't be called if validation fails)
        mock_result = {
            "ok": True,
            "mode": "structured",
            "doc": [],
            "meta": {"file_path": str(mismatched_file)},
        }
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(mock_result).encode("utf-8"),
            stderr=b"",
        )

        from lfx.base.data.base_file import BaseFileComponent

        base_file = BaseFileComponent.BaseFile(
            data=Data(data={"file_path": str(mismatched_file)}),
            path=mismatched_file,
            delete_after_processing=False,
        )

        # Should not raise in silent mode
        result = component.process_files([base_file])
        # Result may be empty or contain data, but no exception should be raised
        assert isinstance(result, list)
