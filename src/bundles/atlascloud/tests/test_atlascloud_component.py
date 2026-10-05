"""Unit tests for the Atlas Cloud extension bundle (``lfx-atlascloud``).

These travel with the bundle and import its public entry point, exercising the
server-free surface (component metadata, model building, live model fetching
with its static fallback and non-chat filter, and input structure) with
``ChatOpenAI`` and the HTTP call monkeypatched -- no network access and no
Atlas Cloud API key is required.

The in-tree fixture ``tests.base.ComponentTestBaseWithoutClient`` is not
importable inside a standalone bundle, so these are plain pytest functions, the
way the empiriolabs bundle's tests are.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from lfx_atlascloud import AtlasCloudModelComponent
from lfx_atlascloud.components.atlascloud.atlascloud import (
    ATLASCLOUD_BASE_URL,
    ATLASCLOUD_MODELS,
    MODEL_NAMES,
)

CHATOPENAI_PATH = "lfx_atlascloud.components.atlascloud.atlascloud.ChatOpenAI"

DEFAULT_KWARGS = {
    "api_key": "test-atlascloud-key",  # pragma: allowlist secret
    "model_name": "deepseek-ai/DeepSeek-V3.1-Terminus",
    "temperature": 0.1,
    "max_tokens": 1000,
    "seed": 1,
    "json_mode": False,
    "model_kwargs": {},
    "stream": False,
}


# --------------------------------------------------------------------------- #
# Bundle entry point
# --------------------------------------------------------------------------- #
def test_bundle_entrypoint_exports():
    assert AtlasCloudModelComponent.__name__ == "AtlasCloudModelComponent"
    assert AtlasCloudModelComponent.name == "AtlasCloudModel"


# --------------------------------------------------------------------------- #
# Model constants
# --------------------------------------------------------------------------- #
def test_atlascloud_models_not_empty():
    assert isinstance(ATLASCLOUD_MODELS, list)
    assert len(ATLASCLOUD_MODELS) > 0


def test_model_names_alias():
    assert MODEL_NAMES == ATLASCLOUD_MODELS
    assert MODEL_NAMES is ATLASCLOUD_MODELS


def test_models_are_unique_strings():
    for model in ATLASCLOUD_MODELS:
        assert isinstance(model, str)
        assert model
    assert len(ATLASCLOUD_MODELS) == len(set(ATLASCLOUD_MODELS))


def test_specific_models_present():
    for expected in ["deepseek-ai/DeepSeek-V3.1-Terminus", "zai-org/glm-4.7", "moonshotai/kimi-k2.6"]:
        assert expected in ATLASCLOUD_MODELS


# --------------------------------------------------------------------------- #
# Chat-model component
# --------------------------------------------------------------------------- #
def test_basic_setup():
    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))

    assert component.display_name == "Atlas Cloud"
    assert component.description == "Generates text using Atlas Cloud LLMs (OpenAI compatible)."
    assert component.icon == "AtlasCloud"
    assert component.name == "AtlasCloudModel"
    assert component.api_key == "test-atlascloud-key"  # pragma: allowlist secret
    assert component.model_name == "deepseek-ai/DeepSeek-V3.1-Terminus"
    assert component.temperature == 0.1
    assert component.max_tokens == 1000
    assert component.seed == 1
    assert component.json_mode is False


@patch(CHATOPENAI_PATH)
def test_build_model_success(mock_chat_openai):
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance

    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    model = component.build_model()

    mock_chat_openai.assert_called_once_with(
        model="deepseek-ai/DeepSeek-V3.1-Terminus",
        api_key="test-atlascloud-key",  # pragma: allowlist secret
        max_tokens=1000,
        temperature=0.1,
        model_kwargs={},
        streaming=False,
        seed=1,
        base_url=ATLASCLOUD_BASE_URL,
    )
    assert model == mock_instance


@patch(CHATOPENAI_PATH)
def test_build_model_with_json_mode(mock_chat_openai):
    mock_instance = MagicMock()
    mock_bound_instance = MagicMock()
    mock_instance.bind.return_value = mock_bound_instance
    mock_chat_openai.return_value = mock_instance

    kwargs = dict(DEFAULT_KWARGS)
    kwargs["json_mode"] = True
    component = AtlasCloudModelComponent()
    component.set_attributes(kwargs)
    model = component.build_model()

    mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
    assert model == mock_bound_instance


@patch(CHATOPENAI_PATH)
def test_build_model_with_streaming(mock_chat_openai):
    mock_chat_openai.return_value = MagicMock()

    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    component.stream = True
    component.build_model()

    _args, kwargs = mock_chat_openai.call_args
    assert kwargs["streaming"] is True


@patch(CHATOPENAI_PATH)
def test_build_model_exception_handling(mock_chat_openai):
    mock_chat_openai.side_effect = ValueError("Invalid API key")

    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))

    with pytest.raises(ValueError, match="Could not connect to Atlas Cloud API"):
        component.build_model()


# --------------------------------------------------------------------------- #
# Live catalog
# --------------------------------------------------------------------------- #
@patch("requests.get")
def test_get_models_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": "deepseek-ai/DeepSeek-V3.1-Terminus"}, {"id": "zai-org/glm-4.7"}]
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    models = component.get_models()

    assert models == ["deepseek-ai/DeepSeek-V3.1-Terminus", "zai-org/glm-4.7"]
    mock_get.assert_called_once()
    assert mock_get.call_args[0][0] == f"{ATLASCLOUD_BASE_URL}/models"


@patch("requests.get")
def test_get_models_drops_non_chat_entries(mock_get):
    """The catalog marks its image models as text output, so they are filtered by id."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"id": "deepseek-ai/DeepSeek-V3.1-Terminus"},
            {"id": "openai/gpt-image-2"},
            {"id": "google/gemini-3-pro-image"},
            {"id": "deepseek-ai/deepseek-ocr"},
            {"id": "zai-org/glm-4.7"},
        ]
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))

    assert component.get_models() == ["deepseek-ai/DeepSeek-V3.1-Terminus", "zai-org/glm-4.7"]


