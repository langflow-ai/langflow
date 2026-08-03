"""Regression guards for Ollama base URL precedence in unified ``get_llm``."""

from __future__ import annotations

from unittest.mock import patch

import lfx.base.models.unified_models as unified_models_module
import pytest
from lfx.base.models.unified_models.instantiation import get_llm


def _capture_factory():
    captured: dict = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    return FakeChatModel, captured


def _ollama_model_selection() -> list[dict]:
    return [
        {
            "name": "llama3.2",
            "provider": "Ollama",
            "metadata": {
                "model_class": "ChatOllama",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
                "base_url_param": "base_url",
            },
        }
    ]


@pytest.mark.parametrize(
    ("component_url", "provider_url", "env_url", "expected_url"),
    [
        (
            "http://component-ollama:11434",
            "http://provider-ollama:11434",
            "http://env-ollama:11434",
            "http://component-ollama:11434",
        ),
        ("", "http://provider-ollama:11434", "http://env-ollama:11434", "http://provider-ollama:11434"),
        ("", None, "http://env-ollama:11434", "http://env-ollama:11434"),
        ("", None, None, "http://localhost:11434"),
    ],
    ids=["component", "provider-variable", "environment", "localhost-fallback"],
)
def test_get_llm_resolves_ollama_base_url_by_precedence(
    monkeypatch,
    component_url,
    provider_url,
    env_url,
    expected_url,
):
    """Resolve component, provider variable, environment, then localhost fallback."""
    if env_url is None:
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("OLLAMA_BASE_URL", env_url)

    provider_vars = {"OLLAMA_BASE_URL": provider_url} if provider_url else {}
    fake_cls, captured = _capture_factory()

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value=None),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value=provider_vars),
    ):
        get_llm(
            _ollama_model_selection(),
            user_id=None,
            ollama_base_url=component_url,
        )

    assert captured["base_url"] == expected_url
