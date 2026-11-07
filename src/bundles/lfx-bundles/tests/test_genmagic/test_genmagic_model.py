"""Unit tests for the GenMagic language model component (needs ``lfx-bundles[genmagic]``)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from lfx_bundles.genmagic.genmagic_common import GenMagicAPIError, client_header
from lfx_bundles.genmagic.genmagic_model import GenMagicModelComponent

from .conftest import API_KEY, response

pytest.importorskip("langchain_openai", reason="install lfx-bundles[genmagic]")


def _model(**values) -> GenMagicModelComponent:
    component = GenMagicModelComponent()
    component.set(**{"api_key": API_KEY, "model_name": "vendor/chat-1", **values})
    return component


@pytest.mark.unit
class TestGenMagicModel:
    def test_builds_a_chat_client_for_genmagic(self) -> None:
        model = _model().build_model()

        assert model.model_name == "vendor/chat-1"
        assert model.openai_api_base == "https://genmagic.co/api/v1"
        assert model.openai_api_key.get_secret_value() == API_KEY
        assert model.default_headers == {"X-GenMagic-Client": client_header()}
        assert model.temperature is None
        assert model.max_tokens is None

    def test_temperature_and_max_tokens_are_passed_when_set(self) -> None:
        model = _model(temperature=0.2, max_tokens=256, stream=True).build_model()

        assert model.temperature == pytest.approx(0.2)
        assert model.max_tokens == 256
        assert model.streaming is True

    def test_never_falls_back_to_the_server_openai_key(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "server-openai-key")  # pragma: allowlist secret
        with pytest.raises(GenMagicAPIError, match="API key is required"):
            _model(api_key="").build_model()

    def test_a_model_must_be_selected(self) -> None:
        with pytest.raises(GenMagicAPIError, match="Select a GenMagic model"):
            _model(model_name="").build_model()

    def test_update_build_config_lists_text_models_newest_first_without_auto(self) -> None:
        catalog = {"data": [{"id": "a/old", "created": 1}, {"id": "b/new", "created": 2}]}
        build_config = {"model_name": {"options": [], "value": ""}}
        with patch("httpx.Client.request", return_value=response(json_body=catalog)) as request:
            _model().update_build_config(build_config, "", "model_name")

        assert build_config["model_name"]["options"] == ["b/new", "a/old"]
        assert request.call_args.kwargs["params"] == {"category": "text"}

    def test_catalog_is_fetched_only_for_the_model_dropdown(self) -> None:
        build_config = {"model_name": {"options": [], "value": ""}}
        with patch("httpx.Client.request") as request:
            _model().update_build_config(build_config, "", "tool_mode")

        request.assert_not_called()
