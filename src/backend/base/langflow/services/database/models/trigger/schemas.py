"""Wire and vocabulary types for triggers, the event ledger, and their leases.

The vocabulary lives here (not on the table module) so the dispatcher, the API
layer, and later trigger tickets (TRG-3 listeners, TRG-4 ingress, TRG-5/TRG-6
provider triggers) can import the enums without importing SQLModel tables.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Trigger kinds are open-ended on purpose: TRG-5/TRG-6 register provider kinds
# (``slack.message``, ``google.calendar``) without a migration. The pattern is the
# contract — lowercase, dot-separated, no whitespace — so a kind is safe to use as
# a registry key, a metric label, and a path-free identifier across planes.
TRIGGER_KIND_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$"
PROVIDER_PATTERN = r"^[a-z][a-z0-9_-]*$"
DEDUPE_KEY_MAX_LENGTH = 255


class TriggerState(str, Enum):
    """Lifecycle of a trigger row.

    ``pending`` is the reconciled-but-not-yet-armed state a canvas save creates;
    ``active`` is the only state the scheduler and dispatcher act on.
    """

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    NEEDS_RECONNECT = "needs_reconnect"
    ERROR = "error"
    DEAD = "dead"


#: States that a tick producer or ingress route may append events for.
LIVE_TRIGGER_STATES = frozenset({TriggerState.ACTIVE.value})


class TriggerEventState(str, Enum):
    """Ledger row lifecycle.

    ``claimed`` means a dispatcher holds a lease; ``dispatched`` means a
    background job exists for the row. ``dead`` is the terminal dead-letter state
    reached when ``attempt`` hits the trigger's ``max_attempts``.
    """

    PENDING = "pending"
    CLAIMED = "claimed"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


#: Rows that no dispatcher will ever pick up again.
TERMINAL_EVENT_STATES = frozenset(
    {TriggerEventState.COMPLETED.value, TriggerEventState.FAILED.value, TriggerEventState.DEAD.value}
)
#: Rows that count against a trigger's concurrency cap.
IN_FLIGHT_EVENT_STATES = frozenset({TriggerEventState.CLAIMED.value, TriggerEventState.DISPATCHED.value})


class TriggerBindingTarget(str, Enum):
    """What a fired event runs.

    ``flow`` runs the saved flow (or the pinned ``flow_version`` when set)
    through the background execution service. ``deployment`` is stored but not
    dispatched in 1.13 — see :class:`BindingUnsupportedError`.
    """

    FLOW = "flow"
    DEPLOYMENT = "deployment"


class TriggerSessionPolicy(str, Enum):
    """How a dispatched run derives its session id when the payload has no conversation."""

    PER_EVENT = "per_event"
    SHARED = "shared"


class TriggerCatchupPolicy(str, Enum):
    """What the schedule tick producer does with ticks missed while the process was down."""

    COALESCE = "coalesce"
    SKIP = "skip"


class TriggerSubscriptionState(str, Enum):
    """Provider-side subscription lifecycle (consumed by TRG-4/TRG-6)."""

    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    ERROR = "error"


class TriggerBase(BaseModel):
    """Fields a client may set on a trigger."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    kind: str = Field(min_length=1, max_length=64, pattern=TRIGGER_KIND_PATTERN)
    provider: str | None = Field(default=None, max_length=64, pattern=PROVIDER_PATTERN)
    node_id: str | None = Field(default=None, max_length=255)
    connection_id: UUID | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    binding_target: TriggerBindingTarget = TriggerBindingTarget.FLOW
    deployment_id: UUID | None = None
    flow_version_id: UUID | None = None
    session_policy: TriggerSessionPolicy = TriggerSessionPolicy.PER_EVENT
    concurrency_limit: int = Field(default=1, ge=1, le=100)
    max_attempts: int = Field(default=5, ge=1, le=20)


class TriggerCreate(TriggerBase):
    flow_id: UUID
    state: TriggerState = TriggerState.PENDING


class TriggerUpdate(BaseModel):
    """Partial update. Every field is optional; unset fields are left alone."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: dict[str, Any] | None = None
    connection_id: UUID | None = None
    binding_target: TriggerBindingTarget | None = None
    deployment_id: UUID | None = None
    flow_version_id: UUID | None = None
    session_policy: TriggerSessionPolicy | None = None
    concurrency_limit: int | None = Field(default=None, ge=1, le=100)
    max_attempts: int | None = Field(default=None, ge=1, le=20)


class TriggerPinRequest(BaseModel):
    """Pin or unpin the flow version a trigger fires.

    ``flow_version_id=None`` unpins, which is why the field is required and
    explicitly nullable rather than optional: an empty body must not silently
    unpin.
    """

    model_config = ConfigDict(extra="forbid")

    flow_version_id: UUID | None


class TriggerReplayRequest(BaseModel):
    """Replay one ledger row as a new, linked event."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID


class TriggerTestRequest(BaseModel):
    """Append a synthetic event so an owner can exercise a trigger end to end."""

    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any] = Field(default_factory=dict)


class TriggerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    flow_id: UUID
    user_id: UUID | None
    name: str
    kind: str
    provider: str | None
    node_id: str | None
    connection_id: UUID | None
    config: dict[str, Any]
    state: str
    binding_target: str
    deployment_id: UUID | None
    flow_version_id: UUID | None
    session_policy: str
    concurrency_limit: int
    max_attempts: int
    next_fire_at: datetime | None
    last_fired_at: datetime | None
    last_error: str | None
    created_at: datetime | None
    updated_at: datetime | None


class TriggerEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trigger_id: UUID
    dedupe_key: str
    state: str
    attempt: int
    available_at: datetime | None
    payload: dict[str, Any]
    session_id: str | None
    job_id: UUID | None
    replay_of_event_id: UUID | None
    error: str | None
    created_at: datetime | None
    updated_at: datetime | None

    @field_validator("payload", mode="before")
    @classmethod
    def _default_payload(cls, value: Any) -> Any:
        """Legacy/NULL payloads read back as ``{}`` rather than failing the response."""
        return {} if value is None else value
