import base64

import pytest
from langflow.utils.image import convert_image_to_base64, create_data_url, create_image_content_dict


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


def test_convert_image_to_base64_success(sample_image):
    """Test successful conversion of image to base64."""
    base64_str = convert_image_to_base64(sample_image)
    assert isinstance(base64_str, str)
    # Verify it's valid base64
    assert base64.b64decode(base64_str)


def test_convert_image_to_base64_empty_path():
    """Test conversion with empty path."""
    with pytest.raises(ValueError, match="Image path cannot be empty"):
        convert_image_to_base64("")


def test_convert_image_to_base64_nonexistent_file():
    """Test conversion with non-existent file."""
    with pytest.raises(FileNotFoundError, match="Image file not found"):
        convert_image_to_base64("nonexistent.png")


def test_convert_image_to_base64_directory(tmp_path):
    """Test conversion with directory path instead of file."""
    with pytest.raises(ValueError, match="Path is not a file"):
        convert_image_to_base64(tmp_path)


def test_create_data_url_success(sample_image):
    """Test successful creation of data URL."""
    data_url = create_data_url(sample_image)
    assert data_url.startswith("data:image/png;base64,")
    # Verify the base64 part is valid
    base64_part = data_url.split(",")[1]
    assert base64.b64decode(base64_part)


def test_create_data_url_with_custom_mime(sample_image):
    """Test creation of data URL with custom MIME type."""
    custom_mime = "image/custom"
    data_url = create_data_url(sample_image, mime_type=custom_mime)
    assert data_url.startswith(f"data:{custom_mime};base64,")


def test_create_data_url_invalid_file():
    """Test creation of data URL with invalid file."""
    with pytest.raises(FileNotFoundError):
        create_data_url("nonexistent.jpg")


def test_create_data_url_unrecognized_extension(tmp_path):
    """Test creation of data URL with unrecognized file extension."""
    invalid_file = tmp_path / "test.unknown"
    invalid_file.touch()
    with pytest.raises(ValueError, match="Could not determine MIME type"):
        create_data_url(invalid_file)


def test_create_image_content_dict_success(sample_image):
    """Test successful creation of image content dict."""
    content_dict = create_image_content_dict(sample_image)
    assert content_dict["type"] == "image_url"
    assert "image_url" in content_dict
    assert "url" in content_dict["image_url"]
    assert content_dict["image_url"]["url"].startswith("data:image/png;base64,")
    # Verify the base64 part is valid
    base64_part = content_dict["image_url"]["url"].split(",")[1]
    assert base64.b64decode(base64_part)


def test_create_image_content_dict_with_custom_mime(sample_image):
    """Test creation of image content dict with custom MIME type."""
    custom_mime = "image/custom"
    content_dict = create_image_content_dict(sample_image, mime_type=custom_mime)
    assert content_dict["type"] == "image_url"
    assert "image_url" in content_dict
    assert "url" in content_dict["image_url"]
    assert content_dict["image_url"]["url"].startswith(f"data:{custom_mime};base64,")


def test_create_image_content_dict_invalid_file():
    """Test creation of image content dict with invalid file."""
    with pytest.raises(FileNotFoundError):
        create_image_content_dict("nonexistent.jpg")


def test_create_image_content_dict_unrecognized_extension(tmp_path):
    """Test creation of image content dict with unrecognized file extension."""
    invalid_file = tmp_path / "test.unknown"
    invalid_file.touch()
    with pytest.raises(ValueError, match="Could not determine MIME type"):
        create_image_content_dict(invalid_file)


def test_create_image_content_dict_format_compatibility(sample_image):
    """Test that the image content dict format is compatible with different LLM providers."""
    content_dict = create_image_content_dict(sample_image)

    # Test the new format structure that should work with Google/Gemini
    assert content_dict["type"] == "image_url"
    assert "image_url" in content_dict
    assert isinstance(content_dict["image_url"], dict)
    assert "url" in content_dict["image_url"]

    # Test that the URL is a valid data URL
    url = content_dict["image_url"]["url"]
    assert url.startswith("data:")
    assert ";base64," in url

    # Verify the structure matches OpenAI's expected format
    # OpenAI expects: {"type": "image_url", "image_url": {"url": "data:..."}}
    assert all(key in ["type", "image_url"] for key in content_dict)
    assert all(key in ["url"] for key in content_dict["image_url"])


