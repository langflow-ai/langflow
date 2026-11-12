# Trigger audit and GA validation

The owner API records successful Resume (`trigger:resume`), Pause
(`trigger:pause`), and Replay (`trigger:replay`) actions in the existing
`authz_audit_log`. These rows are required even when general authorization
auditing is disabled. Each mutation and its audit row commit together. Resume
records the committed enable intent before provider activation; a resume row
does not prove that a remote subscription became active or that a flow ran.
Rejected requests do not produce a successful mutation row.

The acting user and credential actor identify who requested the action, including
on a shared flow. For an API key, `actor_type` is `api_key` and `actor_id` is the
key UUID; `user_id` remains its user. Audit details contain safe identifiers,
never the event payload, signing secret, or credential value. Replays link
`original_event_id` to `replay_event_id`.

Subscription creation uses `trigger_subscription:create`, once per new local
subscription row. Refreshing the same provider subscription does not emit a
second create row. Creation uses the existing subscription lifecycle audit
settings, as renewal and revocation do. With `LANGFLOW_AUTHZ_AUDIT_ENABLED=true`
and `LANGFLOW_AUTHZ_AUDIT_DURABLE=true`, the creation audit shares the subscription
transaction. With durable mode off, creation stages a best-effort audit in a
savepoint of that same transaction. This adds a savepoint and audit write during
creation; an audit insert failure rolls back only that savepoint. Rolling back
the subscription also removes its creation audit, and no independent writer can
retain a create row for a rolled-back subscription. These background lifecycle
rows have no authenticated user actor.

## List replays from the last thirty days

A superuser can query the existing audit API. Set `SINCE` to the UTC timestamp
thirty days before the query and supply a superuser access token:

```bash
curl --get "$LANGFLOW_URL/api/v1/authz/audit" \
  --header "Authorization: Bearer $ACCESS_TOKEN" \
  --data-urlencode 'action=trigger:replay' \
  --data-urlencode 'event=mutation' \
  --data-urlencode "since=$SINCE" \
  --data-urlencode 'size=200' \
  --data-urlencode 'page=1'
```

Read `items[].user_id`, `actor_type`, `actor_id`, `timestamp`, and the linked event
IDs. Continue through `pages` to obtain the complete window. Optional `resource_id`
and `user_id` filters select one trigger or actor. Ordinary users cannot query
this endpoint. The query covers retained audit rows; it does not backfill actions
performed before these action-specific audits existed.

## Four deployment contexts

This record tracks validation before general availability; it is not a release sign-off. The four
contexts are `hosted`, `self_managed`, `desktop`, and `headless`. The wave-1
[transport matrices](../../design/dedicated-integrations-triggers/matrices/)
remain the source for supported mechanisms. No live provider or deployment
validation was run for this audit change.

Pending means no result has been recorded here. HTTPS means validation also
requires reachable public HTTPS. App open means Desktop validation must prove
that firing stops when the app closes. Unsupported records the existing
[process model](../../design/dedicated-integrations-triggers/decisions/process-model.md):
headless `lfx run` / `lfx serve` hosts neither triggers nor listeners, and Desktop
has no public ingress or hosted relay.

| Wave-1 source / mechanism | hosted | self_managed | desktop | headless |
|---|---|---|---|---|
| Slack message/reaction: Events API | Pending | Pending, HTTPS | Unsupported | Unsupported |
| Slack message/reaction: Socket Mode | Pending | Pending | Pending, app open | Unsupported |
| Microsoft mail/calendar/file: Graph notifications | Pending | Pending, HTTPS | Unsupported | Unsupported |
| Microsoft mail/calendar/file: Graph delta polling | Pending | Pending | Pending, app open | Unsupported |
| Google Calendar: push | Pending | Pending, HTTPS | Unsupported | Unsupported |
| Google Calendar: sync polling | Pending | Pending | Pending, app open | Unsupported |
| Google Drive: push | Pending | Pending, HTTPS | Unsupported | Unsupported |
| Google Drive: changes polling | Pending | Pending | Pending, app open | Unsupported |
| Gmail: Pub/Sub push | Pending | Pending, HTTPS | Unsupported | Unsupported |
| Gmail: Pub/Sub pull | Pending | Pending | Pending, app open | Unsupported |

Before sign-off, expand grouped sources to one result per trigger kind and record
the release commit, installation/bundle versions, transport, expected and observed
behavior, evidence location, reviewer, and date. A failed or unsupported cell
needs an accepted bug or documentation disposition. Local API and service tests
supply regression evidence, not a passing deployment cell.

## Trigger policy and Enterprise hooks

The shared policy bundle carries `approved_trigger_kinds`. Kinds are the stable
provider-qualified identities, such as `google.gmail`, `google.calendar`, and
`slack.message`; core kinds include `schedule` and `inbound_webhook`. A configured
set allows only its exact entries, so omitting every kind from a provider blocks
that provider's triggers. The existing integration-provider ceiling also applies
and cannot be widened by approving a trigger kind.

