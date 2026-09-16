"""Unit tests for the AnonRouter bundle component.

``httpx`` is mocked throughout: no test reaches the network or needs a key.
"""

from unittest.mock import Mock, patch

import pytest

pytest.importorskip("lfx_bundles")
pytest.importorskip("langchain_openai")

from lfx_bundles.anonrouter.anonrouter import BASE_URL, AnonRouterComponent

# Shaped like ``GET /v1/models`` on the compatibility origin: an OpenAI-style
# envelope whose entries carry AnonRouter's own capability metadata.
MODELS_PAYLOAD = {
    "object": "list",
    "data": [
        {
            "id": "meta-llama/llama-3.3-70b",
            "object": "model",
            "display_name": "Llama 3.3 70B",
            "model_type": "text",
            "context_window": 65536,
            "capabilities": {"embeddings": False, "streaming": True, "tools": True},
        },
        {
            "id": "z-ai/glm-5.2",
            "object": "model",
            "display_name": "GLM 5.2",
            "model_type": "text",
            "capabilities": {"embeddings": False, "streaming": True, "tools": True},
        },
        {
            "id": "baai/bge-m3",
            "object": "model",
            "display_name": "BGE M3",
            "model_type": "embedding",
            "capabilities": {"embeddings": True, "streaming": False, "tools": False},
        },
        {
            "id": "alibaba/z-image-turbo",
            "object": "model",
            "display_name": "Z-Image Turbo",
            "model_type": "image",
        },
    ],
}


def _mock_response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@pytest.mark.unit
class TestFetchModels:
    def test_discovery_sends_the_key_as_a_bearer_token(self):
        component = AnonRouterComponent(api_key="ar_test-key")

        with patch("httpx.get", return_value=_mock_response(MODELS_PAYLOAD)) as mock_get:
            component.fetch_models()

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == f"{BASE_URL}/models"
        assert kwargs["headers"]["Authorization"] == "Bearer ar_test-key"

    def test_no_key_means_no_request(self):
        """``/v1/models`` 404s without a credential, so never call it unauthenticated."""
        component = AnonRouterComponent(api_key="")

        with patch("httpx.get") as mock_get:
            assert component.fetch_models() is None

        mock_get.assert_not_called()

    def test_nested_creator_model_ids_are_preserved(self):
        component = AnonRouterComponent(api_key="ar_test-key")

        with patch("httpx.get", return_value=_mock_response(MODELS_PAYLOAD)):
            models = component.fetch_models()

        assert [m["id"] for m in models] == ["z-ai/glm-5.2", "meta-llama/llama-3.3-70b"]

    def test_non_chat_routes_are_filtered_out(self):
        component = AnonRouterComponent(api_key="ar_test-key")

        with patch("httpx.get", return_value=_mock_response(MODELS_PAYLOAD)):
            ids = {m["id"] for m in component.fetch_models()}

        assert "baai/bge-m3" not in ids
        assert "alibaba/z-image-turbo" not in ids

    def test_request_error_reports_discovery_failure(self):
        import httpx

        component = AnonRouterComponent(api_key="ar_test-key")

        with patch("httpx.get", side_effect=httpx.RequestError("boom")):
            assert component.fetch_models() is None

    def test_http_error_reports_discovery_failure(self):
        import httpx

        component = AnonRouterComponent(api_key="ar_test-key")
        request = httpx.Request("GET", f"{BASE_URL}/models")
        response = httpx.Response(401, request=request)
        error = httpx.HTTPStatusError("unauthorized", request=request, response=response)
        mock_response = _mock_response(MODELS_PAYLOAD)
        mock_response.raise_for_status.side_effect = error

        with patch("httpx.get", return_value=mock_response):
            assert component.fetch_models() is None

        assert "Error fetching models" in component.status

    def test_a_bare_list_payload_is_accepted(self):
        component = AnonRouterComponent(api_key="ar_test-key")

        with patch("httpx.get", return_value=_mock_response([{"id": "openai/gpt-oss-120b"}])):
            assert [m["id"] for m in component.fetch_models()] == ["openai/gpt-oss-120b"]

    def test_entries_without_an_id_are_skipped(self):
        component = AnonRouterComponent(api_key="ar_test-key")
        payload = {"data": [{"object": "model"}, {"id": "openai/gpt-oss-120b"}]}

        with patch("httpx.get", return_value=_mock_response(payload)):
            assert [m["id"] for m in component.fetch_models()] == ["openai/gpt-oss-120b"]


