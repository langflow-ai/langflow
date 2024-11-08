import base64

import pytest
from langflow.utils.image import convert_image_to_base64, create_data_url


@pytest.fixture
def sample_image(tmp_path):
    """Create a sample image file for testing."""
    image_path = tmp_path / "test_image.png"
    # Create a small black 1x1 pixel PNG file
    image_content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    image_path.write_bytes(image_content)
    return image_path


class TestImageUtils:
    def test_convert_image_to_base64_success(self, sample_image):
        """Test successful conversion of image to base64."""
        base64_str = convert_image_to_base64(sample_image)
        assert isinstance(base64_str, str)
        # Verify it's valid base64
        assert base64.b64decode(base64_str)

    def test_convert_image_to_base64_empty_path(self):
        """Test conversion with empty path."""
        with pytest.raises(ValueError, match="Image path cannot be empty"):
            convert_image_to_base64("")

    def test_convert_image_to_base64_nonexistent_file(self):
        """Test conversion with non-existent file."""
        with pytest.raises(FileNotFoundError, match="Image file not found"):
            convert_image_to_base64("nonexistent.png")

    def test_convert_image_to_base64_directory(self, tmp_path):
        """Test conversion with directory path instead of file."""
        with pytest.raises(ValueError, match="Path is not a file"):
            convert_image_to_base64(tmp_path)

    def test_create_data_url_success(self, sample_image):
        """Test successful creation of data URL."""
        data_url = create_data_url(sample_image)
        assert data_url.startswith("data:image/png;base64,")
        # Verify the base64 part is valid
        base64_part = data_url.split(",")[1]
        assert base64.b64decode(base64_part)

    def test_create_data_url_with_custom_mime(self, sample_image):
        """Test creation of data URL with custom MIME type."""
        custom_mime = "image/custom"
        data_url = create_data_url(sample_image, mime_type=custom_mime)
        assert data_url.startswith(f"data:{custom_mime};base64,")

    def test_create_data_url_invalid_file(self):
        """Test creation of data URL with invalid file."""
        with pytest.raises(FileNotFoundError):
            create_data_url("nonexistent.jpg")

    def test_create_data_url_unrecognized_extension(self, tmp_path):
        """Test creation of data URL with unrecognized file extension."""
        invalid_file = tmp_path / "test.unknown"
        invalid_file.touch()
        with pytest.raises(ValueError, match="Could not determine MIME type"):
            create_data_url(invalid_file)