`null` means unrestricted and keeps the previous OSS behavior and content hash.
An empty list denies every trigger. Nonempty lists are normalized, deduplicated,
and included in the canonical content hash. Use the superuser policy-bundle API
to read the current complete bundle, retain its other facets, and replace the
trigger facet with the current revision as `expected_revision`. Older clients
that omit this field preserve its active value; an explicit `null` clears it.
History, rollback, model-only edits, and catalog-only edits preserve the facet.
Externally managed bundles retain the existing API write restriction.

Deploy every replica with this schema and runtime before configuring the new
ceiling. Earlier releases cannot enforce it. Discovery hides denied components,
and posting their source to component build/update does not reconstruct them.
Enable and dispatch recheck policy; an already queued event cannot bypass a new
ceiling. Refresh pauses denied armed rows in bounded batches, and dispatch also
pauses on a denial before submitting a job. A policy refresh failure denies a
configured ceiling instead of retaining stale allows. Explicit Resume is needed
after approval is restored. Policy denials use `trigger:policy_denied` in the
existing audit API, with safe kind, purpose, and flow identifiers.

An Enterprise trigger service may override `authorize_trigger(context=...)` to
add approval or quota restrictions. The immutable context contains the owner,
kind, purpose (`discover`, `enable`, or `dispatch`), optional flow, and stable
event id. The common ceiling runs first. The hook may raise `TriggerPolicyError`
with a safe owner-facing explanation; it cannot grant a shared-policy denial.
Discovery must not consume quota. Dispatch quota reservations must be atomic in
the external implementation and idempotent by event id across retries. The
dispatch hook runs after provider filtering, immediately before job submission;
reconciliation hints and filtered deliveries cannot reserve a run quota. OSS's
hook adds no approval or quota restrictions. No Enterprise-specific decision
engine or assumed quota is embedded in OSS.

## Instrumented success measures

The existing Prometheus-owning API collector now exports bounded-window gauges
for these measures. The [dashboard](../../deploy/observability/triggers/README.md)
is importable into Grafana. Installation, production measurements, and threshold
selection remain separate from the implementation; no GA result is claimed.

| Measure | Definition | Existing evidence and limitation |
|---|---|---|
| Accepted-event completion | Distinct canonical source events accepted in the collection window, by ledger outcome. The completion fraction excludes filtered (`skipped`) rows. | `langflow_trigger_events` separates `source`, `replay`, and `test`. Provider reconciliation hints are excluded. Pending, claimed, dispatched, failed, and dead outcomes remain visible. An external source cohort and run-level acceptance evidence are still required to detect loss before intake and additional executions; ledger uniqueness alone does not prove either. |
| Accept-to-run dispatch latency | Durable event `created_at` to the minimum retained start job-event timestamp (`build_start` for Langflow, `RUN_STARTED` for AG-UI). Report p50/p95, sample count, missing first-start evidence, and oldest pending age. | `langflow_trigger_dispatch_latency_p50_seconds`, `...p95_seconds`, `...samples`, `langflow_trigger_missing_first_starts`, and `langflow_trigger_oldest_pending_seconds`. Retries use the first start. Missing or purged job-event history is counted as unknown, never as zero latency. Provider-to-accept lag is separate. |
| Subscription renewal continuity | Fenced renewal outcomes with their previous expiry, returned expiry, completion time, and observed recovery gap. | `langflow_trigger_renewals`, `...renewals_with_gap`, `...renewal_gap_seconds`, and `...expired_subscriptions`. Renewal observations commit with subscription state, are retained for the trigger-event retention period, and exclude nonexpiring mechanisms. Intentional retirement is excluded from current-expiry counts. Live deliveries across renewal and provider outages still require acceptance testing. |

Canonical ledger completions that have no submitted job are classified as
`skipped` for these metrics. They represent provider-filtered deliveries, not
successful runs, and are excluded from the completion fraction.

All metrics are gauges over retained records, not all-time counters. The window
is exposed as `langflow_trigger_metrics_window_seconds` and defaults to five
minutes, matching the collector's duration window. Pending age includes older
source rows. Labels use only bounded origin/state/outcome sets and the existing
backend label, never user, flow, trigger, event, or subscription ids or payloads.
Replica-local instrumentation cannot multiply the durable cohort. When scraping
several replicas of one shared database, use the dashboard's `max` aggregation
rather than summing copies. A zero cohort is no data, not 100% completion.

The existing [replica validation](trigger-replica-validation.md) and
[capacity guidance](trigger-capacity.md) describe available local evidence and
its limits. Remaining work before general availability includes configuring and
validating any Enterprise approval/quota adapter, completed deployment results,
ingress/fetch-back security sign-off, a 24-hour chaos soak with renewals, an
in-place 1.13 upgrade with live triggers, installing the dashboard, and recording
measurements for the accepted measures. Local engineering checks do not complete
those live acceptance items.