@pytest.mark.unit
class TestUpdateBuildConfig:
    def test_options_and_tooltips_are_populated(self):
        component = AnonRouterComponent(api_key="ar_test-key")
        build_config = {"model_name": {"options": [], "value": ""}}

        with patch("httpx.get", return_value=_mock_response(MODELS_PAYLOAD)):
            updated = component.update_build_config(build_config, "ar_test-key", "api_key")

        assert updated["model_name"]["options"] == ["z-ai/glm-5.2", "meta-llama/llama-3.3-70b"]
        tooltips = updated["model_name"]["tooltips"]
        assert tooltips["meta-llama/llama-3.3-70b"] == "Llama 3.3 70B (65,536 tokens)"
        # No context window reported, so no "(0 tokens)" is invented.
        assert tooltips["z-ai/glm-5.2"] == "GLM 5.2"

    def test_a_stale_selection_is_cleared_rather_than_left_dangling(self):
        component = AnonRouterComponent(api_key="ar_test-key")
        build_config = {"model_name": {"options": ["gone/model"], "value": "gone/model"}}

        with patch("httpx.get", return_value=_mock_response(MODELS_PAYLOAD)):
            updated = component.update_build_config(build_config, "ar_test-key", "api_key")

        assert updated["model_name"]["value"] == ""

    def test_failed_discovery_does_not_clobber_a_working_selection(self):
        """A transient failure must not wipe a saved flow's model, nor invent a sentinel."""
        import httpx

        component = AnonRouterComponent(api_key="ar_test-key")
        saved = "meta-llama/llama-3.3-70b"
        build_config = {"model_name": {"options": [saved], "value": saved}}

        with patch("httpx.get", side_effect=httpx.RequestError("boom")):
            updated = component.update_build_config(build_config, "ar_test-key", "api_key")

        assert updated["model_name"]["options"] == [saved]
        assert updated["model_name"]["value"] == saved

    def test_successful_empty_catalog_clears_a_stale_selection(self):
        component = AnonRouterComponent(api_key="ar_test-key")
        build_config = {
            "model_name": {
                "options": ["gone/model"],
                "tooltips": {"gone/model": "Gone Model"},
                "value": "gone/model",
            }
        }

        with patch("httpx.get", return_value=_mock_response({"data": []})):
            updated = component.update_build_config(build_config, "ar_test-key", "api_key")

        assert updated["model_name"]["options"] == []
        assert updated["model_name"]["tooltips"] == {}
        assert updated["model_name"]["value"] == ""

    def test_unrelated_fields_do_not_trigger_discovery(self):
        component = AnonRouterComponent(api_key="ar_test-key")
        build_config = {"model_name": {"options": [], "value": ""}}

        with patch("httpx.get") as mock_get:
            component.update_build_config(build_config, 0.5, "temperature")

        mock_get.assert_not_called()


@pytest.mark.unit
class TestBuildModel:
    def test_model_is_pointed_at_the_anonrouter_base_url(self):
        component = AnonRouterComponent(
            api_key="ar_test-key",  # pragma: allowlist secret
            model_name="meta-llama/llama-3.3-70b",
            temperature=0.7,
            max_tokens=None,
        )

        with patch("lfx_bundles.anonrouter.anonrouter.ChatOpenAI") as mock_chat:
            component.build_model()

        kwargs = mock_chat.call_args.kwargs
        assert kwargs["base_url"] == BASE_URL
        assert kwargs["model"] == "meta-llama/llama-3.3-70b"
        assert kwargs["api_key"] == "ar_test-key"  # pragma: allowlist secret
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_retries"] == 0
        assert "max_tokens" not in kwargs

    def test_temperature_falls_back_to_the_default(self):
        component = AnonRouterComponent(
            api_key="ar_test-key",  # pragma: allowlist secret
            model_name="z-ai/glm-5.2",
            temperature=None,
            max_tokens=None,
        )

        with patch("lfx_bundles.anonrouter.anonrouter.ChatOpenAI") as mock_chat:
            component.build_model()

        assert mock_chat.call_args.kwargs["temperature"] == 0.7

    def test_max_tokens_is_coerced_to_an_int(self):
        component = AnonRouterComponent(
            api_key="ar_test-key",  # pragma: allowlist secret
            model_name="z-ai/glm-5.2",
            temperature=0.7,
            max_tokens="512",
        )

        with patch("lfx_bundles.anonrouter.anonrouter.ChatOpenAI") as mock_chat:
            component.build_model()

        assert mock_chat.call_args.kwargs["max_tokens"] == 512

    def test_streaming_is_left_to_the_shared_base_component(self):
        """``LCModelComponent`` drives streaming; the model must not pin it."""
        component = AnonRouterComponent(
            api_key="ar_test-key",  # pragma: allowlist secret
            model_name="z-ai/glm-5.2",
            temperature=0.7,
            max_tokens=None,
        )

        with patch("lfx_bundles.anonrouter.anonrouter.ChatOpenAI") as mock_chat:
            component.build_model()

        assert "streaming" not in mock_chat.call_args.kwargs

    def test_missing_api_key_is_rejected(self):
        component = AnonRouterComponent(api_key="", model_name="z-ai/glm-5.2")

        with pytest.raises(ValueError, match="API key is required"):
            component.build_model()

    def test_missing_model_is_rejected(self):
        component = AnonRouterComponent(api_key="ar_test-key", model_name="")

        with pytest.raises(ValueError, match="Please select a model"):
            component.build_model()
