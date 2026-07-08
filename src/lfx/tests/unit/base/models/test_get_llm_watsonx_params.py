"""Regression guards for IBM WatsonX param-name resolution in unified ``get_llm``.

A stored model selection sourced from the ``GET /api/v1/models`` catalog (which
the frontend uses to augment the Language Model / Agent dropdown right after a
provider is configured) carries only the raw ``create_model_metadata`` fields —
none of the enriched ``*_param`` keys that ``get_language_model_options`` adds.

For IBM WatsonX this is load-bearing: ``langchain_ibm.ChatWatsonx`` exposes both
a ``model`` field (routes to the OpenAI-style **Model Gateway**, a different
catalog) and a ``model_id`` field (routes to **ModelInference**, the foundation
models endpoint the dropdown is populated from). If ``get_llm`` falls back to the
generic ``model`` param name, the selected foundation-model id is sent to the
gateway and fails with "model <id> not found" / IAM "Provided user not found or
active" — even though the dropdown, connection test, and standalone
``IBM watsonx.ai`` component all work. See langflow-ai/langflow#13671.

These tests pin that ``get_llm`` resolves the provider-specific param names
(``model_id``, ``apikey``, ``url``, ``project_id``) from the provider mapping
even when the selection metadata is the raw catalog shape.
"""

from __future__ import annotations

from unittest.mock import patch


def _capture_factory():
    captured: dict = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    return FakeChatModel, captured


def _raw_watsonx_selection() -> list[dict]:
    """Selection as persisted from the raw ``/api/v1/models`` catalog.

    Matches ``create_model_metadata`` output: provider/icon/flags only, with
    none of the enriched ``model_class`` / ``model_name_param`` / ``api_key_param``
    keys that ``get_language_model_options`` injects.
    """
    return [
        {
            "name": "meta-llama/llama-3-3-70b-instruct",
            "provider": "IBM WatsonX",
            "metadata": {
                "provider": "IBM WatsonX",
                "icon": "IBM",
                "tool_calling": True,
                "model_type": "llm",
                "default": True,
            },
        }
    ]


def _build_llm_from_raw_selection() -> dict:
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    fake_cls, captured = _capture_factory()

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="ibm-apikey-xyz",  # pragma: allowlist secret
        ),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={
                "WATSONX_URL": "https://us-south.ml.cloud.ibm.com",
                "WATSONX_PROJECT_ID": "proj-123",
            },
        ),
    ):
        get_llm(_raw_watsonx_selection(), user_id=None, stream=True)

    return captured


def test_watsonx_raw_metadata_sends_model_id_not_model():
    """The foundation-model id must be sent as ``model_id``, never the generic ``model``.

    ``model`` routes ChatWatsonx to the Model Gateway (different catalog) and is
    the root cause of the "model not found" failure in #13671.
    """
    captured = _build_llm_from_raw_selection()

    assert captured.get("model_id") == "meta-llama/llama-3-3-70b-instruct", (
        "get_llm must resolve IBM WatsonX's model param to 'model_id' even when the "
        f"selection carries only raw catalog metadata. Got kwargs keys: {sorted(captured)}."
    )
    assert "model" not in captured, (
        "Passing the foundation-model id under the generic 'model' kwarg routes "
        "ChatWatsonx to the Model Gateway (a different catalog), which fails with "
        f"'model not found'. Got kwargs keys: {sorted(captured)}."
    )


def test_watsonx_raw_metadata_sends_apikey_and_connection_params():
    """The api key, url, and project id must use WatsonX's native param names."""
    captured = _build_llm_from_raw_selection()

    assert captured.get("apikey") == "ibm-apikey-xyz"  # pragma: allowlist secret
    assert captured.get("url") == "https://us-south.ml.cloud.ibm.com"
    assert captured.get("project_id") == "proj-123"
