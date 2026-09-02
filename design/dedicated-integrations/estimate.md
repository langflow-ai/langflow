# Re-issued estimate for INT-1 through INT-14

Status: re-issued 2026-09-01 under the release owner's confirmed decisions
Owners (sign-off roles): release owner
Last verified: 2026-09-01

The gate's last exit criterion is a re-issued estimate. The original ticket breakdown summed to 49
engineer-weeks including INT-1. The numbers below apply the gate's findings ticket by ticket; every delta names the
decision or fact that caused it. Assumptions: one engineer per stream; INT-10, INT-11, INT-12 run in parallel once
INT-3 and INT-5 land; the proposed decisions in `decisions/` hold (Google sdk, Microsoft rest, Slack mixed, hosted
Google app avoids restricted scopes, KB connectors adopt the contract in 1.13 per the release owner's 2026-09-01 decision).

## Per ticket

| Ticket | Original | Re-issued | Delta | Why |
|---|---|---|---|---|
| INT-1 Discovery gate | 3 | 3 | 0 | as sized; this PR |
| INT-2 lfx connection contract | 3 | 3.5 | +0.5 | `ExecutionPrincipal` type and the `connection_resolution` matrix dimension are more than the ticket text; the single env resolver is less (`connection-contract.md` sections 3 to 5) |
| INT-3 Manifest `integrations` field | 1.5 | 1.5 | 0 | as designed; capability ids are the matrices' `action_id`s |
| INT-4 Connection entity and API | 4 | 4.5 | +0.5 | per-connection `allow_non_interactive` flag, connection as a share resource type, `required_connections` in the artifact builder, HKDF envelope (contract section 12.b) |
| INT-5 OAuth broker | 4 | 5 | +1 | two registration modes (customer-owned default, Langflow-owned hosted) times three providers; Desktop loopback; cross-worker single-flight refresh; Microsoft rotating refresh tokens and Slack optional rotation are two refresh behaviors |
| INT-6 Executing identity | 3 | 3 | 0 | the allow/deny table is already written per family in the contract |
| INT-7 Governance | 3 | 3 | 0 | mirrors the model-provider policy pattern as planned |
| INT-8 Frontend Connections UX | 5 | 6 | +1 | OAuth return handling (popup plus `postMessage` or callback route) is greenfield; scope-coverage picker; a11y baseline spec; i18n in seven locales (`frontend-surfaces.md` B3, B5, A14) |
| INT-9 MCP pinned mode | 3 | 3 | 0 | Slack is mixed; day one is a dated tools/list capture against mcp.slack.com to pin the four user-action identifiers (`decisions/substrate-slack.md`) |
| INT-10 lfx-google wave 1 | 5 | 4.75 | -0.25 | include set shrinks to five SDK actions with no restricted scope and no MCP (-1); the `GoogleOAuthToken` deprecation and upgrade-checker rule remain; KB Drive ingestion source on connections (+0.75, `decisions/kb-oauth-connector-adoption.md`) |
| INT-11 lfx-microsoft | 5 | 5.75 | +0.75 | eight Graph actions, a new bundle's eight registration points, the Entra guide; KB OneDrive, SharePoint, and Graph ingestion sources on connections plus the KB connector picker (`decisions/kb-oauth-connector-adoption.md`) |
| INT-12 lfx-slack | 4 | 4 | 0 | mixed: pinned MCP for four user actions plus Web API for three bot actions; 3 if Web API throughout |
| INT-13 Headless reference | 1.5 | 1.5 | 0 | the env resolver is the sample |
| INT-14 GA validation | 4 | 4 | 0 | contexts reduce to two callback paths times two client types, offset by three providers' verification runbooks |
| **Total** | **49** | **52.5** | **+3.5** | inside the plan's 45 to 55 working range |

Sensitivity: Slack Web API throughout removes INT-9 (3) and one week from INT-12, for a total of 48.5. Accepting CASA
instead of avoiding restricted scopes adds no engineer-weeks to INT-10 but adds several weeks of calendar lead time
and an annual recurring assessment that no ticket currently carries.

## External lead times (calendar risk, not engineer-weeks)

| Dependency | Context | Lead time | Source |
|---|---|---|---|
| Google brand verification | hosted | typically 2 to 3 business days | `matrices/google.json` sources `google-restricted-scope-verification` |
| Google sensitive-scope verification (`gmail.send`, Calendar scopes) | hosted | typically 3 to 5 business days | `google-sensitive-scope-verification` |
| Google CASA | hosted, only if the restricted-scope decision flips to accept | several weeks, then annual | `google-restricted-scope-verification` |
| Microsoft publisher verification | hosted | minutes once a verified Cloud Partner Program account exists; obtaining and verifying that account is the real lead time | `matrices/microsoft.json` source `entra-publisher-verification` |
| Slack Marketplace (directory) listing | hosted, required for MCP use and to lift the non-Marketplace rate reduction | Slack review; weeks, not documented | `matrices/slack.json` sources `slack-mcp-server`, `slack-rate-limits` |
| Slack MCP tool identifiers | all | INT-9 day one tools/list capture; an uncovered action moves to the Web API | `decisions/substrate-slack.md` |

## What the estimate does not include

Triggers and webhooks (`triggers-deferred.md`); OAuth for unauthenticated public-flow callers; a self-managed restricted-scope profile
(`decisions/google-restricted-scopes.md` Option C); Enterprise approvals, retention, and audit query UI beyond the
existing plugin seams.
