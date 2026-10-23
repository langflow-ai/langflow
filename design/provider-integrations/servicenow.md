# ServiceNow integration

The first ServiceNow bundle provides four Table API actions and two polling triggers. It is a preview. Contract tests use the actual components and adapters against synthetic HTTP responses. No live ServiceNow tenant has been accepted.

## Supported surface

| Surface | First PR support |
| --- | --- |
| ServiceNow instance | One operator-configured HTTPS instance under service-now.com |
| API | Table API v1 on incident, problem, and change_request tables |
| Actions | Exact-filter search, read by sys_id, create, and PATCH approved fields |
| Creation trigger | New records with provider creation times after the activation watermark |
| Status trigger | Changes between observed numeric state values, with at most 10000 tracked records |
| Langflow hosted | Confidential OAuth actions only |
| Langflow self-managed | Confidential OAuth actions and polling with a dedicated trigger listener |
| Desktop and headless | Unsupported in this first PR |
| Private ServiceNow hosts and custom domains | Unsupported in this first PR |
| Webhooks, deletion events, and audit-log replay | Unsupported in this first PR |

The transport follows the documented authorization-code and Table API contracts for the current ServiceNow platform. The target tenant must expose Table API v1 in its REST API Explorer. Edition licensing, installed plugins, custom state choices, field ACLs, and business rules require tenant acceptance. No release or edition is marked GA from mocked tests.

## Setup

Set LANGFLOW_SERVICENOW_ORIGIN to an exact origin such as https://acme.service-now.com on every API, listener, and worker process. Set LANGFLOW_SERVICENOW_TABLES to a comma-separated subset of incident, problem, and change_request. It defaults to incident. Restart all processes after changing either setting. Canvas inputs cannot select a credential host or another table.

Create a customer-owned confidential authorization-code application in ServiceNow. Register the exact Langflow callback at /api/v1/connections/oauth/servicenow/callback. Enable S256 PKCE and refresh tokens. Configure the same registration through LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS on all Langflow processes. Use provider servicenow, profile user, the configured origin as tenant and allowed_tenants, and the proper deployment context. Langflow retains state, PKCE, encrypted credentials, and locked refresh through its shared OAuth broker.

Create the custom authentication scope langflow_table_read and map it to Table API v1 GET. Create langflow_table_write only when writes are needed and map it to POST and PATCH. These are administrator-created ServiceNow scopes. They are not built-in roles or global Table API permissions. Link each scope to the OAuth entity and request only the needed scopes. Do not use the broad useraccount scope. ServiceNow table and field ACLs still enforce access separately. The connected user needs read access to the selected ticket table and returned fields. Write access should cover only the approved writable fields. Do not use an administrator account as a shortcut.

The connection account label names the issuing instance. The token response does not establish the remote user's name or identifier. Langflow connection ownership still identifies the flow owner. The API client checks the executing identity, granted scope, and exact issuing instance before every request and after refresh. Manual token creation is unsupported.

Search accepts a single exact number, state, or assigned_to filter. Supply the last returned sys_id as After Record ID for another bounded page. No encoded query, script, dot-walk, field expression, continuation URL, or host is accepted from the canvas. Create and update accept short_description, description, state, impact, urgency, assigned_to, and assignment_group. Reference values must be sys_ids. State values use the tenant's numeric choices. Read output contains only the declared ticket fields. Attachments, journal fields, arbitrary tables, and deletes are outside this PR.

## Polling and recovery

Save the flow, select an owned connection, enable Allow background runs, and enable the trigger. Run the ordinary Langflow trigger listener with the same database, encryption key, bundle, and OAuth configuration as the API. Shared leases select one active worker per connection. Shared policy and consent checks run again when resolving background credentials. Hosted polling is unavailable.

Creation activation stores a start watermark without reading historical tickets. The collector uses a five-second settling delay and a two-minute overlapping window. Each complete window uses sys_id keyset pagination with fixed timestamp bounds. Overlap collapses through the durable source identity. A full round and its watermark commit together. A failed HTTP page, malformed record, missing count header on an empty page, stale cursor, changed configuration, or rolled-back transaction cannot advance the watermark. A round is limited to 100 pages of 100 records. Exceeding that bound requires reducing tenant volume or implementing another transport rather than discarding records.

The status trigger first records a baseline without firing old tickets. It compares each later observed state with that durable baseline. New records establish their first state without firing a status event. The cursor tracks at most 10000 record states. State changes carry sys_updated_on and sys_mod_count in their delivery identity, so a later return to an earlier state has a distinct event. Records are not removed from that state map automatically. Crossing the limit stops advancement and requires a narrower integration or a future durable change-feed implementation.

This is latest-state polling. Several transitions between polls can collapse into one observation. A record created and deleted before collection can be missed. Backdated system fields, clock skew beyond the overlap, tenant restores, and ACL changes are not a lossless replay source. Synchronize host clocks. A clock behind the saved watermark waits without moving it backward. Validate the provider's UTC system timestamps and ACL behavior during acceptance.

ServiceNow applies its page limit before ACL filtering. The collector continues after short pages and requires X-Total-Count to prove an empty page is exhausted. An empty page with remaining matches fails before committing. Configure a read boundary that can enumerate its selected table. Do not silently accept a partially hidden table as complete. Search actions expose bounded pages and make no completeness promise under row ACLs.

Pausing stops local polling. There is no remote subscription to delete. Resuming retains the previous watermark and observes the latest accessible state across the pause. Rebinding the connection or changing the table resets collection. Revoking background consent or the connection stops resolution before provider access. Removing the bundle prevents activation and polling. Delete the connection locally and revoke its OAuth grant in ServiceNow when retiring it. Langflow does not claim remote grant revocation for this provider.

HTTP 429 preserves the cursor and exposes a bounded retry delay. Network and server errors expose no provider response text or credential values. A confirmed 401 permits one broker refresh and retries once. Ambiguous create/update timeouts are not retried automatically because the provider might already have applied the write. Inspect the ticket before rerunning a failed write. Tenant rate limits and business-rule side effects need live validation.

## Acceptance still required

Validate authorization, refresh, custom scope enforcement, record and field ACLs, creation pagination, multiple status transitions, a listener restart, pause/resume, rate limits, and write side effects in a nonproduction tenant. Repeat with the actual tenant release and enabled plugins. Fixtures do not prove those external gates.

## Provider references

[Table API](https://www.servicenow.com/docs/r/api-reference/rest-apis/c_TableAPI.html) documents versioned paths, exact query grammar, ordering, pagination, ACL filtering, and X-Total-Count. [Authorization workflow](https://www.servicenow.com/docs/r/platform-security/authentication/authorization-workflow.html) documents the authorization and token endpoints with PKCE. [REST API Auth Scope](https://www.servicenow.com/docs/r/platform-security/authentication/rest-api-auth-scope.html) and [scope configuration](https://www.servicenow.com/docs/r/platform-security/authentication/configure-rest-api-auth-scope.html) describe administrator-defined scopes and their mapping to API methods.
