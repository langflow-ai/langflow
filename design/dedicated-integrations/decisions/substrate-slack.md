# Substrate decision: Slack

Status: accepted
Decision ID: substrate-slack
Applies to: matrices/slack.json, all actions; identity split user vs bot
Owners (sign-off roles): lfx owner, langflow-base owner, Enterprise owner, hosted-app owner, release owner
Last verified: 2026-09-04 (amended; see "Amendment 2026-09-04")

## Context

Decides whether wave-1 Slack runs mixed (official MCP server for user-identity actions, Web API for bot actions) or
Web API throughout, and how Slack's PKCE rule constrains Desktop. The governing plan requires the discovery gate to
freeze the MCP source and version plus an explicit action-to-tool mapping before implementation. The provider docs
name capabilities but not the exact tool identifiers or schemas for the four candidate user actions, and this gate
has no authenticated, dated `tools/list` capture. That evidence boundary blocks MCP—not the Slack actions—from 1.13.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | Slack MCP server at `https://mcp.slack.com/mcp`, JSON-RPC 2.0 over Streamable HTTP; "Slack supports confidential OAuth for MCP clients"; user tokens | https://docs.slack.dev/ai/slack-mcp-server/ | 2026-09-01 | high |
| 2 | "Only directory-published apps or internal apps may use MCP"; workspace admins approve and manage MCP client integrations | same | 2026-09-01 | high |
| 3 | GA: Slack's blog of 2026-02-17 announces 'the general availability of Slack's Real-Time Search (RTS) API and Model Context Protocol (MCP) server', with a companion developer changelog entry the same day; the server docs page itself carries no availability label | https://slack.com/blog/news/mcp-real-time-search-api-now-available and https://docs.slack.dev/changelog/2026/02/17/slack-mcp/ | 2026-09-01 | high |
| 4 | Bot tokens are not issued through the MCP server; bot and channel actions need the Web API | same | 2026-09-01 | high |
| 5 | "Desktop redirects are not allowed to request bot scopes"; PKCE with S256; custom URI schemes and PKCE-opted localhost count as desktop | https://docs.slack.dev/authentication/using-pkce/ | 2026-09-01 | high |
| 6 | Since 2025-05-29 commercially distributed non-Marketplace apps get 1 request per minute with a 15-message cap on conversations.replies (and conversations.history) | https://docs.slack.dev/reference/methods/conversations.replies | 2026-09-01 | high |
| 8 | The server docs enumerate capabilities (search messages and files; read channel history and send messages; create, update, read canvases; fetch user info; list channel members; upload files via `slack_get_file_upload_url` and `slack_complete_file_upload`; lists) and the granular search scopes `search:read.public`, `.private`, `.mpim`, `.im`, but name tool identifiers only for file upload | https://docs.slack.dev/ai/slack-mcp-server/ | 2026-09-01 | high |
| 7 | Web API methods for every wave-1 action are GA with published tiers (search.messages Tier 2 user-token only; chat.postMessage special ~1 per second per channel; reactions.add Tier 3; conversations.members Tier 4; canvases.create Tier 2) | method pages under https://docs.slack.dev/reference/methods/ | 2026-09-01 | high |
| 9 | The MCP server page says "Slack supports confidential OAuth for MCP clients" using the app's `client_id` and `client_secret`, then adds a "Consider using PKCE" callout: "Looking to use desktop clients? PKCE support is now available!"; MCP clients must be backed by a registered Slack app with a fixed app ID; Dynamic Client Registration is not supported; user-token endpoints are `https://slack.com/oauth/v2_user/authorize` and `oauth.v2.user.access`. The PKCE page says enabling PKCE marks the app as a public client and is one-way | https://docs.slack.dev/ai/slack-mcp-server/ and https://docs.slack.dev/authentication/using-pkce/ | 2026-09-01 | high |

## Options

### Option A: Mixed, MCP for user-identity actions and Web API for bot actions

Pros: exercises the strategic substrate where it is closest to production; user-identity reads on MCP are not
subject to the non-Marketplace Web API reduction (fact 6); Slack maintains the tool schemas.
Cons: two auth and error paths in one bundle; requires INT-9 pinned mode (3 engineer-weeks, delivered in 1.13 by the
2026-09-04 amendment below); the hosted
Langflow-owned app must be directory-published (fact 2), which is a Slack review with its own lead time; GA is now cited (fact 3); tool identifiers for the four user actions are not in the docs (fact 8).
Cost: INT-9 plus the Marketplace listing lead time for hosted.

### Option B: Web API throughout (selected for 1.13)

