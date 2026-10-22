# Salesforce records

This preview bundle provides one record change trigger and three record actions. It uses Salesforce REST API v66.0. The trigger polls added or changed record IDs through the replication API, then retrieves each record's latest visible state. It does not preserve every intermediate edit, distinguish a creation from an update, or report deletions. Records deleted or hidden before retrieval have no payload.

## Supported surface

| Object | Writable scalar fields |
| --- | --- |
| Account | Name, Description, Phone, Website, Industry |
| Contact | FirstName, LastName, Email, Phone, Title, AccountId |
| Lead | FirstName, LastName, Company, Email, Phone, Status |
| Opportunity | Name, StageName, CloseDate, Amount, AccountId |
| Case | Subject, Description, Status, Priority, Origin, ContactId |

Read Record retrieves one record by its 15 or 18 character ID. Create Record creates one record. Update Record updates one explicit record. All three use these object and field allowlists. Read and trigger payloads additionally include Id, CreatedDate, LastModifiedDate, and SystemModstamp. Fields unavailable to the connected account fail before writes. Salesforce still enforces sharing, field access, picklists, required custom fields, validation rules, and object permissions. Describe metadata must mark a source object replicateable. Creating orgs with required custom fields outside this list is unsupported for those objects.

There are no arbitrary SOQL, relationship fields, custom objects, custom fields, formula fields, query filters, delete, upsert, bulk mutation, attachments, Experience Cloud site, or Salesforce Government Cloud paths. Use downstream flow conditions to filter the latest returned state. No provider URLs or credentials are accepted on the canvas.

## Authentication and deployment

An operator configures one Salesforce My Domain org for the deployment. Set LANGFLOW_SALESFORCE_ORIGIN to its exact HTTPS origin, such as https://example.my.salesforce.com or https://example--uat.sandbox.my.salesforce.com. The documented demo, develop, patch, sandbox, scratch, and trailblaze My Domain partitions are accepted. The exact configured origin still binds the connection. Configure the same origin and OAuth registrations on the API and every listener process. Restart those processes after changing the origin. A connection's account tenant metadata binds its tokens to this exact origin. Both authorization and refresh reject a different instance_url. Redirects are never followed.

Create a Salesforce external client app, or use an existing connected app. Salesforce restricts creation of new connected apps starting in Spring 2026. The app owner configures an authorization code flow, PKCE, a client secret, and the exact Langflow callback. Enable api, id, and refresh_token scopes. These are OAuth scopes. They do not grant object or field permissions by themselves. Use an API-enabled integration user with the required sharing and object permissions. Enterprise, Unlimited, Performance, and Developer editions include API access. Professional requires its API add-on. Group and Essentials are unsupported.

Register the app in LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS through the shared Connections broker. The Salesforce registration uses provider salesforce, profile user, client_type confidential, tenant equal to LANGFLOW_SALESFORCE_ORIGIN, and exactly the api, id, and refresh_token scopes. Supply the app client_id, client_secret, and redirect_uri ending in /api/v1/connections/oauth/salesforce/callback. Self-managed registrations are customer-owned. Hosted action registrations may be customer-owned or Langflow-owned under the host's existing OAuth policy. The same registration must be available on workers for refresh.

Actions support hosted and self-managed servers. Triggers support self-managed listener processes only. Hosted polling, Desktop, headless environment credentials, pasted bearer tokens, public ingress, CDC, Streaming API, and Pub/Sub API subscriptions are unsupported in this preview. Configure the shared listener service before enabling a trigger. The owner must explicitly allow background runs on the connection. A flow can reference only its owner's user connection. Integration policy can block each declared capability.

## Cursor and recovery

The initial poll establishes a baseline and suppresses those records. Subsequent polls request a maximum five minute window. Salesforce ignores seconds in replication request boundaries. The adapter rounds the lower boundary down to a minute and deduplicates repeated record states by object, record ID, and SystemModstamp through the shared durable ledger. It advances only to Salesforce's latestDateCovered after every record batch succeeds. It fetches 200 records per request, accepts at most 5000 changed IDs per round, and rejects incomplete, unrelated, or malformed batches without advancing the cursor. A source above that bound requires reduced source volume before it can resume. This is a deliberate bounded preview limitation.

The shared runtime commits the ledger and cursor together and rejects a stale replica's cursor commit. It enforces the source lease, owner, connection consent, and capability policy. No remote subscription exists, so disabling or deleting the source requires only shared local cleanup. No webhook secret or remote subscription can remain active.

Salesforce retains at most 30 days of replication history. This adapter rejects cursors older than 29 days rather than pretending to replay a gap. Disable and re-enable the source to establish a fresh baseline after such a gap. Edits during the gap and intermediate states cannot be reconstructed. If Salesforce rejects a token, the shared broker attempts one refresh. Reconnect when refresh expires or is revoked. Daily API exhaustion and HTTP 429 report a rate limit. No automatic write retry follows a timeout because a write may already have committed.

## Verification limits

Contract tests use synthetic credentials and HTTP responses. Lifecycle tests use the shared trigger runtime and database. A real external client app, tenant OAuth callback, Salesforce API request, edition-specific object permissions, token rotation, and multi-process Salesforce traffic remain unverified. This bundle must be installed before its entry points can expose the components and server adapter. The full distribution and reviewed Enterprise profile register this preview bundle. Its capability maturity remains preview.

## Provider references

The API contract was checked against current Salesforce documentation on October 22, 2026.

- [Supported editions and required permissions](https://developer.salesforce.com/docs/platform/api-rest/guide/intro-rest-compatible-editions.html)
- [External client apps, connected apps, and OAuth](https://developer.salesforce.com/docs/platform/api-rest/guide/intro-oauth-and-connected-apps.html)
- [Refresh token flow and rotation](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_refresh_token_flow.htm&language=en_US&type=5)
- [REST Get Updated and latestDateCovered](https://developer.salesforce.com/docs/platform/api-rest/guide/resources-getupdated.html)
- [Replication requirements and retention](https://developer.salesforce.com/docs/platform/api/guide/sforce-api-calls-getupdated.html)
- [sObject record actions](https://developer.salesforce.com/docs/platform/api-rest/guide/resources-sobject-retrieve.html)
- [Create records](https://developer.salesforce.com/docs/platform/api-rest/guide/resources-sobject-basic-info-post.html)
- [Salesforce warning about timestamp SOQL replication](https://help.salesforce.com/s/articleView?id=000391120&language=en_US&type=1)

- [Official My Domain partitions](https://help.salesforce.com/s/articleView?id=sf.domain_name_partitioned_domains.htm&language=en_US&type=5)