def test_image_content_dict_google_gemini_compatibility(sample_image):
    """Test that the format resolves the original Gemini error."""
    content_dict = create_image_content_dict(sample_image)

    # The original error was: "Unrecognized message part type: image"
    # This should now be "image_url" which Gemini supports
    assert content_dict["type"] == "image_url"

    # Gemini should accept this format without the "source_type" field
    # that was causing issues in the old format
    assert "source_type" not in content_dict

    # The nested structure should match what Gemini expects
    assert "image_url" in content_dict
    assert "url" in content_dict["image_url"]


def test_image_content_dict_openai_compatibility(sample_image):
    """Test compatibility with OpenAI's expected image format."""
    content_dict = create_image_content_dict(sample_image)

    # OpenAI Vision API expects exactly this structure:
    # {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    expected_keys = {"type", "image_url"}
    assert set(content_dict.keys()) == expected_keys

    assert content_dict["type"] == "image_url"
    assert isinstance(content_dict["image_url"], dict)
    assert "url" in content_dict["image_url"]

    # OpenAI accepts data URLs with base64 encoding
    url = content_dict["image_url"]["url"]
    assert url.startswith("data:image/")
    assert ";base64," in url


def test_image_content_dict_anthropic_compatibility(sample_image):
    """Test compatibility with Anthropic's expected image format."""
    content_dict = create_image_content_dict(sample_image)

    # Anthropic Claude also uses the image_url format for vision
    # This format should be compatible
    assert content_dict["type"] == "image_url"
    assert "image_url" in content_dict

    # Anthropic accepts base64 data URLs
    url = content_dict["image_url"]["url"]
    assert url.startswith("data:")
    assert "base64" in url


def test_image_content_dict_langchain_message_compatibility(sample_image):
    """Test that the format integrates well with LangChain message structures."""
    content_dict = create_image_content_dict(sample_image)

    # Simulate how this would be used in a LangChain message
    message_content = [{"type": "text", "text": "What do you see in this image?"}, content_dict]

    # Verify the message structure is valid
    text_part = message_content[0]
    image_part = message_content[1]

    assert text_part["type"] == "text"
    assert image_part["type"] == "image_url"
    assert "image_url" in image_part
    assert "url" in image_part["image_url"]


def test_image_content_dict_no_legacy_fields(sample_image):
    """Test that legacy fields that caused issues are not present."""
    content_dict = create_image_content_dict(sample_image)

    # These fields from the old format should not be present
    # as they caused compatibility issues with some providers
    legacy_fields = ["source_type", "source", "media_type"]

    for field in legacy_fields:
        assert field not in content_dict, f"Legacy field '{field}' should not be present"
        assert field not in content_dict.get("image_url", {}), f"Legacy field '{field}' should not be in image_url"


def test_image_content_dict_multiple_formats(tmp_path):
    """Test that the format works consistently across different image types."""
    # Test with different image formats
    formats_to_test = [
        ("test.png", "image/png"),
        ("test.jpg", "image/jpeg"),
        ("test.gif", "image/gif"),
        ("test.webp", "image/webp"),
    ]

    # Use the same image content for all formats (the test PNG data)
    image_content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )

    for filename, expected_mime in formats_to_test:
        image_path = tmp_path / filename
        image_path.write_bytes(image_content)

        try:
            content_dict = create_image_content_dict(image_path)

            # All formats should produce the same structure
            assert content_dict["type"] == "image_url"
            assert "image_url" in content_dict
            assert "url" in content_dict["image_url"]

            # The MIME type should be detected correctly
            url = content_dict["image_url"]["url"]
            assert url.startswith(f"data:{expected_mime};base64,")

        except ValueError as e:
            # Some formats might not be supported, which is fine
            if "Could not determine MIME type" not in str(e):
                raise
