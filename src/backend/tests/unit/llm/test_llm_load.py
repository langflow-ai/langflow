import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest
from langflow.llm.load import _CHAT_MODEL_CACHE, _fetch_llm_instance
from langflow.services.settings.llm import LLMSettings


@pytest.fixture
def reset_cache():
    """Reset the model cache before and after each test."""
    _CHAT_MODEL_CACHE.clear()
    yield
    _CHAT_MODEL_CACHE.clear()


@pytest.fixture
def llm_settings():
    """Create a basic LLMSettings instance for testing."""
    return LLMSettings(
        provider="openai", model="gpt-4o-mini", api_key="test-api-key", base_url="https://api.openai.com/v1"
    )


@pytest.mark.asyncio
async def test_load_llm_missing_api_key():
    """Test that load_llm raises ValueError when api_key is missing."""
    settings = LLMSettings(provider="openai", model="gpt-4o-mini", api_key=None)

    with pytest.raises(ValueError, match="API key is required"):
        await _fetch_llm_instance(settings)


@pytest.mark.asyncio
async def test_load_llm_caching(llm_settings):
    """Test that models are properly cached and reused."""
    mock_model = MagicMock()

    with patch("langflow.llm.load.init_chat_model", return_value=mock_model) as mock_init:
        # First call should initialize the model
        model1 = await _fetch_llm_instance(llm_settings)
        assert model1 == mock_model
        mock_init.assert_called_once()

        # Reset the mock to verify it's not called again
        mock_init.reset_mock()

        # Second call with same settings should use cached model
        model2 = await _fetch_llm_instance(llm_settings)
        assert model2 == mock_model
        mock_init.assert_not_called()

        # Cache should have one entry
        assert len(_CHAT_MODEL_CACHE) == 1


@pytest.mark.asyncio
async def test_load_llm_different_settings(llm_settings):
    """Test that different settings create different cache entries."""
    mock_model1 = MagicMock(name="model1")
    mock_model2 = MagicMock(name="model2")

    with patch("langflow.llm.load.init_chat_model", side_effect=[mock_model1, mock_model2]):
        # First model
        model1 = await _fetch_llm_instance(llm_settings)
        assert model1 == mock_model1

        # Different provider
        different_provider = LLMSettings(provider="anthropic", model="claude-3-haiku-20240307", api_key="test-api-key")
        model2 = await _fetch_llm_instance(different_provider)
        assert model2 == mock_model2

        # Cache should have two entries
        assert len(_CHAT_MODEL_CACHE) == 2


@pytest.mark.asyncio
async def test_load_llm_init_parameters(llm_settings):
    """Test that correct parameters are passed to init_chat_model."""
    with patch("langflow.llm.load.init_chat_model") as mock_init:
        await _fetch_llm_instance(llm_settings)

        mock_init.assert_called_once_with(
            model="gpt-4o-mini", model_provider="openai", api_key="test-api-key", base_url="https://api.openai.com/v1"
        )


@pytest.mark.asyncio
async def test_load_llm_without_base_url():
    """Test loading a model without a base_url attribute."""
    # Create settings without base_url
    settings = LLMSettings(provider="anthropic", model="claude-3-haiku-20240307", api_key="test-api-key")

    # Remove base_url attribute to simulate a settings object without it
    if hasattr(settings, "base_url"):
        delattr(settings, "base_url")

    with patch("langflow.llm.load.init_chat_model") as mock_init:
        await _fetch_llm_instance(settings)

        mock_init.assert_called_once_with(
            model="claude-3-haiku-20240307", model_provider="anthropic", api_key="test-api-key", base_url=None
        )


