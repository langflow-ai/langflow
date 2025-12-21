"""Integration tests for image content dict format with real LLM providers.

These tests verify that the standardized image content dict format works
correctly with actual API calls to OpenAI, Anthropic, and Google Gemini.
Tests are skipped if required API keys are not available.
"""

import base64
import os

import pytest
from langflow.utils.image import create_image_content_dict

from tests.api_keys import has_api_key


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


@pytest.fixture
def sample_jpeg_image(tmp_path):
    """Create a sample image file with .jpg extension for testing MIME type detection."""
    # Use the same PNG data but with .jpg extension to test MIME detection
    # This tests that our code correctly detects MIME type from file extension
    image_content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    image_path = tmp_path / "test_image.jpg"  # .jpg extension
    image_path.write_bytes(image_content)
    return image_path


# use shared has_api_key from tests.api_keys


@pytest.mark.skipif(not has_api_key("OPENAI_API_KEY"), reason="OPENAI_API_KEY not available in CI")
def test_openai_vision_api_real_call(sample_image):
    """Test that image content dict works with real OpenAI Vision API calls."""
    try:
        import openai
    except ImportError:
        pytest.skip("OpenAI package not installed")

    from tests.api_keys import get_openai_api_key

    client = openai.OpenAI(api_key=get_openai_api_key())
    content_dict = create_image_content_dict(sample_image)

    # Test the message structure with OpenAI
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "What color is this image? Just answer with one word."}, content_dict],
        }
    ]

    try:
        response = client.chat.completions.create(model="gpt-4o-mini", messages=messages, max_tokens=10)

        # If we get here without an exception, the format is accepted
        assert response.choices[0].message.content is not None

    except Exception as e:
        pytest.fail(f"OpenAI API call failed with image content dict format: {e}")


@pytest.mark.skipif(not has_api_key("OPENAI_API_KEY"), reason="OPENAI_API_KEY not available in CI")
def test_openai_vision_api_with_jpeg(sample_jpeg_image):
    """Test OpenAI Vision API with JPEG image format."""
    try:
        import openai
    except ImportError:
        pytest.skip("OpenAI package not installed")

    from tests.api_keys import get_openai_api_key

    client = openai.OpenAI(api_key=get_openai_api_key())
    content_dict = create_image_content_dict(sample_jpeg_image)

    # Verify JPEG format is correctly detected from file extension
    assert "data:image/jpeg;base64," in content_dict["image_url"]["url"]

    messages = [
        {"role": "user", "content": [{"type": "text", "text": "Describe this image in one word."}, content_dict]}
    ]

    try:
        response = client.chat.completions.create(model="gpt-4o-mini", messages=messages, max_tokens=10)

        assert response.choices[0].message.content is not None
        # API call successful

    except Exception as e:
        pytest.fail(f"OpenAI API call failed with JPEG image: {e}")


@pytest.mark.skipif(not has_api_key("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not available in CI")
def test_anthropic_vision_api_real_call(sample_image):
    """Test that image content dict works with real Anthropic Claude API calls."""
    try:
        import anthropic
    except ImportError:
        pytest.skip("Anthropic package not installed")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    content_dict = create_image_content_dict(sample_image)

    # Convert our standardized format to Anthropic's format
    data_url = content_dict["image_url"]["url"]
    mime_type, base64_data = data_url.split(";base64,")
    mime_type = mime_type.replace("data:", "")

    # Anthropic format
    anthropic_image = {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": base64_data}}

    # Test the message structure with Anthropic Claude
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "What is in this image? Answer in one word."}, anthropic_image],
        }
    ]

    try:
        response = client.messages.create(model="claude-3-haiku-20240307", max_tokens=10, messages=messages)

        # If we get here without an exception, the format conversion worked
        assert response.content[0].text is not None
        # API call successful

    except Exception as e:
        pytest.fail(f"Anthropic API call failed when converting from image content dict format: {e}")


