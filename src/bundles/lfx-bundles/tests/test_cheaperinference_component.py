"""Unit tests for the Cheaper Inference model component (no network)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

pytest.importorskip("lfx_bundles")
pytest.importorskip("langchain_openai")

from lfx_bundles.cheaperinference.cheaperinference import (
    CHEAPER_INFERENCE_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_MODELS,
    CheaperInferenceComponent,
)

MODELS_PAYLOAD = {
    "data": [
        {"id": "gpt-5.4-mini", "type": "text", "context_length": 400000},
        {"id": "claude-sonnet-5", "type": "text", "context_length": 1000000},
        {"id": "some-image-model", "type": "image"},
    ]
}


def _build_config() -> dict:
    return {"model_name": {"options": list(DEFAULT_MODELS), "value": DEFAULT_MODEL}}


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_fetch_models_sends_bearer_key_and_keeps_text_models():
    component = CheaperInferenceComponent()
    with patch("lfx_bundles.cheaperinference.cheaperinference.httpx.get") as mock_get:
        mock_get.return_value = _response(MODELS_PAYLOAD)
        models = component.fetch_models("ci_live_test")  # pragma: allowlist secret

    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == f"{CHEAPER_INFERENCE_BASE_URL}/models"
    assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Bearer ci_live_test"}
    assert [m["id"] for m in models] == ["claude-sonnet-5", "gpt-5.4-mini"]


def test_fetch_models_without_key_makes_no_request():
    component = CheaperInferenceComponent()
    with patch("lfx_bundles.cheaperinference.cheaperinference.httpx.get") as mock_get:
        assert component.fetch_models(None) == []
    mock_get.assert_not_called()


def test_update_build_config_uses_live_models():
    component = CheaperInferenceComponent()
    with patch("lfx_bundles.cheaperinference.cheaperinference.httpx.get") as mock_get:
        mock_get.return_value = _response(MODELS_PAYLOAD)
        config = component.update_build_config(_build_config(), "ci_live_test", "api_key")

    assert config["model_name"]["options"] == ["claude-sonnet-5", "gpt-5.4-mini"]
    assert config["model_name"]["value"] == DEFAULT_MODEL
    assert config["model_name"]["tooltips"]["claude-sonnet-5"] == "claude-sonnet-5 (1,000,000 tokens)"


def test_update_build_config_falls_back_to_defaults_on_error():
    component = CheaperInferenceComponent()
    with patch("lfx_bundles.cheaperinference.cheaperinference.httpx.get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("offline")
        config = component.update_build_config(_build_config(), "ci_live_test", "api_key")

    assert config["model_name"]["options"] == DEFAULT_MODELS
    assert config["model_name"]["value"] == DEFAULT_MODEL


@pytest.mark.parametrize("payload", [None, [], "text", {"data": None}, {"data": "x"}])
def test_fetch_models_ignores_unexpected_payload(payload):
    component = CheaperInferenceComponent()
    with patch("lfx_bundles.cheaperinference.cheaperinference.httpx.get") as mock_get:
        mock_get.return_value = _response(payload)
        assert component.fetch_models("ci_live_test") == []  # pragma: allowlist secret


def test_build_model_uses_cheaper_inference_endpoint():
    component = CheaperInferenceComponent()
    component.set_attributes(
        {
            "api_key": "ci_live_test",  # pragma: allowlist secret
            "model_name": "claude-sonnet-5",
            "temperature": 0.2,
            "max_tokens": 128,
            "stream": False,
        }
    )
    model = component.build_model()

    assert model.model_name == "claude-sonnet-5"
    assert model.openai_api_base == CHEAPER_INFERENCE_BASE_URL
    assert model.openai_api_key.get_secret_value() == "ci_live_test"
    assert model.temperature == 0.2
    assert model.max_tokens == 128


def test_build_model_requires_api_key():
    component = CheaperInferenceComponent()
    component.set_attributes({"api_key": "", "model_name": "gpt-5.4-mini"})
    with pytest.raises(ValueError, match="API key is required"):
        component.build_model()
