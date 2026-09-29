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

#: TRG-4's subscription renewal loop. Leased for the same reason the dispatcher
#: is: every API replica may run it, and exactly one does at a time, so a
#: provider never sees N renewals of one subscription.
SUBSCRIPTION_LEASE_NAME = "trigger_subscription_renewal"

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

#: Trigger kinds TRG-4 owns. ``inbound_webhook`` is the generic signed endpoint
#: a third-party system posts to; provider kinds arrive with TRG-5 and TRG-6 and
#: name their transport through ``config.mechanism_id``.
KIND_INBOUND_WEBHOOK = "inbound_webhook"

#: Providers the per-trigger ingress route accepts a delivery for. ``webhook``
#: is the generic-HMAC pseudo-provider for ``inbound_webhook`` triggers.
#: Slack is deliberately absent: a Slack app has exactly one Request URL for
#: every workspace it is installed in, so its deliveries arrive on the per-app
#: route and fan out to triggers there, rather than naming one trigger each.
PROVIDER_WEBHOOK = "webhook"
PROVIDER_SLACK = "slack"
PROVIDER_MICROSOFT = "microsoft"
PROVIDER_GOOGLE = "google"
INGRESS_PROVIDERS = frozenset({PROVIDER_WEBHOOK, PROVIDER_MICROSOFT, PROVIDER_GOOGLE})

#: Ledger dedupe-key prefix for a Slack event, from either Slack mechanism. The
#: one prefix named for a provider rather than a producer, on purpose: Slack's
#: ``event_id`` is stable across the Events API's retries *and* a Socket Mode
#: redelivery, so both producers must write the same key for a trigger moving
#: between transports to collapse the event it sees twice.
DEDUPE_PREFIX_SLACK = "slack"

#: Ledger dedupe-key prefix for a delivery that arrived through push ingress.
#: The suffix is the provider's own event identity, which is what makes a Slack
#: retry at zero, one, and five minutes collapse into one run.
INGRESS_DEDUPE_PREFIX = "ingress"

#: Audit action words for ingress decisions. Rejections are audited because an
#: unauthenticated endpoint's refusals are the only signal an operator has that
#: someone is probing it.
AUDIT_INGRESS_ACCEPT = "trigger_ingress:accept"
AUDIT_INGRESS_REJECT = "trigger_ingress:reject"
AUDIT_SUBSCRIPTION_RENEW = "trigger_subscription:renew"
AUDIT_SUBSCRIPTION_REVOKE = "trigger_subscription:revoke"

#: Slack trigger kinds (TRG-5). Each runs on either Slack mechanism; which one is
#: decided per trigger from the connection it resolves and recorded as
#: ``config.mechanism_id``, never named by the flow.
KIND_SLACK_MESSAGE = "slack.message"
KIND_SLACK_REACTION = "slack.reaction"
SLACK_TRIGGER_KINDS = frozenset({KIND_SLACK_MESSAGE, KIND_SLACK_REACTION})

#: ``config.mechanism_id`` values for Slack, equal to the ``mechanism_id`` rows
#: of design/dedicated-integrations-triggers/matrices/slack-events.json.
MECHANISM_SLACK_EVENTS_API = "slack.events_api"
MECHANISM_SLACK_SOCKET_MODE = "slack.socket_mode"

#: ``trigger.provider_state`` key recording which Slack app a Socket Mode
#: trigger's connection proved it belongs to, in that socket's ``hello``. It is a
#: fact about the connection, so it goes whenever the trigger's connection changes.
SLACK_PROVIDER_STATE_APP_ID = "slack_app_id"

#: Mechanisms a provider pushes to Langflow's ingress (Track A). A run started
#: by one executes as the ``trigger_push`` family; everything else a trigger
#: runs - listener sources and the schedule - as ``trigger_listener``.
PUSH_MECHANISMS = frozenset({MECHANISM_SLACK_EVENTS_API})

#: Kinds whose configuration, connection and mechanism are owned by a canvas
#: node and written only by flow-save reconciliation. The owner API never
#: creates them or edits those fields: that is the one writer who normalizes
#: the configuration and proves the connection belongs to the trigger owner.
CANVAS_ONLY_KINDS = SLACK_TRIGGER_KINDS
