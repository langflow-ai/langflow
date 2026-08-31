"""The user's explicit default model is the only source of an auto-selection.

Companion to ``src/lfx/tests/unit/base/models/test_build_config_no_unconfigured_default.py``
for LE-2168. These cases need the langflow ``DatabaseVariableService``, which the isolated
lfx test environment deliberately does not install.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from langflow.services.variable.service import DatabaseVariableService
from lfx.base.models.unified_models.build_config import update_model_options_in_build_config

BUILD_CONFIG_MODULE = "lfx.base.models.unified_models.build_config"


def _component(user_id: str = "3f1a0c9e-5b7d-4f2a-9c3e-1d2b3a4c5d6e") -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id, cache={}, inputs=[])


def _get_options(user_id=None):  # noqa: ARG001
    return [
        {"name": "claude-sonnet-4-5", "provider": "Anthropic", "icon": "Anthropic", "metadata": {}},
        {"name": "gemini-2.5-flash", "provider": "Google Generative AI", "icon": "GoogleGenerativeAI", "metadata": {}},
        {"name": "gpt-4o-mini", "provider": "OpenAI", "icon": "OpenAI", "metadata": {}},
    ]


@asynccontextmanager
async def _fake_session_scope():
    yield MagicMock()


def _patched_default_variable(payload: dict | None):
    """Patch the variable service so ``__default_language_model__`` resolves to *payload*."""
    variable_service = MagicMock(spec=DatabaseVariableService)
    if payload is None:
        variable_service.get_variable_object = AsyncMock(side_effect=ValueError("not found"))
    else:
        variable_service.get_variable_object = AsyncMock(return_value=SimpleNamespace(value=json.dumps(payload)))
    return patch.multiple(
        BUILD_CONFIG_MODULE,
        get_variable_service=MagicMock(return_value=variable_service),
        session_scope=_fake_session_scope,
    )


def _update_on_initial_load(build_config: dict):
    return update_model_options_in_build_config(
        component=_component(),
        build_config=build_config,
        cache_key_prefix="language_model_options",
        get_options_func=_get_options,
        field_name=None,
        field_value=None,
    )


def test_initial_load_uses_the_users_default_model():
    """An explicitly chosen default is a real configuration and still auto-fills."""
    with _patched_default_variable({"model_name": "gpt-4o-mini", "provider": "OpenAI"}):
        result = _update_on_initial_load({"model": {"value": [], "options": []}})

    assert result["model"]["value"][0]["name"] == "gpt-4o-mini"
    assert result["model"]["value"][0]["provider"] == "OpenAI"


def test_initial_load_ignores_default_that_is_not_available():
    """A stale preference pointing at a disabled provider must not fall back to options[0]."""
    with _patched_default_variable({"model_name": "grok-4", "provider": "xAI"}):
        result = _update_on_initial_load({"model": {"value": [], "options": []}})

    assert not result["model"]["value"]


def test_initial_load_stays_empty_when_no_default_is_stored():
    """Without a stored preference the field stays empty even though options exist."""
    with _patched_default_variable(None):
        result = _update_on_initial_load({"model": {"value": [], "options": []}})

    assert not result["model"]["value"]
