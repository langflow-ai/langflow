# Confluence Cloud integrations

This preview bundle provides six connection-backed components. Search Pages lists published pages in an approved space and accepts an exact title filter. Read Page returns a current page and its storage body. Create Page publishes a storage-format page. Update Page requires the expected current version and sends the next version once. It reports conflicts without overwriting a newer edit automatically.

On Page Created and On Page Updated observe bounded space snapshots through the authenticated REST API. The first snapshot establishes a silent baseline. Created events require an original creation timestamp after the baseline began. Moving an older page into the space or gaining access to it does not count as creation. Updated events require a higher content version for a previously observed page.

The integration category is `confluence_integrations`. The optional lfx-bundles distribution keeps its existing `confluence` category and legacy class identities. Installing both does not replace legacy components.

## Setup

Install the lfx-confluence wheel alongside Langflow and the provider runtime prerequisite in [PR 15947](https://github.com/langflow-ai/langflow/pull/15947). The full Langflow package and reviewed Enterprise profile include this bundle after release. The provider wheel includes components and capability metadata. Its server entry point resolves in langflow-base, so standalone lfx can import and discover actions but cannot run the server trigger service.

The deployment operator sets LANGFLOW_CONFLUENCE_CLOUD_ID to one lowercase site UUID and LANGFLOW_CONFLUENCE_SPACE_IDS to a comma-separated list of one to 100 approved numeric space IDs. These settings must match in the API and listener processes. Canvas inputs cannot choose another site or credential destination.

Register an operator-owned confidential Atlassian OAuth 2.0 app in the existing LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS setting. Use provider confluence, profile user, the configured Cloud ID as tenant and its only allowed tenant, and the normal callback at /api/v1/connections/oauth/confluence/callback. Request offline_access, read:confluence-user, read:page:confluence, and write:page:confluence. The operator configures the app once. End users connect their accounts and consent. Do not ask end users to supply API tokens or create individual apps.

The broker sends Atlassian's audience and consent parameters and exchanges confidential grants as JSON. It checks accessible-resources and the current Confluence account on initial authorization and every refresh. Stored account metadata binds each credential to the configured site even though Atlassian's gateway host serves many tenants. The broker encrypts tokens, rotates refresh credentials, and serializes refresh attempts. Atlassian permissions and app access rules still constrain every request.

Enable explicit background consent on a user-owned connection before enabling a trigger. The integration policy must permit the relevant capability. Keep the listener running with the same encryption key and OAuth registration as the API.

## Supported contexts

| Context | Actions | Triggers |
| --- | --- | --- |
| Hosted Langflow with operator OAuth app | Supported preview | Unsupported |
| Self-managed Langflow with operator OAuth app | Supported preview | Authenticated polling preview |
| Desktop or headless environment credentials | Unsupported | Unsupported |
| Confluence Data Center or Server | Unsupported | Unsupported |

No webhook endpoint is advertised. Unsigned deliveries are rejected. Hosted triggers require an authenticated push design and deployment that this preview does not provide. The implementation does not create or depend on an undeployed Forge or Connect app.

## Limits and recovery

One source observes up to 5000 distinct page IDs over its current baseline and at most 50 requests of 100 pages per snapshot. Pagination extracts only an opaque cursor. It rebuilds each request with the approved space and fixed current-page filters. External URLs, different site paths, duplicate pages, repeated cursors, invalid versions, and incomplete snapshots fail without advancing the durable cursor.

The listener commits normalized page observations and the next snapshot together. Concurrent stale collectors cannot advance a changed cursor. Dedupe identity includes the trigger, page and observed version. A paused source makes no further provider calls and requires no remote subscription cleanup.

These are latest-state observations. Intermediate versions, short-lived pages, deletions, restrictions, space moves, and changes missed while access is unavailable are not a complete event history. A page newly visible after the baseline is not reported as an update until another observed version change. Poll snapshots are not provider transactions, so membership changes during pagination can require a retry and cannot prove exact once-only event capture.

When access is revoked, reconnect the user account and verify site permissions and approved spaces. A 429 reports a bounded Retry-After delay. Server and network failures preserve the old snapshot for retry. If the observation bound is exceeded, narrow the space or pause and re-enable the source. Re-enabling creates a new silent baseline and intentionally loses continuity during the pause. Do not clear a cursor manually to recover individual events.

Do not retry a timed-out Create Page blindly. The remote write may have succeeded. Read or search the target first. Update Page reports a version conflict and requires a fresh read. Storage bodies remain provider content and should be treated as untrusted downstream text.

## Evidence

Provider request contracts, OAuth rotation, registered listener delivery, durable dedupe, failed cursor commits, ownership, background consent, policy and scope denials are tested locally. Built-wheel metadata and discovery are checked with the legacy category present. Real tenant authorization, live delivery, real content writes and production failover remain unverified.

The implementation follows the current [Confluence Cloud REST v2 page API](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/), [OAuth 2.0 app guide](https://developer.atlassian.com/cloud/confluence/oauth-2-3lo-apps/), and [current user API](https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-users/#api-wiki-rest-api-user-current-get). The upstream OAuth guide requires a centrally managed app rather than collecting customer tokens or asking every user to create an app.
