from typing import Annotated, Literal

from fastapi import APIRouter, Query
from lfx.base.models.provider_registry import resolve_provider_id
from lfx.base.models.unified_models import (
    get_embedding_model_options,
    get_language_model_options,
    get_model_providers,
)
from lfx.services.model_provider_policy import (
    ModelProviderPolicyPurpose,
    ModelProviderPolicySnapshot,
    aresolve_model_provider_policy,
)

from langflow.api.utils import CurrentActiveUser
from langflow.api.v1.model_provider_policy_scope import (
    ProviderPolicyAttributes,
    ProviderPolicyAttributesDependency,
)

router = APIRouter(prefix="/model_options", tags=["Model Options"], include_in_schema=False)

ProviderReadPurpose = Literal["use", "configure"]


async def _resolve_option_policy(
    current_user: CurrentActiveUser,
    purpose: ProviderReadPurpose | None,
    attributes: ProviderPolicyAttributes,
) -> ModelProviderPolicySnapshot:
    providers = get_model_providers()
    baseline = await aresolve_model_provider_policy(
        user_id=current_user.id,
        providers=providers,
        purpose=ModelProviderPolicyPurpose.USE,
        attributes=attributes,
    )
    requested = ModelProviderPolicyPurpose(purpose) if purpose is not None else ModelProviderPolicyPurpose.USE
    if requested is ModelProviderPolicyPurpose.USE:
        return baseline
    requested_snapshot = await aresolve_model_provider_policy(
        user_id=current_user.id,
        providers=providers,
        purpose=requested,
        attributes=attributes,
    )
    return ModelProviderPolicySnapshot(
        context=baseline.context,
        purpose=requested,
        candidate_provider_ids=baseline.candidate_provider_ids,
        allowed_provider_ids=baseline.allowed_provider_ids & requested_snapshot.allowed_provider_ids,
    )


def _annotate_options(
    options: list[dict],
    provider_policy: ModelProviderPolicySnapshot,
) -> list[dict]:
    annotated_options = []
    for option in options:
        provider = option.get("provider")
        if not isinstance(provider, str) or not provider_policy.allows(provider):
            continue
        annotated_options.append(
            {
                **option,
                "provider_id": resolve_provider_id(provider),
            }
        )
    return annotated_options


@router.get("/language", status_code=200)
async def get_language_model_options_endpoint(
    current_user: CurrentActiveUser,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
    purpose: Annotated[ProviderReadPurpose | None, Query()] = None,
):
    """Get language model options filtered by user's enabled providers and models."""
    provider_policy = await _resolve_option_policy(current_user, purpose, provider_policy_attributes)
    return _annotate_options(
        get_language_model_options(user_id=current_user.id, provider_policy=provider_policy),
        provider_policy,
    )


@router.get("/embedding", status_code=200)
async def get_embedding_model_options_endpoint(
    current_user: CurrentActiveUser,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
    purpose: Annotated[ProviderReadPurpose | None, Query()] = None,
):
    """Get embedding model options filtered by user's enabled providers and models."""
    provider_policy = await _resolve_option_policy(current_user, purpose, provider_policy_attributes)
    return _annotate_options(
        get_embedding_model_options(user_id=current_user.id, provider_policy=provider_policy),
        provider_policy,
    )
