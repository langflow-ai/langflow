# Jira Cloud integration preview

This implementation uses Jira Cloud REST API v3 and confidential OAuth 2.0 authorization code grants. It binds every connection and request to one operator-configured Cloud site. The operator sets LANGFLOW_JIRA_CLOUD_ID to the canonical site UUID before starting the API and listener processes. Canvas fields accept project keys, an optional numeric issue-type filter, issue keys and numeric workflow IDs. They cannot select an API origin or site.

## Deployment and capability matrix

| Context | Actions | Triggers | Authentication |
| --- | --- | --- | --- |
| Hosted Langflow with Jira Cloud | Preview | Unsupported | Operator-owned confidential 3LO registration |
| Self-managed Langflow with Jira Cloud | Preview | Preview polling | Confidential 3LO registration |
| Langflow Desktop | Unsupported | Unsupported | Public-client OAuth is not implemented |
| Headless lfx | Unsupported | Unsupported | Environment tokens cannot prove the required site grant |
| Jira Data Center or Server | Unsupported | Unsupported | No tested edition-specific adapter |

Actions search a project with an optional status filter, read one issue, create one issue, update its summary and optional description, or apply an available workflow transition. Create supports a project key, issue type ID, summary and plain text description converted into Atlassian Document Format. Required custom fields, arbitrary field edits, issue deletion and attachments are outside this preview. The provider still enforces the account's Browse Projects, issue security, Create Issues, Edit Issues and Transition Issues permissions. Returned fields are restricted to the issue ID, key, summary, project, status and timestamps.

## Operator setup

Install lfx-jira with the matching Langflow runtime and configure a single distributable Atlassian 3LO application for this integration. The first PR supplies no application registration or marketplace approval. Follow Atlassian's current distribution and security requirements before offering the integration to customers. Do not collect customer API tokens or ask each end user to create a custom app.

Configure a Jira registration under LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS. Its provider is jira, profile is user, client_type is confidential, tenant is the exact LANGFLOW_JIRA_CLOUD_ID, allowed_tenants contains only that UUID and scopes are read:jira-work, write:jira-work, read:jira-user and offline_access. Use the deployment context self_managed or hosted and the appropriate registration owner. The redirect URI must end in /api/v1/connections/oauth/jira/callback. Store the client secret in operator settings. The OAuth adapter sends JSON token exchanges to auth.atlassian.com, uses audience api.atlassian.com and prompt consent, and relies on the broker's one-time state binding. It does not advertise PKCE support for Atlassian confidential clients.

Initial consent and every rotating refresh prove the selected site through accessible-resources and read the active account through the selected site's myself endpoint. Connections record the verified account and site. Access and refresh credentials stay encrypted in the connection store. Reconnect when Atlassian expires or revokes the rotating refresh grant. No provider response body or credential-bearing URL is included in action errors.

Create an owned Jira connection through the OAuth dialog and explicitly enable background use before arming a trigger. Choose a project or project-and-issue-type filter containing at most 5000 visible issues. This limit also covers distinct issue IDs retained since the baseline. Large projects require a narrower issue-type filter and remain unsupported when that filter exceeds the bound. Start the separate Langflow listener process with the same site UUID and OAuth registration. The server's installed-bundle catalog must include this bundle. Each trigger uses the same saved connection and project and has its own durable observation state.

## Delivery and recovery

A trigger scans all visible issues matching one project and an optional issue-type ID through POST /rest/api/3/search/jql. Each page contains at most 100 issues. Continuation tokens are opaque request-body values. Returned URLs are never followed. Every HTTP call uses api.atlassian.com/ex/jira followed by the exact configured Cloud site UUID.

The first complete snapshot establishes a baseline and emits no events. Created observations require a previously unseen issue whose creation timestamp is at or after that baseline time. Moving an older issue into the project or granting access to an old issue does not manufacture a creation event. Update observations require a changed updated timestamp on an already observed issue. Status observations require a different status ID on an already observed issue.

These are latest-state observations rather than a lossless Jira event history. Intermediate edits or transitions between polls can be missed. Search indexing can delay observation, and pagination does not provide snapshot isolation. Duplicate issue IDs, repeated page tokens, incomplete pages, more than fifty pages or more than 5000 distinct observed IDs fail the entire round. Deleted or inaccessible issues are retained in the small observation map so a later reappearance is not treated as creation. Deletions are not emitted. An explicit pause and re-enable starts a fresh baseline and does not replay the paused interval.

The shared runtime commits the observation map and event ledger in one transaction. A failed fetch or failed commit leaves the cursor unchanged. Stale replicas cannot overwrite a newer cursor. Source versions and the unique event ledger collapse repeated observations. The shared listener owns polling leases, backoff, non-interactive consent, connection ownership and policy checks. A rate limit raises the provider Retry-After delay. Writes are not retried after ambiguous network errors. A rejected access token permits one broker refresh and repeats credential and site checks before another request.

To recover from a snapshot limit, reduce project volume or choose another project, then pause and re-enable deliberately. This creates a new baseline and can skip changes during recovery. An unavailable workflow transition or required custom field needs operator attention to the project configuration. Pausing removes the local polling work. This implementation creates no remote subscription and therefore has no remote webhook to revoke.

## Webhook boundary

This preview registers no Jira push mechanism or verifier. Anonymous or forged Jira webhook deliveries are rejected by the shared ingress path and cannot start a flow. Current Atlassian admin webhooks support HMAC signatures, while dynamic OAuth webhooks have a different bearer authentication contract. Adding signed webhooks and their remote lifecycle is a separate transport change. Do not point an unsigned admin webhook at these triggers.

## Evidence

Synthetic contract tests cover the actual components and fixed-origin HTTP requests, initial and rotating OAuth grants, installed bundle discovery, the registered listener adapter, source and cursor atomicity, duplicate observations, foreign ownership, missing background consent, wrong identity, missing scopes, policy denial, malformed targets, pagination failures, provider outages and redacted errors. No Jira tenant or Atlassian application has been used for live acceptance. The provider remains preview until that validation and registration work is complete.

Official sources checked on October 22, 2026 include [Atlassian 3LO](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/), [enhanced issue search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/), [issue actions](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/), [webhook authentication](https://developer.atlassian.com/cloud/jira/platform/webhooks/) and [app security requirements](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/).
