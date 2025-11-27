"""Dynamic Groq model discovery and tool calling detection.

This module fetches available models directly from the Groq API
and tests their tool calling capabilities programmatically,
eliminating the need for manual metadata updates.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from lfx.log.logger import logger


class GroqModelDiscovery:
    """Discovers and caches Groq model capabilities dynamically."""

    # Cache file location - use local cache directory within models
    CACHE_FILE = Path(__file__).parent / ".cache" / "groq_models_cache.json"
    CACHE_DURATION = timedelta(hours=24)  # Refresh cache every 24 hours

    # Models to skip from LLM list (audio, TTS, guards)
    SKIP_PATTERNS = ["whisper", "tts", "guard", "safeguard", "prompt-guard", "saba"]

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.groq.com"):
        """Initialize discovery with optional API key for testing.

        Args:
            api_key: Groq API key. If None, only cached data will be used.
            base_url: Groq API base URL
        """
        self.api_key = api_key
        self.base_url = base_url

    def get_models(self, *, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
        """Get available models with their capabilities.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Dictionary mapping model IDs to their metadata:
            {
                "model-id": {
                    "name": "model-id",
                    "provider": "Provider Name",
                    "tool_calling": True/False,
                    "preview": True/False,
                    "not_supported": True/False,  # for non-LLM models
                    "last_tested": "2025-01-06T10:30:00"
                }
            }
        """
        # Try to load from cache first
        if not force_refresh:
            cached = self._load_cache()
            if cached:
                logger.info("Using cached Groq model metadata")
                return cached

        # Fetch fresh data from API
        if not self.api_key:
            logger.warning("No API key provided, using minimal fallback list")
            return self._get_fallback_models()

        try:
            models_metadata = {}

            # Step 1: Get list of available models
            available_models = self._fetch_available_models()
            logger.info(f"Found {len(available_models)} models from Groq API")

            # Step 2: Categorize models
            llm_models = []
            non_llm_models = []

            for model_id in available_models:
                if any(pattern in model_id.lower() for pattern in self.SKIP_PATTERNS):
                    non_llm_models.append(model_id)
                else:
                    llm_models.append(model_id)

            # Step 3: Test LLM models for tool calling
            logger.info(f"Testing {len(llm_models)} LLM models for tool calling support...")
            for model_id in llm_models:
                supports_tools = self._test_tool_calling(model_id)
                models_metadata[model_id] = {
                    "name": model_id,
                    "provider": self._get_provider_name(model_id),
                    "tool_calling": supports_tools,
                    "preview": "preview" in model_id.lower() or "/" in model_id,
                    "last_tested": datetime.now(timezone.utc).isoformat(),
                }
                logger.debug(f"{model_id}: tool_calling={supports_tools}")

            # Step 4: Add non-LLM models as unsupported
            for model_id in non_llm_models:
                models_metadata[model_id] = {
                    "name": model_id,
                    "provider": self._get_provider_name(model_id),
                    "not_supported": True,
                    "last_tested": datetime.now(timezone.utc).isoformat(),
                }

            # Save to cache
            self._save_cache(models_metadata)

        except (requests.RequestException, KeyError, ValueError, ImportError) as e:
            logger.exception(f"Error discovering models: {e}")
            return self._get_fallback_models()
        else:
            return models_metadata

    def _fetch_available_models(self) -> list[str]:
        """Fetch list of available models from Groq API."""
        url = f"{self.base_url}/openai/v1/models"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        model_list = response.json()
        # Use direct access to raise KeyError if 'data' is missing
        return [model["id"] for model in model_list["data"]]

    def _test_tool_calling(self, model_id: str) -> bool:
        """Test if a model supports tool calling.

        Args:
            model_id: The model ID to test

        Returns:
            True if model supports tool calling, False otherwise
        """
        try:
            import groq

            client = groq.Groq(api_key=self.api_key)

            # Simple tool definition
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "description": "A test tool",
                        "parameters": {
                            "type": "object",
                            "properties": {"x": {"type": "string"}},
                            "required": ["x"],
                        },
                    },
                }
            ]

            messages = [{"role": "user", "content": "test"}]

            # Try to make a request with tools
            client.chat.completions.create(
                model=model_id, messages=messages, tools=tools, tool_choice="auto", max_tokens=10
            )

        except (ImportError, AttributeError, TypeError, ValueError, RuntimeError, KeyError) as e:
            error_msg = str(e).lower()
            # If error mentions tool calling, model doesn't support it
            if "tool" in error_msg:
                return False
            # Other errors might be rate limits, etc - be conservative
            logger.warning(f"Error testing {model_id}: {e}")
            return False
        else:
            return True

    def _get_provider_name(self, model_id: str) -> str:
        """Extract provider name from model ID."""
        if "/" in model_id:
            provider_map = {
                "meta-llama": "Meta",
                "openai": "OpenAI",
                "groq": "Groq",
                "moonshotai": "Moonshot AI",
                "qwen": "Alibaba Cloud",
            }
            prefix = model_id.split("/")[0]
            return provider_map.get(prefix, prefix.title())

        # Common patterns
        if model_id.startswith("llama"):
            return "Meta"
        if model_id.startswith("qwen"):
            return "Alibaba Cloud"
        if model_id.startswith("allam"):
            return "SDAIA"

        return "Groq"

    def _load_cache(self) -> dict[str, dict] | None:
        """Load cached model metadata if it exists and is fresh."""
        if not self.CACHE_FILE.exists():
            return None

        try:
            with self.CACHE_FILE.open() as f:
                cache_data = json.load(f)

            # Check cache age
            cache_time = datetime.fromisoformat(cache_data["cached_at"])
            if datetime.now(timezone.utc) - cache_time > self.CACHE_DURATION:
                logger.info("Cache expired, will fetch fresh data")
                return None

            return cache_data["models"]

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid cache file: {e}")
            return None

    def _save_cache(self, models_metadata: dict[str, dict]) -> None:
        """Save model metadata to cache."""
        try:
            cache_data = {"cached_at": datetime.now(timezone.utc).isoformat(), "models": models_metadata}

            self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with self.CACHE_FILE.open("w") as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"Cached {len(models_metadata)} models to {self.CACHE_FILE}")

        except (OSError, TypeError, ValueError) as e:
            logger.warning(f"Failed to save cache: {e}")

    def _get_fallback_models(self) -> dict[str, dict]:
        """Return minimal fallback list when API is unavailable."""
        return {
            "llama-3.1-8b-instant": {
                "name": "llama-3.1-8b-instant",
                "provider": "Meta",
                "tool_calling": True,
                "preview": False,
            },
            "llama-3.3-70b-versatile": {
                "name": "llama-3.3-70b-versatile",
                "provider": "Meta",
                "tool_calling": True,
                "preview": False,
            },
        }


# Convenience function for use in other modules
def get_groq_models(api_key: str | None = None, *, force_refresh: bool = False) -> dict[str, dict]:
    """Get Groq models with their capabilities.

    Args:
        api_key: Optional API key for testing. If None, uses cached data.
        force_refresh: If True, bypass cache and fetch fresh data.

    Returns:
        Dictionary of model metadata
    """
    discovery = GroqModelDiscovery(api_key=api_key)
    return discovery.get_models(force_refresh=force_refresh)
