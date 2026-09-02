# Substrate decision: Slack

Status: accepted
Decision ID: substrate-slack
Applies to: matrices/slack.json, all actions; identity split user vs bot
Owners (sign-off roles): lfx owner, langflow-base owner, Enterprise owner, hosted-app owner, release owner
Last verified: 2026-09-01

## Context

Decides whether wave-1 Slack runs mixed (official MCP server for user-identity actions, Web API for bot actions) or
Web API throughout, and how Slack's PKCE rule constrains Desktop. Blocks INT-9 and INT-12. This is the one provider
where the strategic MCP substrate is plausibly production-ready today, so it is also the decision that determines
whether INT-9 (pinned MCP mode) is built in 1.13 at all.

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

## Options

### Option A: Mixed, MCP for user-identity actions and Web API for bot actions (recommended, conditional)

Pros: exercises the strategic substrate where it is closest to production; user-identity reads on MCP are not
subject to the non-Marketplace Web API reduction (fact 6); Slack maintains the tool schemas.
Cons: two auth and error paths in one bundle; requires INT-9 pinned mode (3 engineer-weeks) in 1.13; the hosted
Langflow-owned app must be directory-published (fact 2), which is a Slack review with its own lead time; GA is now cited (fact 3); tool identifiers for the four user actions are not in the docs (fact 8).
Cost: INT-9 plus the Marketplace listing lead time for hosted.

### Option B: Web API throughout

Pros: one auth path (OAuth v2 with `scope` and `user_scope` in a single install), one error normalizer, no INT-9 in
1.13; every method is GA (fact 7).
Cons: the hosted app still needs Marketplace approval or read actions fall to 1 request per minute (fact 6); the
strategic substrate is not exercised in 1.13 and the GA-swap procedure has no live example.
Cost: none beyond INT-12; INT-9 deferred to 1.14 with no sample action.

### Option C: MCP only

Drops every bot action (fact 4) and the Desktop bot limitation becomes moot, but the plan's hosted and self-managed
bot use cases (post as app, react, list members) disappear from wave 1. Not recommended.

## Decision

Option A, confirmed by the release owner on 2026-09-01 with the identifier capture as INT-9's first task. User-identity actions (`slack.user.*`) run on the official Slack MCP server in pinned mode;
bot actions (`slack.bot.*`) run on the Web API with a bot token from the workspace installation. Desktop exposes
user-identity actions only. `substrate_decision.chosen` in `matrices/slack.json` is `["mcp", "rest"]`.

Condition status on 2026-09-01: (1) GA is cited (fact 3): met. (2) Tool names: the docs confirm that every wave-1
user action is a documented server capability (search, read thread via channel history, send message, canvas) but
enumerate identifiers only for the file-upload tools (fact 8). The exact identifiers and argument schemas can only
come from a dated `tools/list` capture, which the gate's docs-only rule admits as supplementary evidence, never as
the sole source. Resolution accepted by the release owner on 2026-09-01: the identifier capture is the first task of INT-9, keeping the fallback that if the capture shows any of the four actions is not covered, that
action moves to the Web API and, if none are covered, INT-9 defers to 1.14 and Slack runs Web API throughout.

## Consequences

- INT-9 stays in 1.13 (3 engineer-weeks) and INT-12 depends on it.
- The hosted Slack app needs a Slack Marketplace listing in either option; the estimate records it as calendar risk.
- Desktop hides bot actions in both options (fact 5).

## Re-open trigger

- Slack documents bot-token support on the MCP server, or
- Slack labels the MCP server preview or deprecated, or
- Slack changes the directory-published requirement.

Re-verify by: the 1.14 planning gate.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| lfx owner | | | |
| langflow-base owner | | | |
| Enterprise owner | | | |
