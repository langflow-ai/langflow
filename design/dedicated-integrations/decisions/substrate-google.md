# Substrate decision: Google Workspace

Status: accepted
Decision ID: substrate-google
Applies to: matrices/google.json, all actions
Owners (sign-off roles): lfx owner, langflow-base owner, Enterprise owner, hosted-app owner, release owner
Last verified: 2026-09-01

## Context

The plan keeps MCP as the strategic substrate but adopts a provider's official server only when it is generally
available with an identity model and scope set that fit the approved matrix. This record decides which substrate
the six wave-1 Google actions run on. It blocks INT-10 and decides whether INT-9 (pinned MCP mode) is needed for
Google in 1.13.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | The Workspace MCP servers (Gmail, Drive, Docs, Sheets, Slides, Calendar, Chat, People) are available "as part of the Google Workspace Developer Preview Program" | https://developers.google.com/workspace/guides/configure-mcp-servers | 2026-09-01 | high |
| 2 | Preview program terms: features "may not be included in public applications prior to the General Availability (GA) announcement" and end users outside the developer's own domain may not be given access before GA | https://developers.google.com/workspace/preview | 2026-09-01 | high |
| 3 | The Gmail server requests `gmail.readonly` and `gmail.compose`; the Drive server requests `drive.readonly` and `drive.file`; users bring their own Google Cloud OAuth client | https://developers.google.com/workspace/guides/configure-mcp-servers | 2026-09-01 | high |
| 4 | `gmail.readonly`, `gmail.compose`, `drive.readonly` are restricted scopes; `gmail.send` is sensitive; `drive.file` is non-sensitive | https://developers.google.com/workspace/gmail/api/auth/scopes and https://developers.google.com/workspace/drive/api/guides/api-specific-auth | 2026-09-01 | high |
| 5 | The Gmail, Drive, and Calendar REST APIs and google-api-python-client are GA with published quotas | https://developers.google.com/workspace/gmail/api/reference/quota (and Drive, Calendar quota pages) | 2026-09-01 | high |
| 6 | Restricted scopes on an app that touches data through a third-party server require a CASA assessment that "can potentially take several weeks" and 12-month reverification | https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification | 2026-09-01 | high |

## Options

### Option A: Official Workspace MCP servers for all wave-1 actions

Pros: aligns with the strategic substrate; tool schemas maintained by Google.
Cons: preview terms forbid shipping to end users outside our own domain before GA (fact 2), which rules out hosted,
self-managed, and Desktop; the Gmail server's `gmail.compose` scope raises Gmail send from sensitive to restricted
(facts 3, 4) and would force CASA on the hosted app for an action that does not otherwise need it; no published
rate limits or GA date. Cost: blocks INT-10 until an unknown GA date.

### Option B: SDK/REST for all wave-1 actions; swap to MCP per action after GA (recommended)

Pros: every substrate is GA today (fact 5); scope tiers are chosen per action, so Gmail send stays sensitive; no
dependency on the preview program; INT-9 pinned mode is not needed for Google in 1.13. The component identity and
saved-flow schema are Langflow-owned, so a later swap to the MCP server changes only the adapter.
Cons: Langflow maintains thin adapters over google-api-python-client for six methods.
Cost: inside the INT-10 estimate (5 engineer-weeks); no external lead time.

### Option C: Mixed (MCP for Calendar, SDK for Gmail and Drive)

Pros: none over B while the Calendar server is also in the preview program (fact 1).
Cons: two auth and error paths for one provider; still blocked by fact 2.

## Decision

Wave-1 Google actions run on the Google APIs SDK (google-api-python-client) with least-privilege scopes chosen per
action. The official Workspace MCP servers are not adopted in 1.13. `substrate_decision.chosen` in
`matrices/google.json` is `["sdk"]`.

## Consequences

- INT-9 pinned MCP mode is not on the Google critical path; INT-10 depends on INT-3 and INT-5 only.
- The Gmail send action stays on `gmail.send` (sensitive) and does not depend on the CASA decision.
- INT-10 documents the GA-swap procedure for one Google action so the substrate can change without touching saved flows.

## Re-open trigger

- Google announces GA of any Workspace MCP server, or
- Google publishes MCP-server scope sets that avoid restricted scopes for the actions in wave 1.

Re-verify by: the 1.14 planning gate.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| lfx owner | | | |
| langflow-base owner | | | |
| Enterprise owner | | | |
