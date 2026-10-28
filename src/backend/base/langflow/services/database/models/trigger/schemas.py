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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

#: States an owner turned on and nothing has told to stop: the rows an operator's
#: bulk pause takes out of service. ``pending`` is excluded because a canvas save
#: creates it without the owner's consent, so a bulk resume must never arm it.
ARMED_TRIGGER_STATES = frozenset(
    {TriggerState.ACTIVE.value, TriggerState.ERROR.value, TriggerState.NEEDS_RECONNECT.value}
)


class TriggerAction(str, Enum):
    """Per-trigger operations a client may offer, in display order.

    Each maps to one route, except ``reconnect``, which is the client's own
    navigation to the connection's reconnect or background-runs consent flow,
    followed by ``resume``.
    """

    PAUSE = "pause"  # POST /triggers/{id}/disable
    RESUME = "resume"  # POST /triggers/{id}/enable
    TEST = "test"  # POST /triggers/{id}/test
    RECONNECT = "reconnect"  # client navigation, then resume
    REPLAY = "replay"  # POST /triggers/{id}/replay
    DELETE = "delete"  # DELETE /triggers/{id}
    # An action name, not a credential. POST /triggers/{id}/signing-secret
    ROTATE_SECRET = "rotate_secret"  # noqa: S105  # pragma: allowlist secret


class TriggerReason(str, Enum):
    """Stable, locale-catalog keys explaining a trigger's state or a refused action.

    ``TriggerRead.reason`` carries one of the state reasons (or null for a
    healthy, running trigger); ``TriggerRead.blocked_actions`` maps each refused
    action to a state reason or to one of the caller reasons below. The human
    detail stays in ``last_error``.
    """

    # State reasons.
    PENDING = "pending"
    CONFIG_INVALID = "config_invalid"
    DEGRADED = "degraded"
    PAUSED = "paused"
    PAUSED_BY_ADMIN = "paused_by_admin"
    NODE_REMOVED = "node_removed"
    SOURCE_SETTINGS_CHANGED = "source_settings_changed"
    ERROR = "error"
    NEEDS_RECONNECT = "needs_reconnect"
    CONSENT_REQUIRED = "consent_required"
    EXPIRED = "expired"
    DEAD = "dead"
    # Caller and applicability reasons; only ever values in ``blocked_actions``.
    INSUFFICIENT_PERMISSION = "insufficient_permission"
    NOT_CONNECTION_OWNER = "not_connection_owner"
    RECONNECT_NOT_NEEDED = "reconnect_not_needed"


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

    @field_validator("name", "config", "binding_target", "session_policy", "concurrency_limit", "max_attempts")
    @classmethod
    def _reject_null_required_fields(cls, value: Any) -> Any:
        """Omission leaves a field unchanged; only nullable references may be cleared."""
        if value is None:
            msg = "This field cannot be null."
            raise ValueError(msg)
        return value


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
    admin_paused_at: datetime | None = None
    created_at: datetime | None
    updated_at: datetime | None
    # Server-computed for the caller; the UI renders these and never re-derives
    # them from ``state``. An action in neither collection does not apply to
    # this trigger and is not shown.
    reason: TriggerReason | None = None
    allowed_actions: list[TriggerAction] = Field(default_factory=list)
    blocked_actions: dict[TriggerAction, TriggerReason] = Field(default_factory=dict)
    # Filled on list responses. ``owner_username`` only in the operator view.
    flow_name: str | None = None
    owner_username: str | None = None


class TriggerListScope(str, Enum):
    """Whose triggers ``GET /triggers`` returns."""

    MINE = "mine"
    ALL = "all"


class TriggerBulkRequest(BaseModel):
    """Select triggers for an operator bulk pause or resume.

    At least one filter is required so an empty body can never mean "every
    trigger on the instance". Both filters together select their intersection.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str | None = Field(default=None, max_length=64, pattern=PROVIDER_PATTERN)
    trigger_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=500)
    dry_run: bool = False

    @model_validator(mode="after")
    def _require_a_filter(self) -> TriggerBulkRequest:
        if self.provider is None and not self.trigger_ids:
            msg = "Name a provider, trigger_ids, or both."
            raise ValueError(msg)
        return self


class TriggerBulkFailure(BaseModel):
    trigger_id: UUID
    detail: str


class TriggerBulkResult(BaseModel):
    """What a bulk pause or resume did, or would do on a dry run.

    ``matched`` counts every trigger the filter selected; each lands in exactly
    one of ``changed``, ``unchanged`` (not eligible: already paused, never
    enabled, or not paused by an operator) or ``failed``.
    """

    action: TriggerAction
    dry_run: bool
    matched: int
    changed: list[UUID]
    unchanged: list[UUID]
    failed: list[TriggerBulkFailure]
    owners: int = Field(description="Distinct owners of the changed triggers.")


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


class TriggerIngressRead(BaseModel):
    """Where a caller posts to a trigger. Never carries the secret."""

    model_config = ConfigDict(from_attributes=True)

    trigger_id: UUID
    public_id: str | None
    ingress_url: str | None
    has_signing_secret: bool


class TriggerSigningSecretRead(TriggerIngressRead):
    """The one response that carries a signing secret, on the way out.

    Nothing reads the secret back: the stored form is encrypted, the GET route
    reports only whether one is set, and a lost secret is rotated rather than
    recovered.
    """

    signing_secret: str
