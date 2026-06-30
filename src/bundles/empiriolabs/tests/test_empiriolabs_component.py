"""Unit tests for the EmpirioLabs extension bundle (``lfx-empiriolabs``).

The components previously lived at ``lfx.components.empiriolabs.*`` on the
contributor branch (PR #13645); they now ship as a standalone bundle, so these
tests travel with the bundle and import the public bundle entry point. They
exercise the server-free surface (component metadata, model building, live
model fetching with its static fallback, input structure, and image-generation
request shaping / validation) with ``ChatOpenAI`` and the HTTP calls
monkeypatched -- no network access or EmpirioLabs API key is required.

The in-tree fixture used ``tests.base.ComponentTestBaseWithoutClient``, which is
not importable inside a standalone bundle; these tests reimplement the same
assertions as plain pytest functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from lfx_empiriolabs import EmpirioLabsImageGenerationComponent, EmpirioLabsModelComponent
from lfx_empiriolabs.components.empiriolabs.empiriolabs import EMPIRIOLABS_MODELS, MODEL_NAMES

CHATOPENAI_PATH = "lfx_empiriolabs.components.empiriolabs.empiriolabs.ChatOpenAI"

DEFAULT_KWARGS = {
    "api_key": "test-empiriolabs-key",  # pragma: allowlist secret
    "model_name": "qwen3-7-plus",
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
    assert EmpirioLabsModelComponent.__name__ == "EmpirioLabsModelComponent"
    assert EmpirioLabsModelComponent.name == "EmpirioLabsModel"
    assert EmpirioLabsImageGenerationComponent.__name__ == "EmpirioLabsImageGenerationComponent"
    assert EmpirioLabsImageGenerationComponent.name == "EmpirioLabsImageGeneration"


# --------------------------------------------------------------------------- #
# Inlined model constants (previously lfx.base.models.empiriolabs_constants)
# --------------------------------------------------------------------------- #
def test_empiriolabs_models_not_empty():
    assert isinstance(EMPIRIOLABS_MODELS, list)
    assert len(EMPIRIOLABS_MODELS) > 0


def test_model_names_alias():
    assert MODEL_NAMES == EMPIRIOLABS_MODELS
    assert MODEL_NAMES is EMPIRIOLABS_MODELS


def test_models_are_unique_strings():
    for model in EMPIRIOLABS_MODELS:
        assert isinstance(model, str)
        assert model
    assert len(EMPIRIOLABS_MODELS) == len(set(EMPIRIOLABS_MODELS))


def test_specific_models_present():
    for expected in ["qwen3-7-plus", "deepseek-v4-pro", "glm-5-1", "minimax-m3"]:
        assert expected in EMPIRIOLABS_MODELS


# --------------------------------------------------------------------------- #
# Chat-model component
# --------------------------------------------------------------------------- #
def test_basic_setup():
    component = EmpirioLabsModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))

    assert component.display_name == "EmpirioLabs"
    assert component.description == "Generates text using EmpirioLabs AI LLMs (OpenAI compatible)."
    assert component.icon == "EmpirioLabs"
    assert component.name == "EmpirioLabsModel"
    assert component.api_key == "test-empiriolabs-key"  # pragma: allowlist secret
    assert component.model_name == "qwen3-7-plus"
    assert component.temperature == 0.1
    assert component.max_tokens == 1000
    assert component.seed == 1
    assert component.json_mode is False


@patch(CHATOPENAI_PATH)
def test_build_model_success(mock_chat_openai):
    mock_instance = MagicMock()
    mock_chat_openai.return_value = mock_instance

    component = EmpirioLabsModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    model = component.build_model()

    mock_chat_openai.assert_called_once_with(
        model="qwen3-7-plus",
        api_key="test-empiriolabs-key",  # pragma: allowlist secret
        max_tokens=1000,
        temperature=0.1,
        model_kwargs={},
        streaming=False,
        seed=1,
        base_url="https://api.empiriolabs.ai/v1",
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
    component = EmpirioLabsModelComponent()
    component.set_attributes(kwargs)
    model = component.build_model()

    mock_instance.bind.assert_called_once_with(response_format={"type": "json_object"})
    assert model == mock_bound_instance


@patch(CHATOPENAI_PATH)
def test_build_model_with_streaming(mock_chat_openai):
    mock_chat_openai.return_value = MagicMock()

    component = EmpirioLabsModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    component.stream = True
    component.build_model()

    _args, kwargs = mock_chat_openai.call_args
    assert kwargs["streaming"] is True


@patch(CHATOPENAI_PATH)
def test_build_model_exception_handling(mock_chat_openai):
    mock_chat_openai.side_effect = ValueError("Invalid API key")

    component = EmpirioLabsModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))

    with pytest.raises(ValueError, match="Could not connect to EmpirioLabs API"):
        component.build_model()


@patch("requests.get")
def test_get_models_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "qwen3-7-plus"}, {"id": "deepseek-v4-pro"}, {"id": "glm-5-1"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    component = EmpirioLabsModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    models = component.get_models()

    assert models == ["qwen3-7-plus", "deepseek-v4-pro", "glm-5-1"]
    mock_get.assert_called_once()


@patch("requests.get")
def test_get_models_fallback(mock_get):
    mock_get.side_effect = requests.RequestException("Network error")

    component = EmpirioLabsModelComponent()
    component.set_attributes(dict(DEFAULT_KWARGS))
    models = component.get_models()

    assert models == MODEL_NAMES
    assert "Error fetching models" in component.status


def test_component_inputs_structure():
    component = EmpirioLabsModelComponent()
    input_names = [input_.name for input_ in component.inputs]
    for expected in ["api_key", "model_name", "model_kwargs", "temperature", "max_tokens", "seed", "json_mode"]:
        assert expected in input_names


def test_component_input_types():
    component = EmpirioLabsModelComponent()
    api_key_input = next(i for i in component.inputs if i.name == "api_key")
    model_name_input = next(i for i in component.inputs if i.name == "model_name")
    temperature_input = next(i for i in component.inputs if i.name == "temperature")

    assert api_key_input.field_type.value == "str"  # SecretStrInput
    assert model_name_input.field_type.value == "str"  # DropdownInput
    assert temperature_input.field_type.value == "slider"  # SliderInput


# --------------------------------------------------------------------------- #
# Image-generation component
# --------------------------------------------------------------------------- #
IMAGE_KWARGS = {
    "api_key": "test-empiriolabs-key",  # pragma: allowlist secret
    "prompt": "a serene mountain lake at sunset",
    "model_name": "seedream-5-0-lite",
    "aspect_ratio": "1:1",
    "size": "",
    "n": 1,
    "seed": 0,
    "negative_prompt": "",
}


def test_image_generation_requires_api_key():
    component = EmpirioLabsImageGenerationComponent()
    kwargs = dict(IMAGE_KWARGS)
    kwargs["api_key"] = ""
    component.set_attributes(kwargs)
    with pytest.raises(ValueError, match="EmpirioLabs API key is required"):
        component.generate_image()


def test_image_generation_requires_prompt():
    component = EmpirioLabsImageGenerationComponent()
    kwargs = dict(IMAGE_KWARGS)
    kwargs["prompt"] = "   "
    component.set_attributes(kwargs)
    with pytest.raises(ValueError, match="non-empty prompt is required"):
        component.generate_image()


@patch("requests.post")
def test_image_generation_success(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"url": "https://cdn.empiriolabs.ai/generated/abc.png"}]}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    component = EmpirioLabsImageGenerationComponent()
    component.set_attributes(dict(IMAGE_KWARGS))
    result = component.generate_image()

    assert result.data["image_url"] == "https://cdn.empiriolabs.ai/generated/abc.png"
    assert result.data["image_urls"] == ["https://cdn.empiriolabs.ai/generated/abc.png"]

    _args, kwargs = mock_post.call_args
    payload = kwargs["json"]
    assert payload["model"] == "seedream-5-0-lite"
    assert payload["prompt"] == "a serene mountain lake at sunset"
    assert payload["sync"] is True
    # No explicit size -> aspect_ratio is used.
    assert payload["aspect_ratio"] == "1:1"
    assert "size" not in payload


@patch("requests.post")
def test_image_generation_request_error_returns_data(mock_post):
    mock_post.side_effect = requests.RequestException("boom")

    component = EmpirioLabsImageGenerationComponent()
    component.set_attributes(dict(IMAGE_KWARGS))
    result = component.generate_image()

    assert result.data["success"] is False
    assert "boom" in result.data["error"]


@patch("requests.get")
def test_image_generation_get_models_fallback(mock_get):
    mock_get.side_effect = requests.RequestException("Network error")

    component = EmpirioLabsImageGenerationComponent()
    component.set_attributes(dict(IMAGE_KWARGS))
    models = component.get_models()

    from lfx_empiriolabs.components.empiriolabs.empiriolabs_image_generation import EMPIRIOLABS_IMAGE_MODELS

    assert models == EMPIRIOLABS_IMAGE_MODELS
