"""Regression tests for connector URL guards at outbound sinks."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _enable_connector_ssrf(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "false")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)


async def test_ollama_discovery_blocks_metadata_before_request():
    from lfx.base.models import model_utils

    with patch.object(model_utils.httpx, "AsyncClient") as mock_client:
        result = await model_utils.is_valid_ollama_url("http://169.254.169.254")

    assert result is False
    mock_client.assert_not_called()


def test_watsonx_discovery_blocks_metadata_before_request():
    from lfx.base.models import model_utils

    with patch.object(model_utils.requests, "get") as mock_get:
        result = model_utils.get_watsonx_llm_models(
            base_url="http://169.254.169.254",
            default_models=["fallback"],
        )

    assert result == ["fallback"]
    mock_get.assert_not_called()
