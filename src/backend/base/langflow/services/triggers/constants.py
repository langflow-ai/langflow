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


#: Trigger kinds TRG-4 owns. ``inbound_webhook`` is the generic signed endpoint
#: a third-party system posts to; provider kinds arrive with TRG-5 and TRG-6 and
#: name their transport through ``config.mechanism_id``.
KIND_INBOUND_WEBHOOK = "inbound_webhook"

#: Providers the ingress route accepts a delivery for. ``webhook`` is the
#: generic-HMAC pseudo-provider for ``inbound_webhook`` triggers; the other
#: three are the wave-1 providers frozen by the gate.
PROVIDER_WEBHOOK = "webhook"
PROVIDER_SLACK = "slack"
PROVIDER_MICROSOFT = "microsoft"
PROVIDER_GOOGLE = "google"
INGRESS_PROVIDERS = frozenset({PROVIDER_WEBHOOK, PROVIDER_SLACK, PROVIDER_MICROSOFT, PROVIDER_GOOGLE})

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
