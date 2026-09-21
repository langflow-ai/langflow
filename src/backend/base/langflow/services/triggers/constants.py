"""Names the trigger subsystem shares with the CI matrices and later tickets.

These strings are a contract, not an implementation detail: the execution
principal matrix (``scripts/ci/execution_principal_matrix.json``), the
authorization endpoint matrix, TRG-3's listener process and TRG-4's ingress
routes all key off the same values.
"""

from __future__ import annotations

#: Execution-principal families. Equal, character for character, to the
#: ``family`` values in scripts/ci/execution_principal_matrix.json.
FAMILY_TRIGGER_PUSH = "trigger_push"
FAMILY_TRIGGER_LISTENER = "trigger_listener"
TRIGGER_FAMILIES = frozenset({FAMILY_TRIGGER_PUSH, FAMILY_TRIGGER_LISTENER})

#: The matrix ``actor`` word for a run nobody is waiting on.
ACTOR_TRIGGER_DISPATCHER = "trigger_dispatcher"

#: Trusted background request field and graph-stamping keyword. The worker
#: strips this internal field before validating the public run request.
EXECUTION_FAMILY_KWARG = "execution_family"

#: Template field the dispatcher writes the firing event into, as a JSON string,
#: through the run request's ``tweaks`` keyed by the trigger's canvas node id.
#: This is the seam that carries a provider payload into the flow; it is the
#: same mechanism the Webhook component's payload rides. Equal, character for
#: character, to ``lfx.base.triggers.base.TRIGGER_EVENT_FIELD`` (lfx must not
#: import langflow, so the string is declared on both sides and pinned by
#: ``test_trigger_event_field_matches_the_lfx_component_contract``).
TRIGGER_EVENT_FIELD = "event_payload"

#: Named singleton leases held in ``trigger_lease``.
DISPATCHER_LEASE_NAME = "trigger_dispatcher"
SCHEDULER_LEASE_NAME = "trigger_scheduler"
#: Held by the ONE API worker that supervises the listener subprocess when
#: ``LANGFLOW_LISTENERS_MODE=subprocess``. The API defaults to several uvicorn
#: workers, so without this the single-container shape would start one listener
#: per worker and every connection would be fought over by siblings.
LISTENER_HOST_LEASE_NAME = "trigger_listener_host"

#: Session-id prefixes. ``per_event`` gives each run its own session;
#: ``shared`` keeps one session per trigger so an agent has memory across ticks.
SESSION_PREFIX = "trigger"

#: Ledger dedupe-key prefixes, one per producer.
TICK_DEDUPE_PREFIX = "tick"
REPLAY_DEDUPE_PREFIX = "replay"
TEST_DEDUPE_PREFIX = "test"

#: Listener transports (TRG-3). A ``socket`` adapter owns a long-lived
#: connection and decides its own cadence; a ``poll`` adapter is driven by the
#: generic poll loop. Both are Track B: Langflow dials out, so no public ingress
#: is required.
TRANSPORT_SOCKET = "socket"
TRANSPORT_POLL = "poll"
LISTENER_TRANSPORTS = frozenset({TRANSPORT_SOCKET, TRANSPORT_POLL})

#: Ledger dedupe-key prefix for the built-in fake adapter. It is the only
#: adapter TRG-3 ships; real provider adapters arrive with TRG-5 and TRG-6 and
#: bring their own prefix from the mechanism's ``dedupe_key`` block.
LISTENER_FAKE_DEDUPE_PREFIX = "fake"

#: ``config.mechanism_id`` of the built-in fake adapter, and the trigger ``kind``
#: it is registered under. Both are deliberately un-provider-like so a real
#: matrix mechanism can never collide with it.
LISTENER_FAKE_KIND = "listener_selftest"
LISTENER_FAKE_MECHANISM = "selftest.tick"
