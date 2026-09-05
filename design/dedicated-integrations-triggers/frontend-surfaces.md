# Frontend surface list for triggers

Status: accepted
Owners (sign-off roles): frontend owner, release owner
Last verified: 2026-09-05 against `release-1.13.0`

TRG-1 exit criterion 8. Every surface the triggers release needs, tagged with the ticket that owns it and whether it
extends something that exists or is net new. Paths are under `src/frontend/src/`. TRG-7 builds these on the TRG-2 API
without waiting for INT-8's shared connection picker (release owner decision, 2026-09-05); the interim connection
field is called out below and is swapped for the shared picker when INT-8 lands.

## Naming rule for trigger components

The 1.13 palette rule is `Product: Verb Object` (`../dedicated-integrations/decisions/palette-naming.md`). Triggers
extend it rather than replace it: a trigger's display name is **`Product: On Event`** - the product as it is branded,
a colon, `On`, and the event in the provider's own noun.

| Ticket | Display name | Not |
|---|---|---|
| TRG-2 | `Schedule: On Cron` | `Cron Trigger`, `Scheduler` |
| TRG-4 | `Webhook: On Request` | `Inbound Webhook Trigger` |
| TRG-5 | `Slack: On Message`, `Slack: On Reaction` | `Slack Trigger`, `Slack Events` |
| TRG-6 | `Outlook: On Message`, `Calendar: On Event`, `OneDrive: On File Change`, `SharePoint: On File Change` | `Microsoft Graph Trigger` |
| TRG-6 | `Google Calendar: On Event`, `Google Drive: On File Change`, `Gmail: On Message` | `Google Trigger`, `Gmail Watch` |

The rule exists so a user scanning the palette can tell an action from a trigger without reading a description, and
so the two never collide alphabetically in a provider group.

## Surfaces that exist and need extension

| # | Surface | Where | Work | Ticket |
|---|---|---|---|---|
| A1 | Palette categories | `utils/styleUtils.ts` (`SIDEBAR_CATEGORIES`), `pages/FlowPage/components/flowSidebarComponent/index.tsx`, `categoryGroup.tsx` | one `triggers` category entry plus its icon; a category absent from `SIDEBAR_CATEGORIES` and `SIDEBAR_BUNDLES` is simply not rendered, so this is the minimum that makes a trigger node visible. Core triggers (schedule, inbound webhook) live in the category; provider triggers stay in their bundle groups next to that provider's actions | TRG-2 (constant), TRG-7 (behaviour) |
| A2 | Node status header | `CustomNodes/GenericNode/components/NodeStatus/index.tsx` | a trigger state badge beside the existing status, following the `HumanInputNodeBadge` pattern; must not disturb the Composio `auth` polling block that INT-8 is generalizing | TRG-7 |
| A3 | Single-trigger-per-flow gating | `flowSidebarComponent/sidebarItemsList.tsx` and its helpers | port the drop-gating from `origin/feat-native-triggers-v2`, but detect a trigger by the base-class marker TRG-2's base trigger component sets rather than by a literal class name; tooltip text moves into the locale catalogs | TRG-7 |
| A4 | Settings navigation and route | `pages/SettingsPage/index.tsx` (`sidebarNavItems`), `routes.tsx` | one nav entry `/settings/triggers` and one `<Route>`, gated on the config flag | TRG-7 |
| A5 | Query layer | `controllers/API/queries/`, `helpers/constants.ts` (`URLs`), `types.ts` | a `triggers/` query group with react-query keys and invalidation on every mutation; poll interval read from `GET /api/v1/config` (`trigger_polling_interval`, default 5 s) rather than hard-coded | TRG-7 |
| A6 | Show-once secret dialog | the `secretKeyModal` pattern | reuse for a trigger's inbound signing secret: show once on create, copy, rotate; rotation invalidates the old secret immediately | TRG-7 behind TRG-4's API |
| A7 | Icon registry | `icons/lazyIconImports.ts`, `icons/eagerIconImports.ts` | `Gmail`, `GoogleDrive`, `Googlecalendar`, `OneDrive` and `outlook` already exist; a `Clock`-style icon covers the schedule and webhook triggers | TRG-2, TRG-7 |
| A8 | a11y harness | `tests/a11y/*.a11y.spec.ts` with baselines, repo-root `scripts/a11y/a11y_routes.json` | one static route entry plus a stateful `triggers.a11y.spec.ts`; keyboard-only paths for the badge popover, the row menu, the drawer, and the dialogs | TRG-7 |
| A9 | Playwright helpers | `tests/utils/`, `tests/core/features/composio.spec.ts` | a `trigger-mocks.ts` following `deployment-mocks.ts`; the Composio spec (injects a fake component, asserts a button state) is the template for a mocked provider-trigger test | TRG-7 |
| A10 | Connection field on a node | `components/core/parameterRenderComponent/index.tsx` | **interim**: TRG-7 renders the trigger's connection with a plain select over `GET /api/v1/connections` until INT-8's `case "connection_ref"` renderer exists, then deletes the interim field. Called out in the TRG-7 pull request so it is not mistaken for a second picker | TRG-7, then INT-8 |

