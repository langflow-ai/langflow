# Substrate decision: Slack

Status: proposed
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
| 3 | The MCP server page carries no availability label (no preview or beta marker); GA status is asserted by Slack announcements not cited here | same | 2026-09-01 | medium |
| 4 | Bot tokens are not issued through the MCP server; bot and channel actions need the Web API | same | 2026-09-01 | high |
| 5 | "Desktop redirects are not allowed to request bot scopes"; PKCE with S256; custom URI schemes and PKCE-opted localhost count as desktop | https://docs.slack.dev/authentication/using-pkce/ | 2026-09-01 | high |
| 6 | Since 2025-05-29 commercially distributed non-Marketplace apps get 1 request per minute with a 15-message cap on conversations.replies (and conversations.history) | https://docs.slack.dev/reference/methods/conversations.replies | 2026-09-01 | high |
| 7 | Web API methods for every wave-1 action are GA with published tiers (search.messages Tier 2 user-token only; chat.postMessage special ~1 per second per channel; reactions.add Tier 3; conversations.members Tier 4; canvases.create Tier 2) | method pages under https://docs.slack.dev/reference/methods/ | 2026-09-01 | high |

## Options

### Option A: Mixed, MCP for user-identity actions and Web API for bot actions (recommended, conditional)

Pros: exercises the strategic substrate where it is closest to production; user-identity reads on MCP are not
subject to the non-Marketplace Web API reduction (fact 6); Slack maintains the tool schemas.
Cons: two auth and error paths in one bundle; requires INT-9 pinned mode (3 engineer-weeks) in 1.13; the hosted
Langflow-owned app must be directory-published (fact 2), which is a Slack review with its own lead time; GA status
needs a citable source before the substrate row can be high confidence (fact 3).
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

Proposed: Option A. User-identity actions (`slack.user.*`) run on the official Slack MCP server in pinned mode;
bot actions (`slack.bot.*`) run on the Web API with a bot token from the workspace installation. Desktop exposes
user-identity actions only. `substrate_decision.chosen` in `matrices/slack.json` is `["mcp", "rest"]`.

Condition: before the record moves to `accepted`, cite a Slack source for the MCP server's GA status and confirm the
tool names for search, thread replies, send, and canvas so the INT-9 action-to-tool mapping can be pinned. If either
cannot be confirmed by gate close, fall back to Option B and defer INT-9 to 1.14.

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
