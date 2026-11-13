"""The shared trigger ceiling and narrowing hooks for Enterprise governance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from lfx.services import deps as lfx_deps
from lfx.services.integration_policy import (
    IntegrationPolicyError,
    IntegrationPolicyPurpose,
    aresolve_integration_policy,
)

from langflow.services.triggers.constants import POLICY_BLOCKED_ERROR
from langflow.services.triggers.error_codes import CodedTriggerError, TriggerErrorCode

if TYPE_CHECKING:
    from uuid import UUID

    from langflow.services.triggers.service import TriggerService


class TriggerPolicyPurpose(str, Enum):
    DISCOVER = "discover"
    ENABLE = "enable"
    DISPATCH = "dispatch"


@dataclass(frozen=True, slots=True)
class TriggerPolicyContext:
    """Credential-free inputs to an approval or quota check.

    Implementations may narrow the shared ceiling, never widen it. The event id
    is stable across dispatch retries so an external quota reservation can be
    idempotent. Discovery must be a read and must not reserve quota.
    """

    user_id: UUID
    kind: str
    purpose: TriggerPolicyPurpose
    flow_id: UUID | None = None
    event_id: UUID | None = None


class TriggerPolicyError(CodedTriggerError):
    """A safe, reason-coded refusal from the shared ceiling or a governance hook."""

    def __init__(self, message: str = POLICY_BLOCKED_ERROR) -> None:
        super().__init__(TriggerErrorCode.POLICY_BLOCKED, message)
        if message != POLICY_BLOCKED_ERROR:
            # An extension's safe approval/quota explanation must not be
            # replaced by the built-in kind-ceiling translation in the UI.
            self.code = "governance_blocked"


def require_trigger_ceiling(kind: str) -> None:
    """Enforce one immutable shared snapshot, including synchronous discovery."""
    # Capture the complete immutable source state once. A failed refresh must
    # not preserve a stale allow when the trigger facet is configured.
    snapshot, available = lfx_deps.get_policy_bundle_service().read_state()
    if not snapshot.allows_trigger_kind(kind) or (snapshot.approved_trigger_kinds is not None and not available):
        raise TriggerPolicyError
    if "." in kind:
        provider = kind.partition(".")[0]
        if snapshot.approved_integration_provider_ids is not None and (
            not available or provider not in snapshot.approved_integration_provider_ids
        ):
            raise TriggerPolicyError(str(IntegrationPolicyError(provider, IntegrationPolicyPurpose.DISCOVER)))


async def require_trigger_policy(context: TriggerPolicyContext) -> None:
    """Check shared and provider policy, including work that only reconciles a source."""
    require_trigger_ceiling(context.kind)
    if "." in context.kind:
        provider = context.kind.partition(".")[0]
        try:
            integration_policy = await aresolve_integration_policy(
                user_id=context.user_id,
                provider_ids={provider},
                purpose=(
                    IntegrationPolicyPurpose.DISCOVER
                    if context.purpose is TriggerPolicyPurpose.DISCOVER
                    else IntegrationPolicyPurpose.USE
                ),
            )
            integration_policy.require_provider(provider)
        except IntegrationPolicyError as exc:
            raise TriggerPolicyError(str(exc)) from exc


async def require_trigger_allowed(context: TriggerPolicyContext, *, service: TriggerService | None = None) -> None:
    """Evaluate the common ceiling before invoking an optional narrowing hook."""
    await require_trigger_policy(context)
    if service is None:
        from langflow.services.deps import get_trigger_service

        service = get_trigger_service()
    await service.authorize_trigger(context=context)


async def pause_disallowed_triggers(session, *, limit: int = 200) -> int:
    """Converge armed rows after a shared ceiling change without waiting for an event.

    The bounded scan selects only rows the configured kind ceiling excludes;
    repeated refreshes therefore make progress even with many allowed rows.
    Enterprise hooks run at admission/dispatch, not during this reconciliation.
    """
    from sqlmodel import col, select, update

    from langflow.services.database.models.trigger.model import Trigger
    from langflow.services.database.models.trigger.schemas import TriggerState

    snapshot, available = lfx_deps.get_policy_bundle_service().read_state()
    kinds = snapshot.approved_trigger_kinds
    if kinds is None:
        return 0
    statement = select(Trigger).where(col(Trigger.state).in_([TriggerState.ACTIVE.value, TriggerState.PENDING.value]))
    if available:
        statement = statement.where(col(Trigger.kind).not_in(sorted(kinds)))
    rows = (await session.exec(statement.order_by(Trigger.id).limit(limit))).all()
    paused = 0
    for row in rows:
        result = await session.exec(
            update(Trigger)
            .where(
                Trigger.id == row.id,
                col(Trigger.state).in_([TriggerState.ACTIVE.value, TriggerState.PENDING.value]),
            )
            .values(state=TriggerState.PAUSED.value, last_error=POLICY_BLOCKED_ERROR)
        )
        if result.rowcount != 1:
            continue
        stage_policy_denial(session, row=row, purpose=TriggerPolicyPurpose.ENABLE)
        paused += 1
    return paused


def component_trigger_kind(component) -> str | None:
    """Read the class-stamped trigger marker, without inspecting source code."""
    if not isinstance(component, dict):
        return None
    metadata = component.get("metadata")
    if not isinstance(metadata, dict):
        return None
    kind = metadata.get("trigger_kind")
    return kind if isinstance(kind, str) and kind else None


async def filter_trigger_palette(all_types, *, user_id):
    """Copy palette mappings before hiding kinds refused by policy or hooks."""
    filtered = {}
    for category, components in all_types.items():
        visible = {}
        for name, component in components.items():
            kind = component_trigger_kind(component)
            if kind is not None:
                try:
                    await require_trigger_allowed(
                        TriggerPolicyContext(user_id=user_id, kind=kind, purpose=TriggerPolicyPurpose.DISCOVER)
                    )
                except TriggerPolicyError:
                    continue
            visible[name] = component
        filtered[category] = visible
    return filtered


def stage_policy_denial(session, *, row, purpose: TriggerPolicyPurpose, actor_user_id=None) -> None:
    """Write a denial with the state change or after a refused enable releases its lock."""
    from langflow.services.authorization.audit import stage_audit_decision

    stage_audit_decision(
        session=session,
        required=True,
        user_id=actor_user_id if actor_user_id is not None else row.user_id,
        action="trigger:policy_denied",
        obj=f"trigger:{row.id}",
        result="deny",
        details={"kind": row.kind, "purpose": purpose.value, "flow_id": str(row.flow_id)},
    )
