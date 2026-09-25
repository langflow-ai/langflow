"""Trigger persistence and lifecycle.

The trigger *row* is authoritative for state, binding, pinning, and identity.
The canvas node is authoritative only for the trigger's own configuration
fields, which reconciliation copies into ``config`` on every flow save (TRG-2's
schedule reconciler). That split is what lets a pinned trigger keep firing the
pinned version while its cron expression still tracks the canvas.

Authorization is deliberately NOT here: triggers ride the flow resource, and the
API layer holds the ``ensure_flow_permission`` calls so every guard is visible
next to the route it protects.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import col, select

from langflow.services.base import Service
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.exceptions import FlowVersionNotFoundError
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import (
    TriggerCreate,
    TriggerState,
    TriggerUpdate,
)
from langflow.services.triggers.cleanup import delete_triggers
from langflow.services.triggers.constants import (
    CANVAS_ONLY_KINDS,
    GOOGLE_SOURCE_KINDS,
    MICROSOFT_SOURCE_KINDS,
    PUSH_MECHANISMS,
    SLACK_TRIGGER_KINDS,
)
from langflow.services.triggers.errors import TriggerNotFoundError
from langflow.services.triggers.ownership import require_owned_connection
from langflow.services.triggers.reconciliation import apply_config_verdict
from langflow.services.triggers.schedule_config import schedule_timing_changed, validate_schedule_config

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

#: Bytes of entropy behind a trigger's public ingress address. The address is
#: unauthenticated and guessable-by-brute-force is the failure to avoid, so it
#: is a random 256-bit value rendered URL-safe, not a sequence or a UUID.
_PUBLIC_ID_BYTES = 24
_SIGNING_SECRET_BYTES = 32


def mint_public_id() -> str:
    """An opaque, URL-safe ingress address for one trigger."""
    return secrets.token_urlsafe(_PUBLIC_ID_BYTES)


def mint_signing_secret() -> str:
    """A shared secret for the generic HMAC verifier."""
    return secrets.token_urlsafe(_SIGNING_SECRET_BYTES)


#: Only these states are re-armable by ``enable``. ``dead`` is terminal: a dead
#: trigger is re-created, not resurrected, so the audit trail stays truthful.
_ENABLEABLE_STATES = frozenset(
    {
        TriggerState.PENDING.value,
        TriggerState.ACTIVE.value,
        TriggerState.PAUSED.value,
        TriggerState.ERROR.value,
        TriggerState.EXPIRED.value,
        TriggerState.NEEDS_RECONNECT.value,
    }
)


def _reject_mechanism(config: dict | None) -> None:
    """``config.mechanism_id`` is derived by the server, never chosen by a client.

    It decides which transport and which verifier a trigger is armed against, so
    accepting it from a request would let a caller point a trigger at a
    mechanism its connection cannot prove.
    """
    if config and "mechanism_id" in config:
        msg = "mechanism_id is derived from the trigger's connection and cannot be set."
        raise ValueError(msg)


async def _arm_slack(session: AsyncSession, row: Trigger) -> None:
    """Re-check a Slack trigger's filters, re-derive its connection and transport, and check it may run unattended.

    Re-derived rather than trusted: the connection can change between the save
    that recorded it and this enable (reinstalled, swapped for an app-level
    token, its background-runs consent withdrawn). The filters are re-checked
    too: a save that refused them stored them as entered, and arming those
    would leave an ``active`` trigger that can never match. Raises a
    ``ValueError`` with the owner-facing reason, which the route answers with 409.
    """
    from langflow.services.connection.oauth.config import deployment_context
    from langflow.services.triggers.providers.slack.arming import (
        bind_connection,
        check_ready_to_arm,
        resolve_arming,
    )
    from langflow.services.triggers.providers.slack.config import normalize_slack_config

    config = normalize_slack_config(row.kind, row.config or {})
    arming = await resolve_arming(session, owner_id=row.user_id, config=config, context=deployment_context())
    await check_ready_to_arm(session, kind=row.kind, config=config, arming=arming)
    moved = bind_connection(row, arming.connection_id)
    if moved or config.get("mechanism_id") != arming.mechanism_id:
        row.config = {**config, "mechanism_id": arming.mechanism_id}
        session.add(row)


class TriggerService(Service):
    """Data access for the ``trigger`` table."""

    name = "triggers_service"

    def __init__(self) -> None:
        self.set_ready()

    async def get(self, session: AsyncSession, trigger_id: UUID) -> Trigger:
        row = await session.get(Trigger, trigger_id)
        if row is None:
            raise TriggerNotFoundError(str(trigger_id))
        return row

    async def list_for_flows(
        self,
        session: AsyncSession,
        *,
        flow_ids: list[UUID],
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trigger]:
        """List triggers on the given flows, newest first.

        An empty ``flow_ids`` returns an empty list without touching the
        database: a caller with no visible flows must not fall through to an
        unfiltered scan.
        """
        if not flow_ids:
            return []
        statement = (
            select(Trigger)
            .where(col(Trigger.flow_id).in_(flow_ids))
            .order_by(col(Trigger.created_at).desc(), col(Trigger.id).desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await session.exec(statement)).all())

    async def list_active(self, session: AsyncSession, *, kind: str | None = None) -> list[Trigger]:
        """Every armed trigger, optionally narrowed to one kind.

        Used by the schedule tick producer; kept here so the dispatcher never
        writes its own trigger queries.
        """
        statement = select(Trigger).where(Trigger.state == TriggerState.ACTIVE.value)
        if kind is not None:
            statement = statement.where(Trigger.kind == kind)
        return list((await session.exec(statement)).all())

    async def get_by_node(self, session: AsyncSession, *, flow_id: UUID, node_id: str) -> Trigger | None:
        statement = select(Trigger).where(Trigger.flow_id == flow_id, Trigger.node_id == node_id)
        return (await session.exec(statement)).first()

    async def create(self, session: AsyncSession, *, payload: TriggerCreate, owner_id: UUID) -> Trigger:
        if payload.kind in CANVAS_ONLY_KINDS:
            msg = f"A {payload.kind!r} trigger is created by adding its component to the flow, not through this API."
            raise ValueError(msg)
        _reject_mechanism(payload.config)
        await self._validate_flow_version(session, flow_id=payload.flow_id, flow_version_id=payload.flow_version_id)
        if payload.connection_id is not None:
            await require_owned_connection(session, connection_id=payload.connection_id, owner_id=owner_id)
        config = payload.config
        if payload.kind == "schedule" and (config or payload.state is TriggerState.ACTIVE):
            config = validate_schedule_config(config)
        row = Trigger(
            flow_id=payload.flow_id,
            user_id=owner_id,
            name=payload.name,
            kind=payload.kind,
            provider=payload.provider,
            node_id=payload.node_id,
            connection_id=payload.connection_id,
            config=config,
            provider_state={},
            state=payload.state.value,
            binding_target=payload.binding_target.value,
            deployment_id=payload.deployment_id,
            flow_version_id=payload.flow_version_id,
            session_policy=payload.session_policy.value,
            concurrency_limit=payload.concurrency_limit,
            max_attempts=payload.max_attempts,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def update(self, session: AsyncSession, *, row: Trigger, payload: TriggerUpdate) -> Trigger:
        """Apply a partial update. Unset fields are left alone.

        ``exclude_unset`` (not ``exclude_none``) is the whole point: it is how a
        caller clears ``connection_id`` or unpins ``flow_version_id`` by sending
        an explicit null, without every other omitted field being nulled too.
        """
        changes = payload.model_dump(exclude_unset=True)
        if row.kind in CANVAS_ONLY_KINDS and ({"config", "connection_id"} & changes.keys()):
            msg = "This trigger's configuration and connection are set on its component in the flow."
            raise ValueError(msg)
        if "config" in changes:
            _reject_mechanism(changes["config"])
        if changes.get("connection_id") is not None:
            await require_owned_connection(session, connection_id=changes["connection_id"], owner_id=row.user_id)
        if "flow_version_id" in changes:
            await self._validate_flow_version(session, flow_id=row.flow_id, flow_version_id=payload.flow_version_id)
        if "config" in changes and row.kind == "schedule":
            changes["config"] = validate_schedule_config(changes["config"])
            if schedule_timing_changed(row.config or {}, changes["config"]):
                row.next_fire_at = None
            # A schedule that validates clears the error a broken one left.
            apply_config_verdict(row, None)
        for field, value in changes.items():
            setattr(row, field, value.value if hasattr(value, "value") else value)
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def set_state(self, session: AsyncSession, *, row: Trigger, state: TriggerState) -> Trigger:
        row.state = state.value
        if state is not TriggerState.ERROR:
            row.last_error = None
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def enable(self, session: AsyncSession, *, row: Trigger) -> Trigger:
        if row.state not in _ENABLEABLE_STATES:
            msg = f"Trigger in state {row.state!r} cannot be enabled."
            raise ValueError(msg)
        if row.kind == "schedule":
            validate_schedule_config(row.config or {})
        if row.kind in SLACK_TRIGGER_KINDS:
            await _arm_slack(session, row)
        if row.kind in MICROSOFT_SOURCE_KINDS | GOOGLE_SOURCE_KINDS:
            from langflow.services.triggers.source_arming import check_ready, normalize_source_config, resolve_arming

            config = normalize_source_config(row.kind, row.config or {})
            arming = await resolve_arming(session, kind=row.kind, owner_id=row.user_id, config=config)
            await check_ready(session, kind=row.kind, arming=arming, config=config)
            changed = (
                row.connection_id != arming.connection_id
                or (row.config or {}).get("mechanism_id") != arming.mechanism_id
            )
            row.connection_id = arming.connection_id
            row.config = {**config, "mechanism_id": arming.mechanism_id}
            if changed:
                row.provider_state = {}
            if arming.mechanism_id in PUSH_MECHANISMS:
                from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH
                from langflow.services.triggers.source_poll import poll_source
                from langflow.services.triggers.source_subscription import provision_source

                if not row.public_id:
                    row.public_id = mint_public_id()
                await session.flush()
                if not (row.provider_state or {}).get("baseline_complete"):
                    await poll_source(session, row, family=FAMILY_TRIGGER_PUSH)
                await provision_source(session, row)
                # Read once more after watch creation to cover the gap between
                # establishing the cursor and registering with the provider.
                await poll_source(session, row, family=FAMILY_TRIGGER_PUSH)
            session.add(row)
        # Re-arming starts from now rather than replaying paused ticks. An
        # idempotent enable on an active trigger must preserve its due tick.
        if row.state != TriggerState.ACTIVE.value:
            row.next_fire_at = None
        return await self.set_state(session, row=row, state=TriggerState.ACTIVE)

    async def disable(self, session: AsyncSession, *, row: Trigger) -> Trigger:
        if row.state == TriggerState.DEAD.value:
            msg = "A dead trigger cannot be disabled."
            raise ValueError(msg)
        # Retire the provider-side subscription with the trigger. A paused
        # trigger whose subscription is still live keeps costing the provider's
        # per-tenant quota and keeps delivering notifications this instance will
        # only reject.
        from langflow.services.triggers.subscriptions import revoke_for_trigger

        await revoke_for_trigger(session, trigger_id=row.id)
        return await self.set_state(session, row=row, state=TriggerState.PAUSED)

    async def pin(self, session: AsyncSession, *, row: Trigger, flow_version_id: UUID | None) -> Trigger:
        """Pin the trigger to a flow version, or unpin with ``None``."""
        await self._validate_flow_version(session, flow_id=row.flow_id, flow_version_id=flow_version_id)
        row.flow_version_id = flow_version_id
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def rotate_signing_secret(self, session: AsyncSession, *, row: Trigger) -> str:
        """Mint (or replace) the trigger's ingress address and signing secret.

        The address is minted once and kept: rotating a leaked secret must not
        force every caller to be reconfigured with a new URL. The secret is
        replaced outright, with no grace window, because a secret is rotated
        precisely when the old one must stop working.

        Returns the plaintext secret. It is the only time it exists outside the
        caller's own storage - the row keeps it encrypted, and nothing reads it
        back except the ingress verifier.
        """
        from langflow.services.auth.utils import encrypt_api_key

        if not row.public_id:
            row.public_id = mint_public_id()
        secret = mint_signing_secret()
        row.signing_secret_encrypted = encrypt_api_key(secret)
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return secret

    async def delete(self, session: AsyncSession, *, row: Trigger) -> None:
        await delete_triggers(session, trigger_ids=[row.id])
        await session.flush()

    @staticmethod
    async def _validate_flow_version(session: AsyncSession, *, flow_id: UUID, flow_version_id: UUID | None) -> None:
        if flow_version_id is None:
            return
        version = (await session.exec(select(FlowVersion).where(FlowVersion.id == flow_version_id))).first()
        if version is None or version.flow_id != flow_id:
            msg = "Flow version not found for this trigger's flow."
            raise FlowVersionNotFoundError(msg)
        if version.data is None:
            msg = "A trigger cannot pin a flow version without flow data."
            raise ValueError(msg)

    async def record_error(self, session: AsyncSession, *, row: Trigger, message: str) -> Trigger:
        row.last_error = message
        row.state = TriggerState.ERROR.value
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def get_flow(session: AsyncSession, flow_id: UUID) -> Flow | None:
        return await session.get(Flow, flow_id)