Pros: one provider API substrate, one OAuth install exchange carrying `scope` and `user_scope`, one error
normalizer, no INT-9 in 1.13; every method is GA (fact 7).
Cons: the hosted app still needs Marketplace approval or read actions fall to 1 request per minute (fact 6); the
strategic substrate is not exercised in 1.13 and the GA-swap procedure has no live example.
Cost: none beyond INT-12; INT-9 deferred to 1.14 with no sample action.

### Option C: MCP only

Drops every bot action (fact 4) and the Desktop bot limitation becomes moot, but the plan's hosted and self-managed
bot use cases (post as app, react, list members) disappear from wave 1. Not recommended.

## Decision

Option B for 1.13. Every `slack.user.*` and `slack.bot.*` action runs on the documented Slack Web API. User actions
use a user-token authorization-code profile; bot actions use the workspace-install bot-token profile and remain
unavailable on Desktop (fact 5). Hosted and self-managed registrations are confidential clients; Desktop user
actions use a Langflow-owned, PKCE-enabled public client with loopback redirect (a second Slack app, with a
customer-owned registration as the override; `decisions/desktop-oauth-ownership.md`); headless credentials are
externally provisioned. `substrate_decision.chosen` in `matrices/slack.json` is `["rest"]`.

The strategic MCP path is deferred to the 1.14 planning gate. It may replace a REST action only after a dated
`tools/list` capture records the server URL/version, exact tool identifier, input schema, output schema, and
authorization exchange for that action. A future adoption changes this decision and the matrix before component
implementation; INT-9 is not a post-gate discovery task for 1.13.

## Amendment 2026-09-04 (release owner decision)

**The Slack substrate decision is unchanged. What changed is INT-9's release, not Slack's substrate.**

The release owner decided on 2026-09-04 that INT-9 ships in 1.13 as a *provider-neutral* capability: the pinned
action-to-tool engine in `lfx.base.mcp.pinned` / `MCPPresetComponent`, the `IntegrationCapability.mcp_pin` manifest
field, the typed `incompatible-tool` error, and the written GA-swap procedure (`../ga-swap-procedure.md`). None of
that moves a Slack action off the Web API.

Consequently:

- `matrices/slack.json` `substrate_decision.chosen` remains `["rest"]` and all seven `slack.user.*` / `slack.bot.*`
  actions remain `substrate: "rest"`. INT-12 is unaffected and still has no MCP implementation dependency.
- The re-open trigger below is unchanged and still binding: no Slack action moves to MCP without a dated
  authenticated `tools/list` capture under `evidence/`. That capture does not exist as of this amendment.
- Because no capture exists, the GA-swap procedure is exercised on a sample action of a fictional provider against a
  recorded fixture that is labeled synthetic inside the file
  (`src/lfx/tests/unit/base/mcp/fixtures/slack-mcp-tools-list.synthetic.json`, exercised by
  `src/lfx/tests/unit/base/mcp/test_ga_swap_procedure.py`). The fixture is Slack-*shaped* and is deliberately NOT
  stored under `evidence/`: it is not evidence, its tool identifiers and schemas are invented, and it may not be
  cited as a fact in this record.
- `../ga-swap-procedure.md` names the exact files an `lfx-slack` adoption would touch once the capture exists, and
  the two Slack-specific questions the capture must answer (whether the MCP server accepts INT-5's
  `oauth.v2.user.access` user token as a Bearer; whether the pinned tool schemas map onto INT-12's REST-shaped
  inputs without changing a flow-facing field name).

## Consequences

- INT-9's engine and GA-swap procedure ship in 1.13 (amendment 2026-09-04); the Slack MCP *adoption* is still
  deferred pending the capture, and INT-12 has no MCP implementation dependency in 1.13.
- The hosted Slack app still needs a Slack Marketplace listing to avoid the reduced
  `conversations.replies` rate tier; the estimate records it as calendar risk.
- Desktop hides bot actions in both options (fact 5).
- Desktop Slack user actions use a second, Langflow-owned, PKCE-enabled Slack app; because PKCE opt-in is one-way
  and marks the app public (fact 9), it cannot share a registration with the confidential-client hosted install. A
  customer-owned PKCE app remains the override (`decisions/desktop-oauth-ownership.md`). INT-5 records client type
  and owner per context through the named OAuth profiles in `connection-contract.md` section 8.

## Re-open trigger

- A dated authenticated `tools/list` capture freezes exact identifiers and schemas for candidate actions, or
- Slack documents those identifiers and schemas itself, or
- Slack changes the directory-published requirement or the MCP server's availability status.

Re-verify by: the 1.14 planning gate.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| lfx owner | | | |
| langflow-base owner | | | |
| Enterprise owner | | | |
| hosted-app owner | | | |
| release owner | Eric Hare | 2026-09-04 | #14906; amended by the release owner decision of 2026-09-04 |