## Surfaces that are net new

| # | Surface | Why nothing exists | Ticket |
|---|---|---|---|
| B1 | Trigger state badge with reason | node status today expresses `validated`, `error`, or a URL; there is no concept of a resource that is live, paused, expired, or needs reconnecting | TRG-7 |
| B2 | `/settings/triggers` table: flow, kind, provider, connection, state, transport, last event, last error, with row actions pause, resume, test, reconnect, delete | no page lists a background resource owned by a flow | TRG-7 |
| B3 | Operator view within B2: provider filter, bulk pause and resume, visible only to `useAuthStore.isAdmin` | no settings surface exposes cross-user background resources | TRG-7 |
| B4 | Per-trigger event inspector: ledger rows with state, attempts, dedupe key, and a link to the run, plus event detail showing the **normalized** payload the API returns | nothing lists a delivery history; the raw provider payload is deliberately never fetched into the browser | TRG-7 |
| B5 | Replay action with lineage: confirm, post, and render the linked new row (`replay_of_event_id`) rather than implying the original re-ran | replay does not exist anywhere in the product | TRG-7 |
| B6 | Transport and latency-class label on a trigger ("push" versus "poll every N") | the self-managed-ingress decision makes the transport context-dependent, so hiding it would make poll latency read as a bug | TRG-7 |
| B7 | Signing-secret panel for inbound-webhook triggers: URL, secret show-once, rotate | `secretKeyModal` is the closest pattern but is bound to API keys | TRG-7 behind TRG-4 |
| B8 | Trigger policy state ("blocked by policy") surfaced read-only on the badge and the row | no policy state is rendered on a node today | TRG-8 |

## Constraints the design must record

1. **Actions are server-driven.** `TriggerRead` carries `allowed_actions` and a `reason` code; the frontend renders
   what the API allows and never re-derives permission from the trigger's state. A disabled row action shows the
   `reason` in its tooltip, from the locale catalog.
2. **Polling, not SSE.** State converges through react-query polling at the interval `GET /api/v1/config` reports
   (`trigger_polling_interval`, 5 s). There is no event stream for triggers in this release, and the Playwright
   assertion is "converges within one polling interval", not "updates instantly".
3. **The normalized payload only.** The event inspector renders what the API returns. The browser never calls a
   provider, and a thin-payload mechanism's raw notification is not exposed.
4. **One trigger per flow in wave 1.** A3's gating enforces it; the tooltip explains it rather than the drop silently
   failing.
5. **i18n and a11y are review gates.** Every string lands in all seven `src/locales/*.json` catalogs (machine
   translations for the six non-English locales, as with the `#14220` precedent), and `locale-parity.test.ts` is the
   check; every new settings route ships an axe baseline.
6. **Hiding a control is presentation, not enforcement.** B3 and B8 hide operator and policy controls in React; the
   API rejects the same actions independently.

## MVP versus defer

MVP for this release: A1 to A10, B1, B2, B4, B5, B6, B7.
Defer: B3 to a follow-up if the operator view needs more than a filter and a bulk toggle; B8 until TRG-8's policy
field exists.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| frontend owner | | | |
| release owner | Eric Hare | 2026-09-05 | #14911 |
