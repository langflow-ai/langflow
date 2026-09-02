# Substrate decision: Microsoft 365 and Teams

Status: accepted
Decision ID: substrate-microsoft
Applies to: matrices/microsoft.json, all actions
Owners (sign-off roles): lfx owner, langflow-base owner, Enterprise owner, hosted-app owner, release owner
Last verified: 2026-09-01

## Context

Decides which substrate the eight wave-1 Microsoft actions run on. Blocks INT-11.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | Work IQ MCP: "This is a preview feature. Preview features aren't meant for production use" | https://learn.microsoft.com/en-us/microsoft-agent-365/tooling-servers-overview | 2026-09-01 | high |
| 2 | "You must have a Microsoft 365 Copilot license to use Work IQ MCP servers" | same | 2026-09-01 | high |
| 3 | Work IQ servers are tenant-scoped (`https://agent365.svc.cloud.microsoft/agents/tenants/{tenantId}/servers/mcp_MailTools`), reached through a customer enterprise app holding `WorkIQ-*` permissions, and governed in the Microsoft 365 admin center | same | 2026-09-01 | high |
| 4 | Microsoft Graph v1.0 REST covers every wave-1 action with delegated permissions that require no admin consent | https://learn.microsoft.com/en-us/graph/permissions-reference | 2026-09-01 | high |
| 5 | Graph publishes per-service throttling limits (Outlook 10,000 requests per 10 minutes per mailbox; Teams 1 request per second per chat or channel) | https://learn.microsoft.com/en-us/graph/throttling-limits | 2026-09-01 | high |

## Options

### Option A: Work IQ MCP servers

Pros: Microsoft-maintained tool schemas; admin-center governance.
Cons: preview and "not meant for production use" (fact 1); smuggles a per-tenant Microsoft 365 Copilot license into
a Langflow feature (fact 2); tenant-scoped endpoints and a customer-registered enterprise app make a Langflow-owned
hosted app impossible (fact 3). Cost: blocks INT-11 on an unknown GA date and on customer licensing.

### Option B: Microsoft Graph REST with delegated permissions (recommended)

Pros: GA, no admin consent for any wave-1 permission (fact 4), published throttling (fact 5), one auth path for
hosted, self-managed, and Desktop; the msgraph-sdk-python or plain httpx suffices.
Cons: Langflow maintains eight thin adapters. Cost: inside the INT-11 estimate.

### Option C: Mixed

No wave-1 action benefits from MCP while facts 1 to 3 hold.

## Decision

Wave-1 Microsoft actions run on Microsoft Graph v1.0 REST with delegated permissions. Application permissions are
excluded. Work IQ MCP is not adopted in 1.13. `substrate_decision.chosen` in `matrices/microsoft.json` is `["rest"]`.

## Consequences

- INT-11 depends on INT-3 and INT-5 only; INT-9 is not on the Microsoft path.
- The hosted app's external dependency is publisher verification, not a Copilot license.

## Re-open trigger

- Work IQ MCP reaches GA and the Copilot-license requirement is dropped or judged acceptable for target customers, or
- Microsoft publishes a Graph-permission-based (non-tenant-scoped) MCP endpoint.

Re-verify by: the 1.14 planning gate.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| lfx owner | | | |
| langflow-base owner | | | |
| Enterprise owner | | | |
