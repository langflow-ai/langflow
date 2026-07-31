"""Superuser administration for the install-wide approved-provider policy."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from lfx.base.models.provider_registry import get_registry_snapshot, resolve_provider_id
from pydantic import BaseModel, Field, StringConstraints, field_validator

from langflow.api.utils import DbSession, DbSessionReadOnly
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.authorization.audit import AUDIT_ALLOW, audit_decision
from langflow.services.database.models.user.model import User
from langflow.services.model_provider_policy import (
    ModelProviderPolicyNotInitializedError,
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

    @field_validator("approved_provider_ids", mode="before")
    @classmethod
    def canonicalize_provider_ids(cls, provider_ids):
        if not isinstance(provider_ids, list):
            return provider_ids
        return [
            resolve_provider_id(provider_id) if isinstance(provider_id, str) else provider_id
            for provider_id in provider_ids
        ]

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


def _policy_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Model-provider policy is not initialized. Apply the latest database migrations and restart Langflow.",
    )


@router.get("", response_model=ModelProviderPolicyRead)
@router.get("/", response_model=ModelProviderPolicyRead, include_in_schema=False)
async def read_model_provider_policy(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSessionReadOnly,
) -> ModelProviderPolicyRead:
    """Read the global provider policy. An empty approved list is unrestricted."""
    try:
        state = await get_model_provider_policy_state(session)
    except ModelProviderPolicyNotInitializedError as exc:
        raise _policy_unavailable() from exc
    return _build_policy_response(state.approved_provider_ids)


@router.post("", response_model=ModelProviderPolicyRead)
@router.post("/", response_model=ModelProviderPolicyRead, include_in_schema=False)
@router.put("", response_model=ModelProviderPolicyRead)
@router.put("/", response_model=ModelProviderPolicyRead, include_in_schema=False)
async def replace_model_provider_policy(
    payload: ModelProviderPolicyWrite,
    admin: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSession,
) -> ModelProviderPolicyRead:
    """Atomically replace the global provider policy and invalidate snapshots."""
    try:
        state = await replace_model_provider_policy_state(session, payload.approved_provider_ids)
    except ModelProviderPolicyNotInitializedError as exc:
        raise _policy_unavailable() from exc

    try:
        await audit_decision(
            user_id=admin.id,
            action="model_provider_policy:replace",
            obj="model_provider_policy:1",
            result=AUDIT_ALLOW,
            details={
                "approved_provider_ids": sorted(state.approved_provider_ids),
                "version": state.version,
            },
        )
    finally:
        # Never publish uncommitted policy to the runtime. A failed commit
        # leaves the previous in-memory ceiling and cached decisions intact.
        # Queue the committed audit first, but still publish if enqueueing
        # fails so this worker cannot keep enforcing stale state.
        apply_model_provider_policy_state(state)
    return _build_policy_response(state.approved_provider_ids)


__all__ = [
    "ModelProviderPolicyRead",
    "ModelProviderPolicyWrite",
    "RegisteredModelProviderRead",
    "router",
]
