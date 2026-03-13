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

    # Models to skip from LLM list (audio, TTS, guards, speech)
    SKIP_PATTERNS = ["whisper", "tts", "guard", "safeguard", "prompt-guard", "saba", "orpheus", "playai"]

    # Phrases that indicate an access/entitlement error rather than a capability error
    ACCESS_ERROR_PHRASES = ["terms acceptance", "terms_required", "model_terms_required", "not available"]

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

            # Step 3: Test LLM models for chat completion and tool calling
            logger.info(f"Testing {len(llm_models)} LLM models for capabilities...")
            for model_id in llm_models:
                supports_chat = self._test_chat_completion(model_id)
                if supports_chat is False:
                    # Model doesn't support chat completions at all (e.g. speech models)
                    non_llm_models.append(model_id)
                    logger.debug(f"{model_id}: does not support chat completions, skipping")
                    continue
                if supports_chat is None:
                    # Transient/access error - assume chat is supported (benefit of the doubt)
                    logger.info(f"{model_id}: chat test indeterminate, assuming chat supported")
                supports_tools = self._test_tool_calling(model_id)
                if supports_tools is None:
                    # Transient/access error on tool test - skip to avoid caching a false negative
                    logger.info(f"{model_id}: tool test indeterminate, skipping (will retry next refresh)")
                    continue
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

        except (requests.RequestException, KeyError, ValueError, ImportError):
            logger.exception("Error discovering models")
            return self._get_fallback_models()
        else:
            return models_metadata

    def _is_access_error(self, error_msg: str) -> bool:
        """Return True if the lowercased error message indicates an access/entitlement issue."""
        return any(phrase in error_msg for phrase in self.ACCESS_ERROR_PHRASES)

    def _fetch_available_models(self) -> list[str]:
        """Fetch list of available models from Groq API."""
        url = f"{self.base_url}/openai/v1/models"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        model_list = response.json()
        # Use direct access to raise KeyError if 'data' is missing
        return [model["id"] for model in model_list["data"]]

    def _test_chat_completion(self, model_id: str) -> bool | None:
        """Test if a model supports basic chat completions.

        This filters out non-chat models (e.g. TTS, speech, embedding models)
        that appear in the API model list but cannot handle chat requests.

        Args:
            model_id: The model ID to test

        Returns:
            True if model supports chat completions, False if it does not,
            None if the result is indeterminate (transient/access errors).
        """
        try:
            import groq

            client = groq.Groq(api_key=self.api_key, base_url=self.base_url)
            messages = [{"role": "user", "content": "test"}]
            client.chat.completions.create(model=model_id, messages=messages, max_tokens=1)

        except ImportError:
            logger.warning("groq package not installed, cannot test chat completion")
            # Propagate the ImportError so callers can fall back to hardcoded model metadata
            raise
        except Exception as e:  # noqa: BLE001
            # The groq SDK does not expose a stable public exception hierarchy: errors can arrive as
            # groq.APIStatusError, groq.BadRequestError, plain ValueError, or even undocumented
            # runtime exceptions depending on the SDK version and the model being probed.  We
            # therefore catch Exception broadly and discriminate solely on the error message text,
            # which is the only reliable signal available across SDK versions.
            error_msg = str(e).lower()
            # Genuine capability error: model does not support chat completions
            if "does not support chat completions" in error_msg:
                logger.debug(f"{model_id}: does not support chat completions")
                return False
            # Access/entitlement errors: model likely supports chat but is not accessible for this key
            if self._is_access_error(error_msg):
                logger.info(f"{model_id}: chat completion not accessible for this API key ({e})")
                # Do not mark the model as non-chat; assume chat is supported but not usable with this key
                return None
            # Other errors (rate limits, transient failures) - indeterminate
            logger.warning(f"Error testing chat for {model_id}: {e}")
            return None
        else:
            return True

    def _test_tool_calling(self, model_id: str) -> bool | None:
        """Test if a model supports tool calling.

        Args:
            model_id: The model ID to test

        Returns:
            True if model supports tool calling, False if it does not,
            None if the result is indeterminate (transient/access errors).
        """
        try:
            import groq

            client = groq.Groq(api_key=self.api_key, base_url=self.base_url)

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

        except ImportError:
            logger.warning("groq package not installed, cannot test tool calling")
            raise
        except Exception as e:  # noqa: BLE001
            # Same rationale as _test_chat_completion: the groq SDK's exception types are not
            # stable across versions, so broad catching with message-based discrimination is the
            # only portable approach.  See _test_chat_completion for a full explanation.
            error_msg = str(e).lower()
            # Genuine capability error: model does not support tools
            if "tool" in error_msg:
                return False
            # Access/entitlement errors: model may support tools but is not accessible for this key
            if self._is_access_error(error_msg):
                logger.info(f"{model_id}: tool calling not testable for this API key ({e})")
                return None
            # Any other API error (rate limits, transient failures, etc) - indeterminate
            logger.warning(f"Error testing tool calling for {model_id}: {e}")
            return None
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
