# lfx-slack

Slack Web API actions for Langflow, backed by [connections](https://docs.langflow.org/connection-oauth).

Seven components, split by executing identity:

| Component | Capability | Identity | Slack method | Required scopes |
| --- | --- | --- | --- | --- |
| `Slack: Search (as user)` | `slack.user.search` | connected user | `search.messages` | `search:read` |
| `Slack: Read Thread (as user)` | `slack.user.read_thread` | connected user | `conversations.replies` | `channels:history`, `groups:history`, `im:history`, `mpim:history` |
| `Slack: Send Message (as user)` | `slack.user.send` | connected user | `chat.postMessage` | `chat:write` |
| `Slack: Create Canvas (as user)` | `slack.user.canvas` | connected user | `canvases.create` | `canvases:write` |
| `Slack: Post Message (as app)` | `slack.bot.post` | app bot user | `chat.postMessage` | `chat:write` |
| `Slack: Add Reaction (as app)` | `slack.bot.add_reaction` | app bot user | `reactions.add` | `reactions:write` |
| `Slack: List Channel Members (as app)` | `slack.bot.list_channel_members` | app bot user | `conversations.members` | `channels:read` (+ `groups:read`, `users:read` conditionally) |

The action set, its scopes, and the executing identity per action are frozen by
the INT-1 discovery gate in
`design/dedicated-integrations/matrices/slack.json`; `capabilities.v1.json` is
lifted from it and `scripts/ci/check_capability_manifests.py` proves the two
still agree.

## Two identities, two connections

Slack user tokens and bot tokens are different credentials with overlapping
scope names, so the bundle ships two authorization profiles:

* `slack-user-oauth` — an OAuth authorization-code grant whose `user_scope` the
  connected Slack user approves. Available in every deployment context,
  including Desktop (PKCE, loopback redirect).
* `slack-bot-install` — a workspace installation whose bot token belongs to the
  workspace, not to the installing user. **Not available on Desktop**: Slack
  desktop redirects may not request bot scopes.

A component that runs as the bot fails closed with `connection-not-authorized`
before its first request when it is handed a user token, and the reverse. It
checks two signals, and each one that is present must match the action:
`ResolvedCredential.identity`, recorded on the connection by the host, and the
token's own type prefix (`xoxb-` bot, `xoxp-` user, optionally behind the
`xoxe.` rotation marker).

Connections resolved from `LF_CONNECTION__SLACK__<NAME>` carry no recorded
identity, so the prefix is the only proof for them, and a headless token without
a recognizable prefix is refused. Slack's own `not_allowed_token_type` is not a
backstop: `chat.postMessage` accepts both token types, so a mismatched token
would post under the wrong author without an error.

Hiding the bot components on Desktop is delivered by capability discovery
filtering on `deployment_contexts` (INT-7/INT-8), not by this bundle; the
bundle only declares the contexts.

## Errors

Slack answers **HTTP 200 with `{"ok": false, "error": "..."}`**, so the bundle
registers a provider error normalizer with lfx. Without it, an expired token or
a missing scope would be reported as `provider-unavailable` and the frontend's
reconnect and grant-scopes affordances would never appear.

| Slack | lfx error |
| --- | --- |
| `invalid_auth`, `not_authed`, `token_expired`, `token_revoked`, `account_inactive` | `auth-expired` |
| `missing_scope` (with `needed`) | `scope-missing` |
| `ratelimited`, `rate_limited`, `message_limit_exceeded`, HTTP 429 | `rate-limited` (with `Retry-After`) |
| `channel_not_found`, `not_in_channel` | `invalid-request`, with a hint to check the channel ID or invite the app |
| caller-fault codes such as `invalid_name`, `invalid_blocks_format`, `no_text`, `thread_not_found`, `is_archived` | `invalid-request` |
| workspace or admin denials such as `restricted_action`, `team_access_not_granted`, `no_permission` | `connection-not-authorized` (reason `provider`) |
| `not_allowed_token_type`, `method_not_supported_for_channel_type`, `free_team_not_allowed`, … | `action-unsupported` |
| anything else | `provider-unavailable` |

Only `rate-limited` and `provider-unavailable` are retryable. The full code sets
live in `_client.py`. Slack's HTTP 200 is never copied onto the typed error, so a
run that fails this way is not reported with a success status.

An `auth-expired` rejection triggers exactly one reactive re-resolve through
`CredentialLease.get_token_after_auth_error`, which is how a rotated Slack
token is picked up: Slack tokens have no expiry unless the app opted into
rotation, so a rejection is the only signal.

## Rate limits

`conversations.replies` (Read Thread) is Tier 3 for Slack Marketplace apps but
**1 request per minute with a 15-message page** for commercially distributed
apps that are not listed in the Marketplace. `chat.postMessage` is roughly one
message per second per channel. Components make one Web API call per run (plus
one `users.info` per member when *Resolve display names* is on), and components
with two outputs memoize the response so a second output never spends a second
call.

## SSRF posture

The API root is the module constant `SLACK_API_BASE_URL`
(`https://slack.com/api/`) and no component exposes a URL, host, or proxy
input, so there is no user-controllable request target. The bundle therefore
does not use `lfx.utils.ssrf_transport`: those helpers build httpx clients with
DNS pinning, and `slack_sdk.web.async_client.AsyncWebClient` speaks aiohttp,
for which lfx ships no equivalent. Removing the surface is a stronger guarantee
than pinning DNS for a URL a flow author can set.

## Install

`lfx-slack` is part of the default `uv pip install langflow` install. Installing
`lfx` on its own:

```bash
uv pip install lfx-slack
```

## Tests

```bash
uv venv
uv pip install ./src/lfx ./src/bundles/slack pytest pytest-asyncio
.venv/bin/python -m pytest src/bundles/slack/tests -q -m "not api_key_required"
```

The opt-in live-workspace suite (`tests/test_slack_live.py`) is marked
`api_key_required` and skips unless `LANGFLOW_SLACK_LIVE_USER_TOKEN`,
`LANGFLOW_SLACK_LIVE_BOT_TOKEN`, and `LANGFLOW_SLACK_LIVE_CHANNEL` are set. It
is never run in CI.
