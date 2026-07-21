"""Regression tests for IBM WatsonX credential validation."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

WATSONX_VARIABLES = {
    "WATSONX_APIKEY": "test-watsonx-key",  # pragma: allowlist secret
    "WATSONX_PROJECT_ID": "test-project-id",
    "WATSONX_URL": "https://us-south.ml.cloud.ibm.com",
}


def test_validate_watsonx_uses_live_model_when_static_catalog_has_no_active_models():
    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    calls = {}

    class FakeChatWatsonx:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs

        def invoke(self, prompt):
            calls["prompt"] = prompt
            return "ok"

    with (
        patch.dict("sys.modules", {"langchain_ibm": SimpleNamespace(ChatWatsonx=FakeChatWatsonx)}),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch("lfx.base.models.unified_models.credentials.validate_connector_url_for_ssrf"),
        patch.object(
            model_utils,
            "get_watsonx_llm_models",
            return_value=["ibm/granite-current"],
        ) as get_live_models,
    ):
        validate_model_provider_key("IBM WatsonX", WATSONX_VARIABLES)

    get_live_models.assert_called_once_with(
        "https://us-south.ml.cloud.ibm.com",
        default_models=[],
    )
    assert calls["kwargs"]["apikey"] == "test-watsonx-key"  # pragma: allowlist secret
    assert calls["kwargs"]["model_id"] == "ibm/granite-current"
    assert calls["kwargs"]["project_id"] == "test-project-id"
    assert calls["prompt"] == "test"


def test_validate_watsonx_rejects_ibm_iam_error():
    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    class FakeChatWatsonx:
        def __init__(self, **_kwargs):
            pass

        def invoke(self, _prompt):
            msg = "BXNIM0410E: Provided user not found or active."
            raise RuntimeError(msg)

    with (
        patch.dict("sys.modules", {"langchain_ibm": SimpleNamespace(ChatWatsonx=FakeChatWatsonx)}),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch("lfx.base.models.unified_models.credentials.validate_connector_url_for_ssrf"),
        patch.object(model_utils, "get_watsonx_llm_models", return_value=["ibm/granite-current"]),
        pytest.raises(ValueError, match="Could not validate IBM WatsonX credentials"),
    ):
        validate_model_provider_key("IBM WatsonX", WATSONX_VARIABLES)


def test_validate_watsonx_fails_when_no_test_model_is_available():
    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    with (
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch("lfx.base.models.unified_models.credentials.validate_connector_url_for_ssrf"),
        patch.object(model_utils, "get_watsonx_llm_models", return_value=[]),
        pytest.raises(ValueError, match="No IBM WatsonX chat model is available"),
    ):
        validate_model_provider_key("IBM WatsonX", WATSONX_VARIABLES)
