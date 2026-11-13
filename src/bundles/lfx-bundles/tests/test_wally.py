import httpx
import pytest

pytest.importorskip("lfx_bundles")

from lfx_bundles.wally.wally import WallyComponent


def _build_config(value: str) -> dict:
    return {"model_name": {"options": [value], "value": value}}


def test_refresh_lists_models_and_tolerates_null_context(monkeypatch: pytest.MonkeyPatch):
    payload = {
        "data": [
            {"id": "glm-5.3-flash", "name": "GLM-5.3 Flash", "context_length": 1048576},
            {"id": "kimi-k3", "name": "Kimi K3", "context_length": None},
        ]
    }
    response = httpx.Response(
        200, json=payload, request=httpx.Request("GET", "https://inference.runanywhere.ai/v1/models")
    )
    monkeypatch.setattr(httpx, "get", lambda *_, **__: response)

    config = WallyComponent().update_build_config(_build_config(""), "", "model_name")

    assert config["model_name"]["options"] == ["glm-5.3-flash", "kimi-k3"]
    assert config["model_name"]["tooltips"]["kimi-k3"] == "Kimi K3 (0 tokens)"


def test_failed_refresh_keeps_the_selected_model(monkeypatch: pytest.MonkeyPatch):
    def fail(*_, **__):
        msg = "offline"
        raise httpx.ConnectError(msg)

    monkeypatch.setattr(httpx, "get", fail)

    config = WallyComponent().update_build_config(_build_config("glm-5.3-flash"), "", "model_name")

    assert config["model_name"]["value"] == "glm-5.3-flash"
    assert config["model_name"]["options"] == ["glm-5.3-flash"]