@patch("requests.get")
def test_get_models_falls_back_when_everything_is_filtered(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "openai/gpt-image-2"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))

    assert component.get_models() == MODEL_NAMES


@patch("requests.get")
def test_get_models_fallback(mock_get):
    mock_get.side_effect = requests.RequestException("Network error")

    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    models = component.get_models()

    assert models == MODEL_NAMES
    assert "Error fetching models" in component.status


@patch("requests.get")
def test_get_models_sends_the_key_when_present(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "zai-org/glm-4.7"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    component.get_models()

    headers = mock_get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-atlascloud-key"  # pragma: allowlist secret


@patch("requests.get")
def test_get_models_works_without_a_key(mock_get):
    """Atlas Cloud serves /v1/models unauthenticated, so the dropdown fills in first."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "zai-org/glm-4.7"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    kwargs = dict(DEFAULT_KWARGS)
    kwargs["api_key"] = ""
    component = AtlasCloudModelComponent()
    component.set_attributes(kwargs)

    assert component.get_models() == ["zai-org/glm-4.7"]
    assert "Authorization" not in mock_get.call_args.kwargs["headers"]


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
def test_component_inputs_structure():
    component = AtlasCloudModelComponent()
    input_names = [input_.name for input_ in component.inputs]
    for expected in ["api_key", "model_name", "model_kwargs", "temperature", "max_tokens", "seed", "json_mode"]:
        assert expected in input_names


def test_model_name_dropdown_defaults_to_a_known_model():
    component = AtlasCloudModelComponent()
    model_input = next(i for i in component.inputs if i.name == "model_name")

    assert model_input.options == MODEL_NAMES
    assert model_input.value in MODEL_NAMES


def test_update_build_config_refreshes_the_options():
    component = AtlasCloudModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    build_config = {"model_name": {"options": []}}

    with patch.object(AtlasCloudModelComponent, "get_models", return_value=["a", "b"]):
        updated = component.update_build_config(build_config, "", "model_name")

    assert updated["model_name"]["options"] == ["a", "b"]
