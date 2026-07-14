import pytest
from lfx.base.models.unified_models.credentials import get_api_key_for_provider
from lfx.services.variable.service import VariableService


@pytest.mark.asyncio
async def test_variable_service_refuses_protected_process_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_SECRET_KEY", "server-master-key")

    assert await VariableService().get_variable("LANGFLOW_SECRET_KEY") is None


def test_unified_custom_credential_name_refuses_protected_process_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_SECRET_KEY", "server-master-key")

    assert get_api_key_for_provider(None, "OpenAI", "LANGFLOW_SECRET_KEY") is None


def test_unified_canonical_fallback_refuses_protected_process_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_SECRET_KEY", "server-master-key")
    monkeypatch.setattr(
        "lfx.base.models.unified_models.credentials.get_model_provider_variable_mapping",
        lambda: {"Test Provider": "LANGFLOW_SECRET_KEY"},
    )

    assert get_api_key_for_provider(None, "Test Provider") is None


@pytest.mark.asyncio
async def test_variable_service_still_allows_provider_process_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "provider-key")

    assert await VariableService().get_variable("OPENAI_API_KEY") == "provider-key"
