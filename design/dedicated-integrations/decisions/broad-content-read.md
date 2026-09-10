# Broad content-read grants, independent of provider classification

Status: proposed
Decision ID: broad-content-read
Applies to: scope_risk_decisions and scopes[].content_read_reach in all three matrices
Owners (sign-off roles): release owner, hosted-app owner, Enterprise owner, langflow-base owner, frontend owner, product owner
Last verified: 2026-09-09 (provider documentation only; no live tenant verification)

## Context

Provider verification vocabulary does not measure access breadth. A Slack `sensitive` history scope or Graph
`non_sensitive` delegated permission can read content across conversations, mailboxes' messages, files, or
calendars. Selecting one thread or file as an action input does not narrow the OAuth grant. The existing Google
restricted-scope rule remains in force; this is an additional, provider-independent gate rule.

## Decision

Propose `accept_with_controls` for the scopes below, subject to the controls and owner signatures in this record.
The release owner has not yet accepted this new risk decision. The normal checker permits a proposed record;
`--require-accepted` blocks gate close until acceptance and all signatures are recorded. An included action with
an `avoid` or `defer` decision fails even the normal check; remove or defer the action if these controls cannot ship.

Every scope declares `content_read_reach`: `none` (no message, file, canvas, or event content read),
`selected_resources` (provider-enforced app/selection boundary), or `cross_resource` (the grant can read content
across resources independently of the node's target). Every cross-resource scope on an included or deferred
action requires a `scope_risk_decisions` entry. Optional grants count too. The source on the scope supports the
reach classification; the checker requires the field but human review must establish its truth.

| Provider / scopes | Grant and consequence | Proposed decision and action-specific controls |
|---|---|---|
| Slack `search:read` | User-token search across content visible to the connected user in one workspace; can expose private-channel and DM content, beyond a single query result | Conditional acceptance for `slack.user.search`. Before consent, explain workspace-wide search access and private/DM reach. Do not request it for send-only actions. Slack now labels this scope legacy and recommends granular Real-time Search scopes: INT-12 must document the alternative's fit before acceptance; switching API requires schema and estimate review. |
| Slack `channels:history` | Public-channel history available to the user, beyond the chosen thread | Conditional acceptance for `slack.user.read_thread`; explicitly explain the four-scope profile before consent. |
| Slack `groups:history` | History of private channels the user belongs to | Same decision; private-channel access must be named in the rationale, not hidden behind "read one thread". |
| Slack `im:history` | The user's direct-message history | Same decision; explicitly disclose direct messages. |
| Slack `mpim:history` | Group direct-message history the user can access | Same decision; explicitly disclose group direct messages. The current profile requests all four history scopes for all supported conversation types. They are not all required by a single thread request; this is a product scope choice that owners must accept. A narrower conversation-type profile requires a contract amendment before implementation. |
| Microsoft `Mail.Read` | Full content across the signed-in user's mailbox | Conditional acceptance for Outlook search with body output; explain mailbox-wide access before consent. |
| Microsoft `Calendars.Read`, `Calendars.ReadWrite` | Read access across user calendars; ReadWrite also permits changes beyond a single create operation | Conditional acceptance for Calendar list/create; disclose read and write reach even for the create action. |
| Microsoft `Files.Read` | All files in the user's OneDrive, not just the requested folder | Conditional acceptance for list/fetch with this default scope. |
| Microsoft `Files.Read.All`, `Sites.Read.All` | All files/site content the signed-in user may access | Conditional acceptance only when the action's declared conditional input activates the grant. Show the shared-library/site rationale before re-consent. |
| Google `calendar.events.readonly`, `calendar.events` | Event content across the user's calendars; the latter also permits editing | Conditional acceptance for Calendar list/create, with the read/write breadth explained before consent. |

Google `gmail.readonly` remains excluded under the accepted avoid decision. `drive.file` is
`selected_resources`: the provider restricts access to app-created or user-selected/opened files. Neither is an
exemption from the existing restricted-scope rule. Slack `canvases:write` creates/edits canvases; metadata/member
scopes do not by themselves read conversation content. `none` is not a claim of zero privacy or write risk.

## Required controls and owners

1. INT-10/11/12 bundle owners author per-action reason, executing identity, exact scope union and effective reach.
   INT-8 owns localized pre-consent presentation (B2); frontend and product owners review it. Display existing
   grants as well as newly requested grants; an already-connected account must not hide broad access.
2. INT-5 requests only scopes needed by the selected capabilities and activated conditional inputs. INT-7 enforces
   provider/capability/registration policy. A narrow node input is never represented as a narrow OAuth grant.
3. INT-4 defaults `allow_non_interactive` off. INT-8 exposes its persisted state, explanation and disable control
   on B1; B10 warns and blocks publication when the resolver would deny access. The opt-in never overrides policy
   or enables anonymous public use of a user's connection.
4. INT-8 owns reconnect/revoke and the builder's policy/tenant messages (B5/B11/B12); INT-5 normalizes provider
   errors. INT-14 validates permitted, approval-required and blocked tenant configurations before rollout.
5. No token, message body or private conversation identifier enters consent telemetry. INT-14 verifies that
   losing consent or disabling the opt-in prevents subsequent resolutions and that scope changes require consent.

## Evidence

Documentation re-read 2026-09-09:

- [Slack search scope and granular alternative](https://docs.slack.dev/reference/scopes/search.read/)
- [Slack thread endpoint](https://docs.slack.dev/reference/methods/conversations.replies/)
- Slack history scopes: [public channels](https://docs.slack.dev/reference/scopes/channels.history/),
  [private channels](https://docs.slack.dev/reference/scopes/groups.history/),
  [direct messages](https://docs.slack.dev/reference/scopes/im.history/),
  [group direct messages](https://docs.slack.dev/reference/scopes/mpim.history/)
- [Graph delegated permission reach](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Google Calendar scope reach](https://developers.google.com/workspace/calendar/api/auth)
- [Google Drive per-file authorization](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [Slack canvas write scope](https://docs.slack.dev/reference/scopes/canvases.write/)

## Re-open trigger

Re-read matrix evidence at least every 30 days while this gate is maintained and before gate close or release
validation. Re-open this decision for changed provider scope reach, a narrower supported API, new deployment
contexts, or changes to the required controls. Do not refresh dates without reading the supporting documentation.

## Sign-off

| Role | Name | Date | PR |
|---|---|---|---|
| release owner | | | |
| hosted-app owner | | | |
| Enterprise owner | | | |
| langflow-base owner | | | |
| frontend owner | | | |
| product owner | | | |
