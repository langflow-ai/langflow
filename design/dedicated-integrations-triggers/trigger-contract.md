# Trigger contract

Status: accepted
Decision ID: trigger-contract
Applies to: TRG-2 (entity, ledger, dispatcher, families), TRG-3 (listener leases), TRG-4 (ingress and subscriptions), TRG-5 and TRG-6 (source adapters), TRG-7 (frontend)
Owners (sign-off roles): platform owner, lfx owner, langflow-base owner, Enterprise owner, release owner
Last verified: 2026-09-05

TRG-1 exit criterion 6. This is the contract every other triggers ticket builds against: the entity and its tables,
the ledger's delivery rule, how a trigger binds to what it runs, how a triggered run correlates to a conversation,
which identity it executes as, and where the boundary with the 1.13 connection contract sits. Names here are
normative - a ticket that needs a different name changes this record first.

## 1. Entities

Five tables, created by **one** migration on the TRG-2 branch so that TRG-3 and TRG-4 add none. Column shapes below
are the contract; types and indexes are TRG-2's to write.

### `trigger`

The authoritative record of a trigger's existence and state. It is authoritative for state, pinning, and binding;
schedule fields are configured on the node and copied onto `config` when the flow is saved, so a flow export stays
self-contained and the table stays the source of truth for the runtime.

| Column | Meaning |
|---|---|
| `id` | primary key |
| `flow_id` | owning flow, `ON DELETE CASCADE` |
| `user_id` | owner; the identity a dispatched run executes as |
| `kind` | `schedule`, `inbound_webhook`, or a bundle-declared provider kind |
| `provider` | null for core kinds; `slack`, `microsoft`, `google` for provider kinds |
| `mechanism_id` | the `matrices/<provider>-events.json` mechanism this trigger uses, null for core kinds |
| `connection_id` | the INT-4 connection this trigger resolves, nullable |
| `config` | JSON; node-configured fields copied on save (cron expression, timezone, filters) |
| `provider_state` | JSON; cursors owned by the runtime (`deltaLink`, `syncToken`, `startPageToken`, `historyId`) |
| `state` | `pending`, `active`, `paused`, `expired`, `needs_reconnect`, `error`, `dead` |
| `last_error` | typed error code and sanitized message behind the trigger's state |
| `binding_target` | `flow` or `deployment` |
| `flow_version_id` | pinned flow version, nullable |
| `deployment_id` | deployment target, nullable |
| `session_policy` | `per_event` (default) or `provider_correlated` |
| `concurrency_limit` | per-trigger cap on simultaneously dispatched events, default 1 |
| `max_attempts` | per-event attempt cap, default 5 |
| `enabled` | operator and owner switch, distinct from `state` |

### `trigger_event`

The ledger. One row per accepted delivery.

| Column | Meaning |
|---|---|
| `id` | primary key |
| `trigger_id` | owning trigger |
| `dedupe_key` | per-mechanism key from the matrices; **`UNIQUE (trigger_id, dedupe_key)`** |
| `state` | `pending`, `claimed`, `dispatched`, `completed`, `failed`, `dead`, `replayed` |
| `attempt`, `available_at`, `lease_owner`, `lease_expires_at` | claim and retry bookkeeping |
| `payload` | the normalized event, never the raw provider body for thin mechanisms |
| `job_id` | the background-execution job, `ON DELETE SET NULL` |
| `replay_of_event_id` | self-reference; a replay is a new row, never a mutation |
| `error`, timestamps | last failure and audit trail |

### `trigger_lease`

Named singleton leases (`dispatcher`, `schedule_tick`, `purge`, `subscription_renewal`): `name` primary key,
`owner`, `expires_at`. One row per loop, held with a heartbeat, so exactly one API worker runs each loop.

### `trigger_listener_lease`

One row per provider connection a listener holds: `connection_id` primary key, `holder`, `acquired_at`,
`heartbeat_at`. TTL 30 s, heartbeat 10 s, reconcile poll 5 s (`decisions/process-model.md`).

### `trigger_subscription`

Provider-side subscription objects for Track A, plus their renewal schedule: subscription/channel/watch identifier,
`client_state` or channel token, `expires_at`, `renew_after`, row-lock lease columns for the renewal job, and the
owning `trigger_id`. Created by TRG-4 and written by TRG-4 and TRG-6; the table ships in TRG-2's migration.

## 2. Delivery

`decisions/delivery-semantics.md` is normative and is summarized here only so this record reads on its own:
at-least-once at the edge, collapsed once by `UNIQUE (trigger_id, dedupe_key)`; ingress and listeners write the row
and never execute; listeners ack after the commit; replay window 7 days, purge at 30; retries with backoff to
`max_attempts` then `dead`; no cross-trigger ordering; per-trigger concurrency is the backpressure knob.

## 3. Binding and pinning

`binding_target` decides what a dispatched event runs:

| Target | Behaviour in this release |
|---|---|
| `flow` (default) | runs the flow's current saved version through `BackgroundExecutionService` |
| `flow` with `flow_version_id` set | runs that pinned version's data; a pinned version that no longer exists moves the trigger to `error` rather than silently running current |
| `deployment` | stored and shown, but dispatch returns the typed error `trigger_binding_unsupported`; the deployment adapter path is not wired in this release |

A trigger is never re-bound implicitly. Editing the flow does not clear a pin, and unpinning is an explicit action
with its own audit row. The deployment target is stored rather than rejected so the frontend can offer it and so the
follow-up that wires it does not need a migration.

## 4. Correlation

Default `session_policy` is `per_event`: the dispatched run's session id is `trigger:{trigger_id}:{event_id}`, so
every event is its own conversation and nothing leaks between them. `provider_correlated` opts a trigger into the
provider's own conversation key, taken from the `session_key` block of its mechanism row:

| Provider | Session key |
|---|---|
| Slack (both mechanisms) | `slack:{team_id}:{channel}:{thread_ts or ts}` |
| Microsoft Outlook | `microsoft:outlook:{conversationId}` |
| Microsoft calendar | `microsoft:calendar:{iCalUId or seriesMasterId}` |
| Microsoft files | `microsoft:files:{driveItem id}` |
| Google Calendar | `google:calendar:{iCalUID or recurringEventId}` |
| Google Drive | `google:files:{fileId}` |
| Gmail | `google:gmail:{threadId}` |

The push and poll mechanisms of one provider derive the same session key, exactly as they derive the same dedupe
key; a customer moving between transports keeps their conversations.

## 5. Executing identity

Two new families join `scripts/ci/execution_principal_matrix.json`, using the same `execution_family` key and
`FAMILY_*` naming INT-6 introduces (agreed rather than rebased - TRG-2 bases on the INT-5 branch):

| Family | Source | Executes as | Interactive | Notes |
|---|---|---|---|---|
| `trigger_push` | `api/v1/trigger_ingress.py` (TRG-4); `api/v1/triggers.py` until it exists | `flow_owner` | no | provider-signed edge; the request never executes a flow |
| `trigger_listener` | `services/triggers/dispatcher.py` and the listener adapters | `flow_owner` | no | also the only principal allowed to resolve the Slack app-level token |

The dispatcher stamps `ExecutionPrincipal(kind="flow_owner", interactive=False, family=...)` with actor
`trigger_dispatcher` on every submitted run, through its own frame source, so the warm-graph path cannot substitute a
different principal. Because the run is non-interactive, the INT-2 rule applies verbatim: a user connection resolves
only with the per-connection `allow_non_interactive` opt-in, an instance connection resolves under the INT-6 policy
floor, and an anonymous or unknown principal never resolves anything. A trigger whose connection lacks the opt-in
fails closed with a typed `IntegrationError` and moves to `needs_reconnect`; it does not run without credentials.

Authorization rides on the flow resource: managing a trigger requires flow **write**, and replay and test require
flow **execute**. No new authz resource word is introduced, which also spares Enterprise a `roles.py` vocabulary
addition at the next pin bump.

TRG-4's ingress route is classified under a new access mode `provider_signed` (preset `public_or_conditional`) in
`scripts/ci/authz_endpoint_matrix.json`, with a `trigger_ingress` family: unauthenticated at the HTTP layer,
authenticated by the provider's own signature or token, and audited on every rejection.

## 6. Boundary with the 1.13 connection contract

| Obligation | Owner | Status |
|---|---|---|
| The connection record grows no trigger-specific fields | INT-4 | held: trigger state lives on `trigger` and `trigger_subscription` |
| The INT-2 resolver is callable from a non-API process | INT-2 | required by `decisions/process-model.md`; the listener resolves through the registered `BaseConnectionResolverService` |
| INT-5 single-flight refresh coordinates across processes | INT-5 | required: the listener process refreshes the same connection the API might |
| Non-interactive rules apply to trigger families verbatim | INT-6 | this record adds two families, it does not weaken the rule |
| The Slack app-level token is a third named profile (`slack-app-token`, kind `api_key`, identity `bot`, manual entry) resolvable only by `trigger_listener` principals | INT-5 + TRG-5 | new; the only credential-model change triggers ask for |
| A revoked connection cascades to its triggers and their provider subscriptions | INT-4 + TRG-4 | on-revoke hook registry in the connection service; triggers move to `needs_reconnect` |

Triggers own no credential storage of their own. Everything a listener or a renewal job needs is resolved through the
connection service with a trigger principal.

## 7. What this contract does not cover

Provider policy and quotas (TRG-8), the operator approval surface, Enterprise audit query UI, and any relay
(`decisions/self-managed-ingress.md` forbids one).

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| platform owner | | | |
| lfx owner | | | |
| langflow-base owner | | | |
| Enterprise owner | | | |
| release owner | Eric Hare | 2026-09-05 | #14911 |
