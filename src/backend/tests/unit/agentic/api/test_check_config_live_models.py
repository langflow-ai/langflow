"""check-config must surface live installed models for live providers.

Reproduced live (2026-06-12, release-1.11.0, Ollama-only setup):
``GET /agentic/check-config`` returns the STATIC Ollama catalog (37
models headed by ``llama3.3``) while the running Ollama server has only
``gpt-oss:20b``, ``llama3.2:latest`` and ``qwen2.5:1.5b`` installed. The
frontend picker and the backend default both point at models that 404.

The live fetch boundary (``get_live_models_for_provider``, reached via
``list_installed_tool_calling_models``) is mocked: it requires an
external Ollama server CI cannot reproduce.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langflow.agentic.api.router import check_assistant_config
from langflow.services.database.models.user.model import User

ROUTER_MODULE = "langflow.agentic.api.router"
PROVIDER_MODULE = "langflow.agentic.services.provider_service"

INSTALLED_OLLAMA_MODELS = [
    {"name": "gpt-oss:20b", "tool_calling": True, "model_type": "llm"},
    {"name": "llama3.2:latest", "tool_calling": True, "model_type": "llm"},
    {"name": "qwen2.5:1.5b", "tool_calling": True, "model_type": "llm"},
]


class TestCheckConfigLiveModels:
    @pytest.mark.asyncio
    async def test_should_list_installed_models_when_ollama_is_the_provider(self):
        user = User(id=uuid4(), username="tester")
        with (
            patch(
                f"{ROUTER_MODULE}.get_enabled_providers_for_user",
                new_callable=AsyncMock,
                return_value=(["Ollama"], {"Ollama": True}),
            ),
            patch(
                f"{PROVIDER_MODULE}.get_live_models_for_provider",
                return_value=INSTALLED_OLLAMA_MODELS,
            ),
        ):
            config = await check_assistant_config(current_user=user, session=AsyncMock())

        ollama = next(p for p in config["providers"] if p["name"] == "Ollama")
        model_names = [m["name"] for m in ollama["models"]]
        assert model_names == ["gpt-oss:20b", "llama3.2:latest", "qwen2.5:1.5b"], (
            f"Expected the installed models, got the static catalog: {model_names[:5]}..."
        )

    @pytest.mark.asyncio
    async def test_should_default_to_an_installed_model_not_the_catalog_default(self):
        user = User(id=uuid4(), username="tester")
        with (
            patch(
                f"{ROUTER_MODULE}.get_enabled_providers_for_user",
                new_callable=AsyncMock,
                return_value=(["Ollama"], {"Ollama": True}),
            ),
            patch(
                f"{PROVIDER_MODULE}.get_live_models_for_provider",
                return_value=INSTALLED_OLLAMA_MODELS,
            ),
        ):
            config = await check_assistant_config(current_user=user, session=AsyncMock())

        assert config["default_provider"] == "Ollama"
        assert config["default_model"] == "gpt-oss:20b", (
            f"Default must be an installed model, got: {config['default_model']}"
        )

    @pytest.mark.asyncio
    async def test_should_keep_static_catalog_when_live_fetch_returns_nothing(self):
        user = User(id=uuid4(), username="tester")
        with (
            patch(
                f"{ROUTER_MODULE}.get_enabled_providers_for_user",
                new_callable=AsyncMock,
                return_value=(["Ollama"], {"Ollama": True}),
            ),
            patch(
                f"{PROVIDER_MODULE}.get_live_models_for_provider",
                return_value=[],
            ),
        ):
            config = await check_assistant_config(current_user=user, session=AsyncMock())

        ollama = next(p for p in config["providers"] if p["name"] == "Ollama")
        assert ollama["models"], "Static catalog must remain as fallback when live fetch fails"
        assert config["default_model"] == "llama3.3"
