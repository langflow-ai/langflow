"""Superuser administration for atomic provider-and-catalog policy bundles."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from lfx.base.models.provider_registry import resolve_provider_id
from lfx.services.deps import get_catalog_policy_service, get_model_provider_policy_service
from lfx.services.model_provider_policy import normalize_blocked_model_key
from lfx.services.policy_bundle import PolicyBundleSnapshot
from pydantic import BaseModel, Field, StringConstraints, field_validator

from langflow.api.utils import DbSession, DbSessionReadOnly
from langflow.api.v1.policy_bundle_errors import policy_bundle_revision_conflict
from langflow.api.v1.schemas.catalog_policy import CatalogPolicyKeyList, normalize_catalog_policy_keys
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.authorization.audit import AUDIT_ALLOW, audit_decision
from langflow.services.database.models.policy_bundle import POLICY_BUNDLE_REASON_MAX_LENGTH
from langflow.services.database.models.user.model import User
from langflow.services.policy_bundle import (
    PolicyBundleApplicationNotSupportedError,
    PolicyBundleNotInitializedError,
    PolicyBundleRevisionConflictError,
    apply_policy_bundle_state,
    ensure_policy_bundle_application_supported,
    get_policy_bundle_state,
    list_policy_bundle_history,
    replace_policy_bundle_state,
    rollback_policy_bundle_state,
)

router = APIRouter(prefix="/policy-bundle", tags=["Policy Bundle"])

ProviderId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=255)]


class PolicyBundleWrite(BaseModel):
    """Complete replacement guarded by the caller's observed revision."""

    expected_revision: int = Field(ge=1)
    approved_provider_ids: Annotated[list[ProviderId], Field(max_length=1000)]
    blocked_component_keys: CatalogPolicyKeyList
    blocked_template_keys: CatalogPolicyKeyList
    # Defaulted so policy writers built before model blocking existed keep
    # working; omitting the field clears no other decision but blocks no models.
    blocked_model_keys: CatalogPolicyKeyList = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=POLICY_BUNDLE_REASON_MAX_LENGTH)

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

    @field_validator("blocked_component_keys", "blocked_template_keys")
    @classmethod
    def normalize_catalog_keys(cls, values: list[str]) -> list[str]:
        return normalize_catalog_policy_keys(values)

    @field_validator("blocked_model_keys")
    @classmethod
    def normalize_model_keys(cls, values: list[str]) -> list[str]:
        try:
            normalized = [normalize_blocked_model_key(value) for value in values]
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return sorted(set(normalized))


class PolicyBundleRollbackWrite(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=POLICY_BUNDLE_REASON_MAX_LENGTH)


class PolicyBundleRead(BaseModel):
    revision: int
    initialized: bool
    source: str
    approved_provider_ids: list[str]
    blocked_component_keys: list[str]
    blocked_template_keys: list[str]
    blocked_model_keys: list[str]
    content_hash: str
    created_at: datetime | None
    created_by: UUID | None
    reason: str | None
    rollback_of_revision: int | None
    managed_externally: bool = False


class PolicyBundleHistoryRead(BaseModel):
    items: list[PolicyBundleRead]
    next_before_revision: int | None


def _managed_externally() -> bool:
    return (
        get_model_provider_policy_service().external_approved_provider_ids is not None
        or get_catalog_policy_service().external_policy_snapshot is not None
    )


def _response(snapshot: PolicyBundleSnapshot, *, managed_externally: bool = False) -> PolicyBundleRead:
    return PolicyBundleRead(
        revision=snapshot.revision,
        initialized=snapshot.initialized,
        source=snapshot.source,
        approved_provider_ids=sorted(snapshot.approved_provider_ids),
        blocked_component_keys=sorted(snapshot.blocked_component_keys),
        blocked_template_keys=sorted(snapshot.blocked_template_keys),
        blocked_model_keys=sorted(snapshot.blocked_model_keys),
        content_hash=snapshot.content_hash,
        created_at=snapshot.created_at,
        created_by=snapshot.created_by,
        reason=snapshot.reason,
        rollback_of_revision=snapshot.rollback_of_revision,
        managed_externally=managed_externally,
    )


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Policy bundle is not initialized. Apply the latest database migrations and restart Langflow.",
    )


