"""Tests for the Runcrate model component: live model list, fallback, and model construction."""

from unittest.mock import patch

import httpx
import pytest

pytest.importorskip("lfx_bundles")

from lfx_bundles.runcrate.runcrate import DEFAULT_MODELS, RUNCRATE_BASE_URL, RuncrateModelComponent

MODELS_URL = f"{RUNCRATE_BASE_URL}/models"
TENANT_KEY = "rc_live_test-key"  # pragma: allowlist secret


def _response(status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", MODELS_URL), **kwargs)


def _build_config() -> dict:
    return {"model_name": {"options": [], "value": DEFAULT_MODELS[0]}}


MODEL_LIST = {
    "data": [
        {"id": "zai-org/GLM-5.3", "name": "GLM 5.3", "output_modalities": ["text"], "context_length": 200000},
        {"id": "image/model", "name": "Image", "output_modalities": ["image"], "context_length": 4096},
        {"id": "deepseek-ai/DeepSeek-V4.1-Flash", "output_modalities": ["text"], "context_length": 128000},
        {"name": "No id", "output_modalities": ["text"], "context_length": 8192},
        {"id": "zero/context", "output_modalities": ["text"], "context_length": 0},
        {"id": "string/context", "output_modalities": ["text"], "context_length": "8192"},
        "not-a-model",
    ]
}


def test_fetch_models_keeps_text_models_sorted_by_name():
    with patch("lfx_bundles.runcrate.runcrate.httpx.get", return_value=_response(json=MODEL_LIST)) as get:
        models = RuncrateModelComponent().fetch_models()

    get.assert_called_once_with(MODELS_URL, timeout=10.0)
    assert models == [
        {"id": "deepseek-ai/DeepSeek-V4.1-Flash", "name": "deepseek-ai/DeepSeek-V4.1-Flash", "context": 128000},
        {"id": "zai-org/GLM-5.3", "name": "GLM 5.3", "context": 200000},
    ]


def test_update_build_config_uses_live_models_with_tooltips():
    with patch("lfx_bundles.runcrate.runcrate.httpx.get", return_value=_response(json=MODEL_LIST)):
        config = RuncrateModelComponent().update_build_config(_build_config(), DEFAULT_MODELS[0], "model_name")

    assert config["model_name"]["options"] == ["deepseek-ai/DeepSeek-V4.1-Flash", "zai-org/GLM-5.3"]
    assert config["model_name"]["tooltips"]["zai-org/GLM-5.3"] == "GLM 5.3 (200,000 tokens)"


@pytest.mark.parametrize(
    "outcome",
    [
        _response(503, json={"error": "unavailable"}),
        _response(content=b"not json"),
        _response(json=["unexpected", "list"]),
        _response(json={"data": {"id": "not-a-list"}}),
        _response(json={"data": []}),
        httpx.ConnectError("connection refused"),
    ],
    ids=["http-error", "invalid-json", "non-object", "data-not-list", "empty-list", "network-error"],
)
def test_update_build_config_falls_back_to_default_models(outcome):
    kwargs = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
    with patch("lfx_bundles.runcrate.runcrate.httpx.get", **kwargs):
        config = RuncrateModelComponent().update_build_config(_build_config(), DEFAULT_MODELS[0], "model_name")

    assert config["model_name"]["options"] == DEFAULT_MODELS


@pytest.mark.parametrize("max_tokens", [None, 0, 512])
def test_build_model_targets_runcrate_endpoint(max_tokens):
    component = RuncrateModelComponent(
        api_key=TENANT_KEY,
        model_name="zai-org/GLM-5.3",
        temperature=0.2,
        stream=True,
        max_tokens=max_tokens,
    )
    with patch("lfx_bundles.runcrate.runcrate.ChatOpenAI") as chat:
        component.build_model()

    kwargs = chat.call_args.kwargs
    assert kwargs["openai_api_base"] == RUNCRATE_BASE_URL
    assert kwargs["openai_api_key"] == TENANT_KEY
    assert kwargs["model"] == "zai-org/GLM-5.3"
    assert kwargs["temperature"] == 0.2
    assert kwargs["streaming"] is True
    if max_tokens:
        assert kwargs["max_tokens"] == max_tokens
    else:
        assert "max_tokens" not in kwargs


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"api_key": "", "model_name": "zai-org/GLM-5.3"}, "API key is required"),
        ({"api_key": None, "model_name": "zai-org/GLM-5.3"}, "API key is required"),
        ({"api_key": TENANT_KEY, "model_name": ""}, "select a model"),
    ],
    ids=["empty-key", "missing-key", "missing-model"],
)
def test_build_model_rejects_missing_inputs_before_client(fields, message, monkeypatch):
    # An empty key must not let ChatOpenAI fall back to an unrelated OPENAI_API_KEY.
    monkeypatch.setenv("OPENAI_API_KEY", "operator-openai-key")
    component = RuncrateModelComponent(**fields)
    with patch("lfx_bundles.runcrate.runcrate.ChatOpenAI") as chat, pytest.raises(ValueError, match=message):
        component.build_model()
    chat.assert_not_called()
