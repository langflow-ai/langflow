"""Superuser administration for the install-wide approved-provider policy."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from lfx.base.models.provider_registry import get_registry_snapshot
from pydantic import BaseModel, Field, StringConstraints, field_validator

from langflow.api.utils import DbSession, DbSessionReadOnly
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.user.model import User
from langflow.services.model_provider_policy import (
    apply_model_provider_policy_state,
    get_model_provider_policy_state,
    replace_model_provider_policy_state,
)

router = APIRouter(prefix="/model-provider-policy", tags=["Model Provider Policy"])

ProviderId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=255)]


class RegisteredModelProviderRead(BaseModel):
    """Stable provider identity exposed to the administrative picker."""

    provider_id: str
    display_name: str
    provider: str


class ModelProviderPolicyWrite(BaseModel):
    """Complete replacement for the install-wide approved-provider set."""

    approved_provider_ids: Annotated[list[ProviderId], Field(max_length=1000)]

    @field_validator("approved_provider_ids")
    @classmethod
    def deduplicate_provider_ids(cls, provider_ids: list[str]) -> list[str]:
        return sorted(set(provider_ids))


class ModelProviderPolicyRead(BaseModel):
    """Current deployment ceiling plus every provider registered in this process."""

    approved_provider_ids: list[str]
    registered_providers: list[RegisteredModelProviderRead]


def _build_policy_response(approved_provider_ids: set[str] | frozenset[str]) -> ModelProviderPolicyRead:
    snapshot = get_registry_snapshot()
    registered_providers = [
        RegisteredModelProviderRead(
            provider_id=provider_id,
            display_name=descriptor.display_name or descriptor.name,
            provider=descriptor.name,
        )
        for provider_id, descriptor in snapshot.descriptors_by_id.items()
    ]
    registered_providers.sort(key=lambda descriptor: (descriptor.display_name.casefold(), descriptor.provider_id))
    return ModelProviderPolicyRead(
        approved_provider_ids=sorted(approved_provider_ids),
        registered_providers=registered_providers,
    )


@router.get("", response_model=ModelProviderPolicyRead)
@router.get("/", response_model=ModelProviderPolicyRead)
async def read_model_provider_policy(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSessionReadOnly,
) -> ModelProviderPolicyRead:
    """Read the global provider policy. An empty approved list is unrestricted."""
    state = await get_model_provider_policy_state(session)
    return _build_policy_response(state.approved_provider_ids)


@router.post("", response_model=ModelProviderPolicyRead)
@router.post("/", response_model=ModelProviderPolicyRead)
@router.put("", response_model=ModelProviderPolicyRead)
@router.put("/", response_model=ModelProviderPolicyRead)
async def replace_model_provider_policy(
    payload: ModelProviderPolicyWrite,
    _admin: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSession,
) -> ModelProviderPolicyRead:
    """Atomically replace the global provider policy and invalidate snapshots."""
    state = await replace_model_provider_policy_state(session, payload.approved_provider_ids)

    # Never publish uncommitted policy to the runtime. A failed commit leaves
    # the previous in-memory ceiling and cached decisions intact.
    apply_model_provider_policy_state(state)
    return _build_policy_response(state.approved_provider_ids)


__all__ = [
    "ModelProviderPolicyRead",
    "ModelProviderPolicyWrite",
    "RegisteredModelProviderRead",
    "router",
]