@pytest.mark.skipif(not has_api_key("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not available in CI")
def test_anthropic_vision_api_with_jpeg(sample_jpeg_image):
    """Test Anthropic Claude API with JPEG image format."""
    try:
        import anthropic
    except ImportError:
        pytest.skip("Anthropic package not installed")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    content_dict = create_image_content_dict(sample_jpeg_image)

    # Verify JPEG format is correctly detected from file extension
    assert "data:image/jpeg;base64," in content_dict["image_url"]["url"]

    # Convert our standardized format to Anthropic's format
    data_url = content_dict["image_url"]["url"]
    mime_type, base64_data = data_url.split(";base64,")
    mime_type = mime_type.replace("data:", "")

    # Anthropic format
    anthropic_image = {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": base64_data}}

    messages = [
        {"role": "user", "content": [{"type": "text", "text": "What do you see? One word answer."}, anthropic_image]}
    ]

    try:
        response = client.messages.create(model="claude-3-haiku-20240307", max_tokens=10, messages=messages)

        assert response.content[0].text is not None
        # API call successful

    except Exception as e:
        pytest.fail(f"Anthropic API call failed with JPEG image: {e}")


@pytest.mark.skipif(not has_api_key("GEMINI_API_KEY"), reason="GEMINI_API_KEY not available in CI")
def test_google_gemini_vision_api_real_call(sample_image):
    """Test that image content dict works with real Google Gemini API calls."""
    try:
        import google.generativeai as genai
    except ImportError:
        pytest.skip("Google Generative AI package not installed")

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    content_dict = create_image_content_dict(sample_image)

    # Convert our format to what Gemini expects
    # Gemini uses a different format, but we need to verify our dict doesn't break when converted
    try:
        # Extract the data URL from our format
        data_url = content_dict["image_url"]["url"]

        # For Gemini, we need to extract just the base64 part
        mime_type, base64_data = data_url.split(";base64,")
        mime_type = mime_type.replace("data:", "")

        # Gemini format
        gemini_image = {"mime_type": mime_type, "data": base64.b64decode(base64_data)}

        response = model.generate_content(["What is in this image? Answer in one word.", gemini_image])

        assert response.text is not None
        # API call successful

    except Exception as e:
        pytest.fail(f"Google Gemini API call failed when processing image content dict: {e}")


@pytest.mark.skipif(not has_api_key("GEMINI_API_KEY"), reason="GEMINI_API_KEY not available in CI")
def test_google_gemini_vision_api_with_jpeg(sample_jpeg_image):
    """Test Google Gemini API with JPEG image format."""
    try:
        import google.generativeai as genai
    except ImportError:
        pytest.skip("Google Generative AI package not installed")

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    content_dict = create_image_content_dict(sample_jpeg_image)

    # Verify JPEG format is correctly detected from file extension
    assert "data:image/jpeg;base64," in content_dict["image_url"]["url"]

    try:
        # Convert our format for Gemini
        data_url = content_dict["image_url"]["url"]
        mime_type, base64_data = data_url.split(";base64,")
        mime_type = mime_type.replace("data:", "")

        gemini_image = {"mime_type": mime_type, "data": base64.b64decode(base64_data)}

        response = model.generate_content(["Describe this image briefly.", gemini_image])

        assert response.text is not None
        # API call successful

    except Exception as e:
        pytest.fail(f"Google Gemini API call failed with JPEG image: {e}")


def test_langchain_integration_format_compatibility(sample_image):
    """Test that the image content dict integrates properly with LangChain message formats."""
    content_dict = create_image_content_dict(sample_image)

    # Test LangChain-style message structure
    langchain_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Analyze this image"},
            content_dict,  # Our standardized format should fit here
        ],
    }

    # Verify the structure is what LangChain expects
    assert len(langchain_message["content"]) == 2
    text_part = langchain_message["content"][0]
    image_part = langchain_message["content"][1]

    assert text_part["type"] == "text"
    assert image_part["type"] == "image_url"
    assert "image_url" in image_part
    assert "url" in image_part["image_url"]

    # This format should be compatible with LangChain's OpenAI and Anthropic integrations
    # because it follows the standardized structure they expect


@pytest.mark.skipif(
    not (has_api_key("OPENAI_API_KEY") and has_api_key("ANTHROPIC_API_KEY")),
    reason="Both OPENAI_API_KEY and ANTHROPIC_API_KEY needed for cross-provider test",
)
def test_cross_provider_consistency(sample_image):
    """Test that the same image content dict works across multiple providers."""
    content_dict = create_image_content_dict(sample_image)

    # Test with OpenAI
    try:
        import openai

        from tests.api_keys import get_openai_api_key

        openai_client = openai.OpenAI(api_key=get_openai_api_key())

        openai_response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": [{"type": "text", "text": "What color is this? One word."}, content_dict]}
            ],
            max_tokens=5,
        )

        openai_result = openai_response.choices[0].message.content
        # API call successful

    except ImportError:
        pytest.skip("OpenAI package not available for cross-provider test")

    # Test with Anthropic using the same content_dict (but converted to Anthropic format)
    try:
        import anthropic

        anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Convert our standardized format to Anthropic's format
        data_url = content_dict["image_url"]["url"]
        mime_type, base64_data = data_url.split(";base64,")
        mime_type = mime_type.replace("data:", "")

        anthropic_image = {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": base64_data}}

        anthropic_response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=5,
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "What color is this? One word."}, anthropic_image],
                }
            ],
        )

        anthropic_result = anthropic_response.content[0].text
        # API call successful

    except ImportError:
        pytest.skip("Anthropic package not available for cross-provider test")

    # Both should process the same format successfully
    # (We don't assert they give the same answer since models may interpret differently)
    assert openai_result is not None
    assert anthropic_result is not None


def test_error_handling_without_api_keys(sample_image):
    """Test that image content dict format is valid even without API access."""
    content_dict = create_image_content_dict(sample_image)

    # The format should be correct regardless of API availability
    assert content_dict["type"] == "image_url"
    assert "image_url" in content_dict
    assert "url" in content_dict["image_url"]

    # Should not contain legacy fields that caused provider issues
    assert "source_type" not in content_dict
    assert "source" not in content_dict
    assert "media_type" not in content_dict

    # URL should be a valid data URL
    url = content_dict["image_url"]["url"]
    assert url.startswith("data:image/")
    assert ";base64," in url

    # Base64 part should be valid
    base64_part = url.split(";base64,")[1]
    assert base64.b64decode(base64_part)


if __name__ == "__main__":
    # Print which API keys are available for manual testing
    keys_available = []
    if has_api_key("OPENAI_API_KEY"):
        keys_available.append("OpenAI")
    if has_api_key("ANTHROPIC_API_KEY"):
        keys_available.append("Anthropic")
    if has_api_key("GEMINI_API_KEY"):
        keys_available.append("Gemini")

    # Available API keys can be checked via has_api_key() function