def _raise_if_externally_managed() -> None:
    if _managed_externally():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy bundle is externally managed and cannot be changed through this API.",
        )
    try:
        ensure_policy_bundle_application_supported()
    except PolicyBundleApplicationNotSupportedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


async def _audit_bundle(snapshot: PolicyBundleSnapshot, *, user_id: UUID, action: str) -> None:
    await audit_decision(
        user_id=user_id,
        action=action,
        obj=f"policy_bundle:{snapshot.revision}",
        result=AUDIT_ALLOW,
        details={
            "revision": snapshot.revision,
            "content_hash": snapshot.content_hash,
            "source": snapshot.source,
            "rollback_of_revision": snapshot.rollback_of_revision,
            "reason": snapshot.reason,
        },
    )


@router.get("", response_model=PolicyBundleRead)
@router.get("/", response_model=PolicyBundleRead, include_in_schema=False)
async def read_policy_bundle(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSessionReadOnly,
) -> PolicyBundleRead:
    try:
        snapshot = await get_policy_bundle_state(session)
    except PolicyBundleNotInitializedError as exc:
        raise _unavailable() from exc
    return _response(snapshot, managed_externally=_managed_externally())


@router.put("", response_model=PolicyBundleRead)
@router.put("/", response_model=PolicyBundleRead, include_in_schema=False)
async def replace_policy_bundle(
    payload: PolicyBundleWrite,
    admin: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSession,
) -> PolicyBundleRead:
    _raise_if_externally_managed()
    try:
        snapshot = await replace_policy_bundle_state(
            session,
            expected_revision=payload.expected_revision,
            approved_provider_ids=payload.approved_provider_ids,
            blocked_component_keys=payload.blocked_component_keys,
            blocked_template_keys=payload.blocked_template_keys,
            blocked_model_keys=payload.blocked_model_keys,
            actor_user_id=admin.id,
            reason=payload.reason,
        )
    except PolicyBundleNotInitializedError as exc:
        raise _unavailable() from exc
    except PolicyBundleRevisionConflictError as exc:
        raise policy_bundle_revision_conflict(exc) from exc

    try:
        await _audit_bundle(snapshot, user_id=admin.id, action="policy_bundle:replace")
    finally:
        apply_policy_bundle_state(snapshot)
    return _response(snapshot)


@router.get("/history", response_model=PolicyBundleHistoryRead)
async def read_policy_bundle_history(
    _admin: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSessionReadOnly,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_revision: Annotated[int | None, Query(ge=1)] = None,
) -> PolicyBundleHistoryRead:
    items = await list_policy_bundle_history(
        session,
        limit=limit,
        before_revision=before_revision,
    )
    next_before_revision = items[-1].revision if len(items) == limit else None
    return PolicyBundleHistoryRead(
        items=[_response(item) for item in items],
        next_before_revision=next_before_revision,
    )


@router.post("/rollback/{revision}", response_model=PolicyBundleRead)
async def rollback_policy_bundle(
    revision: int,
    payload: PolicyBundleRollbackWrite,
    admin: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSession,
) -> PolicyBundleRead:
    _raise_if_externally_managed()
    try:
        snapshot = await rollback_policy_bundle_state(
            session,
            expected_revision=payload.expected_revision,
            target_revision=revision,
            actor_user_id=admin.id,
            reason=payload.reason,
        )
    except PolicyBundleNotInitializedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PolicyBundleRevisionConflictError as exc:
        raise policy_bundle_revision_conflict(exc) from exc

    try:
        await _audit_bundle(snapshot, user_id=admin.id, action="policy_bundle:rollback")
    finally:
        apply_policy_bundle_state(snapshot)
    return _response(snapshot)


__all__ = [
    "PolicyBundleHistoryRead",
    "PolicyBundleRead",
    "PolicyBundleRollbackWrite",
    "PolicyBundleWrite",
    "router",
]
