from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.components.deactivated.chat_litellm_model import ChatLiteLLMModelComponent
from lfx.services.model_provider_policy import ModelProviderPolicyError, ModelProviderPolicyPurpose


class _UnhydratedSecret:
    def __bool__(self) -> bool:
        raise AssertionError


@pytest.mark.parametrize(
    ("provider", "provider_id"),
    [("OpenAI", "openai"), ("Azure", "azure-openai")],
)
@pytest.mark.parametrize(
    "purpose",
    [ModelProviderPolicyPurpose.CONFIGURE, ModelProviderPolicyPurpose.USE],
)
async def test_saved_litellm_uses_raw_selected_provider_before_secret_hydration(
    monkeypatch,
    purpose,
    provider,
    provider_id,
) -> None:
    component = ChatLiteLLMModelComponent(_user_id="resource-owner")
    denial = ModelProviderPolicyError(provider_id, purpose)
    snapshot = SimpleNamespace(require=Mock(side_effect=denial))
    resolve_policy = AsyncMock(return_value=snapshot)
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve_policy)

    with pytest.raises(ModelProviderPolicyError):
        await component.arequire_model_provider_policy(
            purpose,
            user_id="policy-actor",
            parameters={
                "provider": provider,
                "api_key": _UnhydratedSecret(),
            },
        )

    resolve_policy.assert_awaited_once_with(
        user_id="policy-actor",
        providers=[provider_id],
        purpose=purpose,
    )
    snapshot.require.assert_called_once_with(provider_id)
