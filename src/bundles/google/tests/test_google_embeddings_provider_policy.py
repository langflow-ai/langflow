from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.services.model_provider_policy import ModelProviderPolicyError, ModelProviderPolicyPurpose
from lfx_google.components.google.google_generative_ai_embeddings import GoogleGenerativeAIEmbeddingsComponent


class _UnhydratedSecret:
    def __bool__(self) -> bool:
        raise AssertionError


@pytest.mark.parametrize(
    "purpose",
    [ModelProviderPolicyPurpose.CONFIGURE, ModelProviderPolicyPurpose.USE],
)
async def test_google_embeddings_are_gated_as_google_before_secret_hydration(monkeypatch, purpose) -> None:
    component = GoogleGenerativeAIEmbeddingsComponent(_user_id="resource-owner")
    denial = ModelProviderPolicyError("google-generative-ai", purpose)
    snapshot = SimpleNamespace(require=Mock(side_effect=denial))
    resolve_policy = AsyncMock(return_value=snapshot)
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve_policy)

    with pytest.raises(ModelProviderPolicyError):
        await component.arequire_model_provider_policy(
            purpose,
            user_id="policy-actor",
            parameters={"api_key": _UnhydratedSecret()},
        )

    assert component.model_provider_id == "google-generative-ai"
    resolve_policy.assert_awaited_once_with(
        user_id="policy-actor",
        providers=["google-generative-ai"],
        purpose=purpose,
    )
    snapshot.require.assert_called_once_with("google-generative-ai")