@pytest.mark.asyncio
async def test_load_llm_concurrent_calls(llm_settings):
    """Test that concurrent calls to load_llm work correctly."""
    mock_model = MagicMock()

    with patch("langflow.llm.load.init_chat_model", return_value=mock_model) as mock_init:
        # Create multiple concurrent calls
        tasks = [_fetch_llm_instance(llm_settings) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All results should be the same model
        assert all(result == mock_model for result in results)

        # init_chat_model should be called exactly once despite concurrent calls
        mock_init.assert_called_once()


# Integration tests with real API keys


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OpenAI API key required")
async def test_load_openai_model_integration():
    """Integration test that loads an actual OpenAI model using environment API key."""
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")

    # Create settings with real API key
    settings = LLMSettings(
        provider="openai",
        model="gpt-3.5-turbo",  # Using a cheaper model for testing
        api_key=api_key,
    )

    # Load the model
    model = await _fetch_llm_instance(settings)

    # Verify the model was loaded correctly
    assert model is not None
    assert hasattr(model, "invoke")

    # Test a simple completion to verify the model works
    try:
        response = await model.ainvoke("Hello, world!")
        assert response is not None
        assert hasattr(response, "content")
        assert isinstance(response.content, str)
        assert len(response.content) > 0
    except (ValueError, TypeError, RuntimeError, ConnectionError) as e:
        pytest.fail(f"Model invocation failed: {e!s}")


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="Anthropic API key required")
async def test_load_anthropic_model_integration():
    """Integration test that loads an actual Anthropic model using environment API key."""
    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")

    # Create settings with real API key - using a more reliable model name
    settings = LLMSettings(
        provider="anthropic",
        model="claude-3-haiku-20240307",  # Using the base model name without version
        api_key=api_key,
    )

    # Load the model
    try:
        model = await _fetch_llm_instance(settings)

        # Verify the model was loaded correctly
        assert model is not None
        assert hasattr(model, "invoke")

        # Test a simple completion to verify the model works
        try:
            response = await model.ainvoke("Hello, world!")
            assert response is not None
            assert hasattr(response, "content")
            assert isinstance(response.content, str)
            assert len(response.content) > 0
        except (ValueError, TypeError, RuntimeError, ConnectionError) as e:
            pytest.fail(f"Anthropic model invocation failed: {e!s}")
    except (ValueError, TypeError, RuntimeError, ConnectionError) as e:
        pytest.fail(f"Anthropic model test failed: {e!s}")


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OpenAI API key required")
async def test_load_openai_model_caching_integration():
    """Integration test that verifies caching works with real models."""
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")

    # Create settings with real API key
    settings = LLMSettings(provider="openai", model="gpt-3.5-turbo", api_key=api_key)

    # Load the model twice
    model1 = await _fetch_llm_instance(settings)
    model2 = await _fetch_llm_instance(settings)

    # Verify both references point to the same object (cached)
    assert model1 is model2

    # Verify cache has one entry
    assert len(_CHAT_MODEL_CACHE) == 1


@pytest.mark.asyncio
@pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") and os.getenv("ANTHROPIC_API_KEY")),
    reason="Both OpenAI and Anthropic API keys required",
)
async def test_load_multiple_providers_integration():
    """Integration test that loads models from different providers."""
    # Get API keys from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    # Create settings for OpenAI
    openai_settings = LLMSettings(provider="openai", model="gpt-3.5-turbo", api_key=openai_api_key)

    # Create settings for Anthropic - using a more reliable model name
    anthropic_settings = LLMSettings(provider="anthropic", model="claude-3-haiku-20240307", api_key=anthropic_api_key)

    # Load both models
    openai_model = await _fetch_llm_instance(openai_settings)

    # Verify OpenAI model was loaded correctly
    assert openai_model is not None
    assert hasattr(openai_model, "invoke")

    # Test OpenAI model
    try:
        openai_response = await openai_model.ainvoke("Hello from OpenAI!")
        assert openai_response is not None
        assert len(openai_response.content) > 0
    except (ValueError, TypeError, RuntimeError, ConnectionError) as e:
        pytest.fail(f"OpenAI model invocation failed: {e!s}")

    # Try to load Anthropic model, but skip if it fails
    try:
        anthropic_model = await _fetch_llm_instance(anthropic_settings)
        assert anthropic_model is not None
        assert hasattr(anthropic_model, "invoke")

        # Verify they are different models
        assert openai_model is not anthropic_model

        # Verify cache has two entries
        assert len(_CHAT_MODEL_CACHE) == 2

        # Test Anthropic model
        try:
            anthropic_response = await anthropic_model.ainvoke("Hello from Anthropic!")
            assert anthropic_response is not None
            assert len(anthropic_response.content) > 0
        except (ValueError, TypeError, RuntimeError, ConnectionError) as e:
            pytest.fail(f"Anthropic model invocation failed: {e!s}")
    except (ValueError, TypeError, RuntimeError, ConnectionError) as e:
        pytest.fail(f"Anthropic model in multiple providers test failed: {e!s}")
