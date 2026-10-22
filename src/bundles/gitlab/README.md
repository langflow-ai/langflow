# GitLab integrations

This preview bundle adds nine actions and two project webhook triggers. Actions read projects and read, create, update, and comment on issues and merge requests. Triggers filter issue and merge request events by project ID and selected action.

Update actions send only supplied changes. Leaving Title or Description blank preserves the existing field, so closing or reopening an item does not require restating its title or description. Supply at least one new value or state change. Clearing an existing description is outside this preview.

## Setup

Install the bundle with the matching Langflow release and provider runtime. The deployment operator configures LANGFLOW_GITLAB_ORIGIN before startup. It defaults to https://gitlab.com. Self-Managed instances need one public HTTPS DNS origin without a path prefix or custom port. Redirects and private network destinations are rejected. Changing this origin requires restoring it for old webhook cleanup before replacing connections.

Create a personal access token with the actual GitLab api scope. Add a GitLab connection through the connection catalog and choose API token. Langflow checks the token's self endpoint and current user. It records the verified user, instance, scope, and provider expiration instead of trusting entered identity claims. Project and group access tokens, OAuth, deploy tokens, job tokens, and granular tokens without api are unavailable in this preview.

Actions run as the token owner. GitLab still enforces project membership and endpoint permissions. Trigger setup requires Maintainer or Owner access to create project webhooks. Allow background execution on the connection and add the trigger to a saved flow. Set the numeric project ID and event actions. Configure Langflow public HTTPS trigger ingress and enable the trigger. GitLab 19.1 or newer is required for HMAC signing tokens. Langflow checks the server version before webhook creation.

## Delivery and recovery

Each trigger owns a separate project webhook. The receiver verifies Standard Webhooks HMAC-SHA256 over the message ID, timestamp, and raw body. It checks timestamp freshness, the stored project ID, payload event type, and selected actions. Secret-header-only deliveries are rejected. Project and target project IDs must match for merge requests. Confidential issue events are excluded.

Events by the connection owner and actors marked as bots are filtered by default. Keep both filters enabled when a flow writes back to GitLab. These filters cannot identify every automation account. GitLab payloads may omit bot metadata, so operator review still matters for loop prevention.

The durable event ledger deduplicates identical JSON event bodies even if delivery headers or whitespace change. Semantically different payloads remain separate events. A provider retry outside the configured timestamp window is rejected. GitLab delivery history is finite, and this preview has no polling backfill or exactly-once guarantee. Provider failures can require webhook reactivation and manual redelivery after fixing the cause.

Enable first commits a pending callback reservation before provider creation. The reservation records the exact project, connection, account, callback, and a separate HMAC ownership marker. It contains no access token or signing key. Setup scans up to 1,000 project hooks using numeric pagination. It never follows provider continuation URLs. A timed-out create is recovered by its exact per-trigger callback URL and HMAC ownership marker and updated with the same derived signing key. Successful setup promotes the original reservation to the returned hook ID. A lost create response still leaves a durable cleanup target. Multiple matching hooks fail closed. A repeated enable reuses the completed subscription. Pause or delete queues durable remote cleanup. Cleanup reads the recorded hook and checks its callback and ownership marker before deleting it. If the hook ID was lost, cleanup scans only the original project and deletes only exact callback and marker matches. It proves the original GitLab user before cleanup and waits while an activation lease is held. Owner deletion uses the existing sealed access token with its bounded deadline. Deleted hooks are treated as already cleaned up. Changed callbacks require administrator cleanup. Re-enable waits for all previous cleanup for that trigger to finish, so an old cleanup task cannot delete its replacement.

Personal access tokens are not refreshed automatically. Replace the connection before provider expiration, then save and re-enable affected flows. Do not revoke the old credential before its pending webhook cleanup finishes. A 401 stops the request without replaying writes. Rate limits and provider errors use fixed credential-free errors. Requests are limited to 64 KiB and responses to 2 MiB. Actions do not retry writes because a lost response may follow a successful mutation.

## Deployment support

| Context | Actions | Triggers |
| --- | --- | --- |
| Hosted Langflow | Verified stored connection | Public HTTPS ingress and background consent |
| Self-Managed Langflow | Verified stored connection | Public HTTPS ingress and background consent |
| Desktop | Verified stored connection | Unavailable |
| Headless service | Host resolver with verified account, instance, scope, expiry, and user identity | Langflow server runtime with public HTTPS ingress |
| Bare environment token | Unavailable because it lacks verified account metadata | Unavailable |

GitLab.com and public Self-Managed GitLab 19.1 or newer use the same API v4 contract. GitLab Dedicated and custom network topologies have not been validated. Private-only instances, path-prefix installations, and custom ports are outside this preview. No live GitLab tenant delivery or deployment acceptance has been verified.

## Primary references

The implementation was checked against GitLab documentation on October 22, 2026.

[Signed webhooks](https://docs.gitlab.com/user/project/integrations/webhooks/) explains Standard Webhooks signatures and signing token availability. [Project webhook API](https://docs.gitlab.com/api/project_webhooks/) defines signing_token, setup, pagination, and deletion. [Webhook event payloads](https://docs.gitlab.com/user/project/integrations/webhook_events/) defines issue and merge request actions. [Personal token API](https://docs.gitlab.com/api/personal_access_tokens/) defines self introspection and token expiration. The [projects](https://docs.gitlab.com/api/projects/), [issues](https://docs.gitlab.com/api/issues/), [merge requests](https://docs.gitlab.com/api/merge_requests/), and [notes](https://docs.gitlab.com/api/notes/) APIs define the action requests.
