# GitHub

This preview bundle connects GitHub.com repositories to Langflow through a GitHub App installation. It includes eight actions and two event triggers. Every saved node stores a connection reference. Tokens and webhook signing secrets stay on the server.

## Setup

1. Install lfx-github in the same server environment as langflow-base. The extension entry point discovers the components and capability manifest. The trigger provider entry point registers the server adapter through the provider foundation.
2. Create a GitHub App and install it on the selected repositories. GitHub attributes these actions to the app. Personal access tokens, OAuth user tokens, GitHub Enterprise Server, and configurable API origins are unavailable in this preview. The client checks the installation-only API before each action so changing token types cannot silently change the executing identity.
3. Give the installation only the repository permissions needed below. Generate a short-lived installation access token scoped to those repositories. Create an owned GitHub connection using the github-installation profile through the common manual connection API. Supply access_token, its actual expires_at, and no OAuth scopes. Do not place an app private key, PAT, or installation token in a component input or graph.
4. Installation tokens expire after one hour. This bundle does not mint tokens or store app private keys. Use a host credential resolver that rotates installation tokens. With direct manual credentials, delete the expired connection, recreate it with the same name and a fresh token and expiry, then save and re-enable affected trigger flows to bind the new connection ID. A rejected token gets one lease re-resolution. If the replacement is also rejected, the error asks the owner to reconnect. Background triggers need a resolver that keeps the installation credential current for webhook setup and cleanup.
5. For triggers, enable trigger ingress and set LANGFLOW_TRIGGER_INGRESS_ORIGIN to the instance's public HTTPS origin. Add the On Issue or On Pull Request node, choose an owned connection, select one repository and event actions, enable background runs on that connection, then arm the trigger. Langflow creates a repository webhook with its own encrypted signing secret. Do not configure a second app-level webhook for the same trigger.

| Capability | GitHub repository permission |
| --- | --- |
| Get Repository | Metadata read |
| Get Issue | Issues read |
| Create or Update Issue | Issues write |
| Get Pull Request | Pull requests read |
| Create or Update Pull Request | Pull requests write |
| Create Issue Comment | Issues write |
| On Issue | Issues read and Webhooks write |
| On Pull Request | Pull requests read and Webhooks write |

GitHub App permissions are not OAuth scopes. The connection stores no claimed OAuth scopes. The manual connection validator proves App installation identity through GitHub. It does not claim to introspect the installation token's permissions. GitHub enforces the installation's actual repository selection and permissions on every API call. Langflow's existing connection policy separately enforces ownership, declared capability policy, consent, and background execution.

Create Issue Comment also accepts a pull request number because GitHub uses its issue comments API for pull request conversation comments. This component requires Issues write and does not create inline review comments. Update nodes require a title and body and send both along with open or closed state. Updating a pull request does not merge it. Creating a pull request requires an existing head branch and base branch. The bundle cannot execute code, push commits, merge pull requests, delete repositories, create reviews, manage organization settings, or grant repository access.

## Event delivery and recovery

| Deployment | Actions | Exact issue and pull request event delivery |
| --- | --- |
| Hosted or self-managed with public HTTPS ingress | Supported | Signed repository webhooks |
| Headless server with public HTTPS ingress and dispatcher | Supported | Signed repository webhooks |
| Desktop or an instance without public ingress | Supported | Unavailable with a clear arming error |

Issue events include opened, edited, closed, reopened, assigned, unassigned, labeled, and unlabeled. Pull request events also include synchronize, ready_for_review, and converted_to_draft. Other webhook event families and actions are rejected. Each node selects a subset of this supported list. Bot events are ignored by default to prevent an app action from triggering a reply loop. Enable Include Bot Events only when the flow can safely handle its own app-generated updates. Signed pings and unselected supported actions are acknowledged without starting a flow.

The verifier compares HMAC-SHA256 against the raw request bytes before parsing JSON. It checks the signed repository ID and full name against the repository captured during setup. The per-trigger secret cannot authenticate another trigger. The delivery UUID is metadata because GitHub does not sign that header. Deduplication uses the body digest so a replay with a different UUID cannot enqueue the same signed body again within the ledger retention period. GitHub does not sign a delivery timestamp, so replay protection depends on that durable ledger and its configured retention. Rotating the signing secret closes the window for payloads captured before rotation.

Pausing or deleting the trigger queues durable webhook deletion. Re-enabling waits for that cleanup to finish so an old deletion task cannot remove a replacement webhook. A missing remote hook is already cleaned up. If installation access is revoked before cleanup succeeds, remove the webhook in the repository settings or restore installation access until cleanup completes. GitHub repository webhooks do not expire, so cleanup records must remain until remote deletion succeeds. If a webhook is removed or disabled in GitHub, disarm and rearm the node to recreate or reactivate it. Repository renames require updating the node and rearming it. This preview does not continuously health-check remote hooks.

GitHub redelivery of a previously accepted payload is acknowledged by the shared ledger without another run. Failed deliveries can be redelivered from GitHub's webhook delivery view. Flow failures use the existing trigger job retry and replay controls. Webhook acknowledgement confirms durable intake, not successful flow completion. Writes and comments are not automatically retried after transport failures because GitHub might have already applied them.

## Limits and validation

Requests and responses stay pinned to https://api.github.com. User-provided URLs, continuation links, redirects, local addresses, and Enterprise hosts are never followed. TLS verification stays enabled. Each API exchange has a 25-second outer deadline and a 20-second HTTP timeout. An action verifies installation identity and then sends its request. Requests are capped at 64 KiB and responses at 2 MiB. Titles are at most 256 UTF-8 bytes, bodies at most 60,000 bytes, and webhook payloads at most 1 MiB. Oversized GitHub payloads are rejected rather than partially executed.

Rate limiting propagates a sanitized rate-limited error with Retry-After or the primary rate reset. The client does not sleep or repeat a write on 429 or a provider outage. Provider bodies, access tokens, webhook secrets, and sensitive HTTP transport logs are excluded from errors. Setup scans at most 1,000 repository hooks and reconciles a prior timed-out creation by the exact opaque callback URL before creating another hook.

The automated contract tests use the real HTTP client with a deterministic HTTPX transport and actual credential leases. Real-tenant installation, hosted ingress, and end-to-end GitHub webhook delivery remain unverified. GitHub Enterprise has no supported path in this bundle.

## Provider references

- [Installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)
- [Repository webhook API](https://docs.github.com/en/rest/repos/webhooks)
- [Webhook signature validation](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [Event payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
- [Issues API](https://docs.github.com/en/rest/issues/issues)
- [Pull requests API](https://docs.github.com/en/rest/pulls/pulls)
- [API best practices and rate limiting](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)
