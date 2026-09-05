# Self-managed ingress and the no-relay rule

Status: accepted
Decision ID: self-managed-ingress
Applies to: `public_ingress_by_context` and every `ingress_requirement` in `matrices/*-events.json`
Owners (sign-off roles): platform owner, Enterprise owner, hosted-app owner, release owner
Last verified: 2026-09-05

## Context

TRG-1 exit criterion 4, and the user story that names it: an Enterprise customer without public ingress needs a
written answer for which sources work on their instance. It is also the criterion the deferred record's re-open
trigger 3 measures ("two of three providers' event delivery confirmed usable from a self-managed instance without
public ingress"). The answer has to be per provider and per deployment context, and it has to say what Langflow will
not do, because the obvious product answer - Langflow hosts a relay that accepts provider webhooks and forwards them
to the customer's instance - is the one that would quietly turn a self-managed deployment into a hosted dependency.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | Slack Socket Mode needs no public URL: the app dials out over a WebSocket authenticated with an app-level token | https://docs.slack.dev/apis/socket-mode/ | 2026-09-05 | high |
| 2 | A Socket Mode app cannot be distributed through the Slack Marketplace, so the hosted (distributed) registration cannot use it | https://docs.slack.dev/apis/socket-mode/ | 2026-09-05 | high |
| 3 | Microsoft Graph delta queries are ordinary outbound calls returning `@odata.deltaLink`, and a stale link fails with 410 `syncStateNotFound` | https://learn.microsoft.com/en-us/graph/delta-query-overview | 2026-09-05 | high |
| 4 | Google Calendar and Drive both publish a sync-token / page-token change feed reachable with ordinary outbound calls | https://developers.google.com/workspace/calendar/api/guides/sync and https://developers.google.com/workspace/drive/api/guides/manage-changes | 2026-09-05 | high |
| 5 | Google Calendar and Drive push channels require an https `address` on a domain verified with Google and a valid certificate | https://developers.google.com/workspace/calendar/api/guides/push | 2026-09-05 | high |
| 6 | A Cloud Pub/Sub subscription can be pull rather than push; a pull subscriber opens an outbound connection and acknowledges by ack id | https://cloud.google.com/pubsub/docs/pull | 2026-09-05 | high |
| 7 | Gmail `users.watch` publishes to a Pub/Sub topic in a Cloud project the customer owns, and requires the restricted `gmail.readonly` scope | https://developers.google.com/workspace/gmail/api/guides/push | 2026-09-05 | high |
| 8 | The accepted 1.13 Google restricted-scope decision is "avoid": the hosted Langflow Google app requests no restricted scope | `../dedicated-integrations/decisions/google-restricted-scopes.md` | 2026-09-01 | high |
| 9 | Microsoft Graph change notifications need a publicly reachable `notificationUrl` that answers the `validationToken` handshake within ten seconds | https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks | 2026-09-05 | high |

## Options

### Option A: Track A only, and self-managed customers must expose an ingress

Pros: one code path per provider; lowest engineering cost.
Cons: fails the user story outright for air-gapped and firewalled instances, and fails re-open trigger 3.
Cost: none, but the gate cannot close on it.

### Option B: Langflow operates a relay that receives provider webhooks and forwards them

Pros: every provider works everywhere with one mechanism.
Cons: every self-managed customer's event payloads traverse Langflow-operated infrastructure, which is precisely
what a self-managed deployment is bought to avoid; it creates a hosted availability dependency for self-managed
instances, a multi-tenant secret custody problem for signing secrets, and a data-residency question no wave-1 ticket
answers. Not recommended.
Cost: a new operated service with its own SLO, on-call, and Enterprise contractual surface.

### Option C: one outbound-only mechanism per provider, and no relay (selected)

Pros: every provider has a documented answer without ingress; the outbound mechanisms are ones the providers already
publish (facts 1, 3, 4, 6); it is verifiable by a machine check.
Cons: outbound mechanisms have poll latency rather than push latency, and Slack's outbound mechanism is not available
to the hosted registration (fact 2), so the transport differs by context and the frontend has to explain that.
Cost: TRG-3's poll loop and Socket Mode adapter, both already in the TRG estimate.

## Decision

Option C, with the rule stated first: **Langflow operates no relay.** No Langflow-operated service receives provider
events on behalf of a self-managed instance, in this release or as a follow-up, and no gate record may assume one.
Every mechanism is either delivered directly to the customer's own ingress or fetched by the customer's own instance.

Every wave-1 provider therefore ships at least one `outbound_only` mechanism, and the checker enforces it:

| Provider | Track A (needs public HTTPS) | Track B (no ingress) | Context notes |
|---|---|---|---|
| Slack | `slack.events_api` | `slack.socket_mode` | Socket Mode is unavailable on hosted (fact 2); hosted uses the Events API |
| Microsoft | `microsoft.graph_change_notifications` | `microsoft.graph_delta_poll` | delta is the same recovery path Graph itself prescribes after a `missed` lifecycle event |
| Google Calendar and Drive | `google.calendar_push`, `google.drive_push` | `google.calendar_sync_poll`, `google.drive_changes_poll` | this is the gate's answer to "Calendar and Drive without ingress": poll, do not relay |
| Google Gmail | `google.gmail_watch_pubsub_push` | `google.gmail_watch_pubsub_pull` | both need a customer-owned registration and Cloud project (facts 7, 8); neither ships on hosted |

`public_ingress_by_context` is fixed for all three providers as hosted `available`, self-managed `conditional`,
desktop `unavailable`, headless `unavailable`. "Conditional" is the honest word for self-managed: some instances have
an ingress and some do not, so a Track A mechanism may offer itself there only when it names an `outbound_only`
fallback that covers the same context. Desktop and headless are `unavailable` outright - Desktop has no stable public
URL, and the process-model decision gives `lfx serve` no trigger surface at all.

The customer-owned side of this is a documented prerequisite, not a Langflow feature: Google push needs the
notification domain verified with Google (fact 5), Graph needs a reachable `notificationUrl` (fact 9), and Gmail on
either transport needs a Cloud project with a Pub/Sub topic that grants the Gmail service account publish rights
(fact 7).

## Consequences

- Re-open trigger 3 of `../dedicated-integrations/triggers-deferred.md` is satisfied by three providers, not two:
  Slack via Socket Mode, Microsoft via delta, Google via sync-token and page-token polling plus Pub/Sub pull.
- Latency is a context-dependent product property. A self-managed instance without ingress sees poll-interval
  latency, and TRG-7 shows the active transport and its latency class on the trigger, rather than implying push.
- The Enterprise ingress documentation gains a triggers section: which routes must be reachable, and that not
  exposing them costs latency rather than function.
- `LANGFLOW_PUBLIC_URL` (TRG-4) is required only for Track A; a no-ingress instance leaves it unset and every Track A
  trigger reports a typed "no public URL configured" reason rather than failing at subscription time.
- Nothing in this initiative may add a Langflow-operated forwarding component. A future proposal to do so replaces
  this record rather than extending it.

## Re-open trigger

- A customer contract requires push latency on a self-managed instance with no ingress and accepts a relay's data
  path in writing, or
- a provider withdraws its outbound mechanism (Slack withdraws Socket Mode; Microsoft withdraws delta for a wave-1
  resource; Google withdraws Pub/Sub pull), which would leave that provider with no no-ingress answer, or
- Google changes the drive.file change-feed visibility rules in a way that makes the Drive fallback useless.

Re-verify by: the 1.14 planning gate.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| platform owner | | | |
| Enterprise owner | | | |
| hosted-app owner | | | |
| release owner | Eric Hare | 2026-09-05 | #14911 |
