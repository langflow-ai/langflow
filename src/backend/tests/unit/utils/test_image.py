"""Tests for langflow.utils.image module."""

import base64
import tempfile
from pathlib import Path

import pytest

from langflow.utils.image import convert_image_to_base64, create_data_url, create_image_content_dict


@pytest.fixture
def sample_image(tmp_path):
    """Create a small PNG-like file for testing."""
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    return img_path


class TestConvertImageToBase64:
    def test_valid_file(self, sample_image):
        result = convert_image_to_base64(sample_image)
        # Should be valid base64
        decoded = base64.b64decode(result)
        assert decoded.startswith(b"\x89PNG")

    def test_string_path(self, sample_image):
        result = convert_image_to_base64(str(sample_image))
        assert isinstance(result, str)

    def test_empty_path_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            convert_image_to_base64("")

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            convert_image_to_base64("/nonexistent/path/image.png")

    def test_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not a file"):
            convert_image_to_base64(tmp_path)


class TestCreateDataUrl:
    def test_with_explicit_mime(self, sample_image):
        result = create_data_url(sample_image, mime_type="image/png")
        assert result.startswith("data:image/png;base64,")

    def test_guesses_mime_from_extension(self, sample_image):
        result = create_data_url(sample_image)
        assert result.startswith("data:image/png;base64,")

    def test_unknown_extension_raises(self, tmp_path):
        f = tmp_path / "file.unknownext"
        f.write_bytes(b"data")
        with pytest.raises(ValueError, match="Could not determine MIME type"):
            create_data_url(f)

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            create_data_url("/nonexistent/file.png", mime_type="image/png")


class TestCreateImageContentDict:
    def test_returns_dict(self, sample_image):
        # Clear lru_cache to avoid stale results
        create_image_content_dict.cache_clear()
        result = create_image_content_dict(str(sample_image), mime_type="image/png")
        assert result["type"] == "image_url"
        assert "image_url" in result
        assert result["image_url"]["url"].startswith("data:image/png;base64,")

    def test_unknown_mime_raises(self, tmp_path):
        create_image_content_dict.cache_clear()
        # Use a unique filename to avoid lru_cache hits from other tests
        f = tmp_path / "unique_no_mime_file.xyz123"
        f.write_bytes(b"data")
        with pytest.raises(ValueError, match="Could not determine MIME type"):
            create_image_content_dict(str(f))
