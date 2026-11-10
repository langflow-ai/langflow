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

## Proposed success measures

These three engineering measures are proposals. Thresholds, production collection,
and dashboards remain pending; no measurements or dashboard completion are claimed.

| Measure | Definition | Existing evidence and limitation |
|---|---|---|
| Accepted-event completion | For distinct accepted, eligible source events in a bounded cohort, count events with one completed run, missing completions, and additional runs per source identity. Report explicit replays separately and preserve failed/dead-letter outcomes. | `trigger_event` stores dedupe identity, replay linkage, state, and `job_id`; job records carry execution outcomes. The source cohort and a run-level record are needed to detect loss before intake and duplicate execution. Ledger uniqueness alone does not prove either. |
| Accept-to-run dispatch latency | Elapsed time from durable event acceptance to the first job run starting; report the distribution and pending-event ages for the same cohort. | Ledger `created_at` and job state are available, but ledger `updated_at` changes on retries and is not a dispatch timestamp. A dedicated acceptance-to-job-start observation and production collector still need implementation. Provider-to-accept lag is a separate measure. |
| Subscription renewal continuity | For subscriptions requiring renewal during a bounded window, report how many renew before expiry without an active-coverage gap, plus failures and observed gap duration. Exclude intentional revocations and nonexpiring mechanisms. | Subscription expiry/renewal state and lifecycle audits support investigation. Successive provider expiry intervals and deliveries across renewal must be retained to prove continuity; a renewal count alone is insufficient. |

The existing [replica validation](trigger-replica-validation.md) and
[capacity guidance](trigger-capacity.md) describe available local evidence and
its limits. Remaining work before general availability includes the approved-trigger policy facet
(provider/kind/content hash at discovery, enable, and dispatch), Enterprise
approval/quota hooks, policy-denial coverage, completed deployment results,
ingress/fetch-back security sign-off, a 24-hour chaos soak with renewals, an
in-place 1.13 upgrade with live triggers, and instrumentation and dashboards for
the accepted measures. This audit slice does not complete those items.
