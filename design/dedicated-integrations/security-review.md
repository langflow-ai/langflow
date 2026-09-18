# Security review: dedicated integrations connection substrate (INT-14 / LE-2472)

Status: accepted
Review ID: int-14-security-review
Applies to: the OAuth broker (`services/connection/oauth/`), the connections and integrations APIs
(`api/v1/connections.py`, `api/v1/integrations.py`), and the execution-principal identity rules
(`api/utils/execution_principal.py`, `lfx/services/connection/base.py`,
`services/connection/service.py`, `services/database/models/connection/`)
Owners (sign-off roles): langflow-base owner, lfx owner, Enterprise owner
Last verified: 2026-09-17

## Scope and methodology

GA validation review of the credential-bearing surfaces of the Dedicated Integrations (Connectors)
feature. Method: read every line of the files in scope, then check each security invariant from
`connection-contract.md` section 0 against the code, then sweep for the standard web risks
(open redirects, state replay, CSRF on the callback, timing oracles, log/telemetry leakage of
tokens or codes, authorization bypass via shares or instance connections, SQL/ORM injection, mass
assignment on PATCH). Line references were verified against `feat/int-14-ga-validation` on
2026-09-17 and re-verified at `13e1ec8ed7` after `release-1.13.0` merged in. Existing regression
coverage relied on: `test_connections.py`, `test_connection_oauth.py`,
`test_connection_resolution_families.py`, `test_integrations.py`, and
`tests/unit/services/connection/`.

## Findings

| ID | Severity | Title | Evidence | Status |
|----|----------|-------|----------|--------|
| INT-14-01 | HIGH | No rate limiting on the connections or integrations routers | `api/v1/connections.py` and `api/v1/integrations.py` had no `check_rate_limit` call; only `api/v1/login.py:43`, `api/v1/chat.py:1141-1146`, and `api/v2/workflow_public.py:86-89` used the rate-limit service | fixed |
| INT-14-02 | LOW | Health/test hold the connection row lock across a possible outbound token refresh | `services/connection/service.py:549-575`, `services/connection/oauth/broker.py:186-190`, provider timeout `providers.py:87` | open (accepted) |
| INT-14-03 | LOW | Rate-limit counters are keyed by client IP only | `services/rate_limit/service.py:128-150` | open (accepted) |
| INT-14-04 | HIGH | The login-sized limit from INT-14-01 cut off the pending-consent poll | `GET /connections` on `rate_limit_per_minute` (5) vs `usePendingConnectionPoll`'s 2000ms refetch with `retry: false` (`src/frontend/src/controllers/API/queries/connections/use-connections.ts:155-171`) | fixed |

### INT-14-01 (HIGH, fixed): no rate limiting on the connections or integrations routers

Every endpoint of both routers sat in front of credential material or outbound provider calls with
no throttle: `POST /{id}/oauth/start` mints consent state and sets the browser-binding cookie,
`GET /oauth/{provider}/callback` is unauthenticated (state replaces login) and performs a token
exchange plus a durable state-consumption write, and `POST /{id}/test` / `POST /{id}/health` can
trigger a provider token refresh. The login, public-chat, and public-workflow endpoints were
already limited; these routers were not.

Fix, mirroring `login.py`'s `check_rate_limit` idiom with per-endpoint counter namespaces:

- `api/v1/connections.py:71-76` defines the scopes; checks at `:246` (list), `:259` (create),
  `:288` (test), `:318` (health), `:353` (update), `:383` (revoke), `:404` (delete),
  `:428` (OAuth start), `:479` (registration listing), `:528` (OAuth callback) — every route the
  router exposes.
- `api/v1/integrations.py:28` defines the `integrations` scope; checks at `:113` (catalog) and
  `:191` (effective policy).
- Same config knobs as the rest of the platform: `rate_limit_enabled`, `rate_limit_per_minute`,
  `rate_limit_storage_uri`, `rate_limit_trust_proxy`
  (`src/lfx/src/lfx/services/settings/groups/security.py:334-352`), plus
  `connection_metadata_rate_limit_per_minute` for the read bucket INT-14-04 added. OAuth
  start/callback and test/health get their own buckets so a burst of provider-bound traffic cannot
  consume a client's write budget, and so unauthenticated callback spam cannot block a user's
  consent starts.
- Tests: `src/backend/tests/unit/api/v1/test_connections_rate_limit.py` (16 tests: the 429 contract
  with `Retry-After: 60` on metadata reads, every mutating route, test/health, OAuth start, the
  registration listing, the unauthenticated callback, bucket independence in both directions, the
  shared integrations bucket, the pending-consent poll at shipped defaults, and the
  disabled-setting passthrough). `test_every_connections_route_checks_the_rate_limit` walks the
  router's decorated handlers so a route added later cannot ship unlimited — the gap that
  `GET /oauth/registrations` opened when INT-8 landed on the branch after this review's first
  pass.

### INT-14-02 (LOW, open): row lock held across an outbound refresh

`DatabaseConnectionResolverService._resolve` holds the connection row lock (on SQLite, the
database-wide write reservation) while `broker.refresh_if_needed` may wait up to 20 seconds on a
provider token endpoint. This is the contract's deliberate cross-worker single-flight choice
(`connection-contract.md` question 12.b.4), and INT-14-01's rate limits bound how often a caller
can drive it. Accepted; revisit if provider latency incidents appear.

### INT-14-04 (HIGH, fixed): the login-sized limit cut off the pending-consent poll

Found while validating INT-14-01 rather than in the first pass, and it is INT-14-01's own fix that
caused it. `check_rate_limit` with no explicit allowance falls back to `rate_limit_per_minute`,
which defaults to 5 — that number is sized for login attempts. `GET /api/v1/connections` inherited
it, and the Connections UI that landed with INT-8 polls exactly that endpoint every 2000ms while an
OAuth consent is pending (`usePendingConnectionPoll`), with `refetchIntervalInBackground: true` and
`retry: false`.

Thirty reads a minute against an allowance of five: the poll took a 429 on its sixth request, about
ten seconds in, and `retry: false` means that one rejection ends it. A user authorizing at the
provider — which takes longer than ten seconds — came back to a row that never flipped to
authorized, with no error surfaced and no recovery short of a manual reload. Reproduced at stock
defaults before the fix:

```
12 polls -> [200, 200, 200, 200, 200, 429, 429, 429, 429, 429, 429, 429]
```

Fix: metadata reads move to their own counter namespace with their own allowance, following the
`public_flow_rate_limit_per_minute` precedent of throttling a different traffic shape separately
from login.

- New scope `connections-read` for `GET /connections` and `GET /oauth/registrations`; the
  integrations catalog and effective-policy reads keep the `integrations` namespace but take the
  same allowance. All four decrypt nothing and make no outbound provider call.
- `connection_metadata_rate_limit_per_minute` defaults to 60, i.e. double the poll rate.
  `get_metadata_read_limit` returns `None` when rate limiting is disabled, so the disabled path is
  unchanged.
- Writes, credential tests, health checks, OAuth start, and the OAuth callback are untouched and
  stay on the tighter buckets. The split is enforced in both directions:
  `test_exhausted_read_bucket_does_not_block_writes` proves a polling tab cannot lock the owner out
  of a rename, and `test_mutating_routes_share_one_write_bucket` proves a write burst cannot
  throttle the poll.
- `test_shipped_defaults_admit_a_full_minute_of_the_pending_oauth_poll` runs 30 reads at the
  shipped defaults with no override, so lowering the default re-breaks the flow in CI rather than
  in a user's consent screen.

### INT-14-03 (LOW, open): IP-only rate-limit keys

The shared rate-limit service keys counters by client IP (rightmost `X-Forwarded-For` hop only
under `rate_limit_trust_proxy`). Authenticated connection calls could instead be keyed per user;
that requires extending `check_rate_limit`, is shared with login and the public-flow endpoints, and
is out of scope for INT-14. Accepted as platform-wide behavior.

## Per-area narrative

### OAuth broker (`services/connection/oauth/broker.py`) — clean

- State minting: `start` uses `secrets.token_urlsafe(32)` for state and browser values and stores
  only SHA-256 digests (`broker.py:58-73`); the verifier is 64 bytes, Fernet-encrypted
  (`:74`). State is bound to the registration fingerprint, scopes, user, and a fresh generation
  UUID, with a 10-minute expiry (`:68-76`). Scopes must be a subset of the configured registration
  (`:52-54`), and Google tenant restrictions force `openid`/`email` (`:55-57`).
- State replay: `complete` consumes state via a single `UPDATE ... RETURNING` that matches both
  digests and nulls them before any provider exchange (`:85-98`), so no later failure — including
  the provider rejecting an expired code — rolls state back into use. Consumption commits in its
  own transaction; `test_concurrent_callbacks_exchange_only_once` covers the double-spend race.
- Supersession: the second phase re-reads the binding under `lock_connection` and refuses on any
  generation mismatch (`:109-114`), so a newer `start` invalidates an in-flight callback.
- Authorization: the initiating user is re-loaded, must still be active, and must still pass
  `ensure_connection_permission(WRITE)` at callback time (`:115-121`) — consent started by a
  since-revoked user fails closed.
- Token rotation: `refresh_if_needed` honors `rejected_token_digest` with `secrets.compare_digest`
  (`:178-180`), keeps a 60-second expiry margin (`:181`), and refuses refresh without a stored
  refresh token (`:183-185`). Components never see the refresh token: only `access_token` is copied
  into `ResolvedCredential` (`service.py:801-813`), whose `__repr__` redacts and whose `__reduce__`
  raises (`lfx/integrations/models.py:117-129`).
- Revoke: provider revocation is attempted with local removal guaranteed even when the provider
  call fails or the envelope no longer decrypts (`broker.py:194-217`, `service.py:425-439`).

### OAuth configuration and providers (`oauth/config.py`, `oauth/providers.py`, `oauth/locking.py`) — clean

- Redirect validation pins the exact path `/api/v1/connections/oauth/{provider}/callback`, requires
  HTTPS or loopback HTTP, and rejects userinfo, query, and fragment (`config.py:36-54`) — no open
  redirect through registration data, and registrations come only from operator settings, never
  flow JSON (`config.py:1`).
- Validation error text is whitelisted: pydantic input values and unknown field names, which may
  hold secrets, are never echoed (`config.py:103-118`).
- Provider HTTP calls disable redirects and never include response bodies in errors
  (`providers.py:82-99`). Slack identity type and team restriction are re-checked on the token
  response (`:120-142`); Google's `hd` claim is verified against signed ID tokens with fetched
  certificates rather than trusting the authorization-URL hint (`:195-221`). Microsoft certificate
  client assertions are pinned to PS256 with a 5-minute expiry (`:53-79`).
- `lock_connection` takes the row lock as the first statement of a fresh transaction, which the
  SQLite reservation semantics require (`locking.py:18-29`).

### Connection API (`api/v1/connections.py`) — one HIGH (fixed), otherwise clean

- Log leakage: the custom route class strips callback query strings from the request scope before
  dependencies or access logs can render them (`connections.py:39-51`), and the handler clears the
  scope again at response time (`:524`). The authorization `code` and `state` therefore never reach
  uvicorn's access log.
- Browser binding: the cookie name derives from the state digest, is HttpOnly, `SameSite=lax`,
  `secure` when the registration's redirect is HTTPS, path-scoped to the OAuth subtree, and lives
  600 seconds (`:442-450`). This also defeats login-CSRF account linking: a victim who
  opens an attacker's authorization URL completes the callback without the attacker's cookie and
  fails the browser-digest check (`:526`, `:530-537`, `broker.py:88-92`).
- Callback responses carry `no-store`, `no-referrer`, and a `default-src 'none'` CSP (`:73-77`),
  and the failure body is a fixed string with no request data (`:543-546`).
- Authorization ordering: mutations authorize in a separate read transaction before the row lock
  is taken, re-verify ownership under the lock, and re-check the permission after acquiring it
  (`:155-220`); the instance-connection superuser floor applies even when authorization is disabled
  or a plugin would allow (`:59`, `:166-174`). Tests: `test_non_owner_cannot_test_or_delete_connection`,
  `test_denied_cross_user_fetch_does_not_lock_connection`,
  `test_mutation_rechecks_policy_under_lock_without_blocking_durable_audit`.
- Mass assignment: `ConnectionCreate`/`ConnectionUpdate` are `extra="forbid"`; PATCH touches only
  `display_name` and `allow_non_interactive`, and only the owner may widen the opt-in
  (`schemas.py:64-131`, `connections.py:223-227`, `:355-363`). The handle, scopes, identity, and
  credentials are immutable post-creation. All queries are parameterized through SQLModel; no raw
  SQL is built from request data.
- Responses never contain credential material (`schemas.py:134-154`;
  `test_connection_responses_never_include_tokens`).

### Integrations API (`api/v1/integrations.py`) — clean besides the fixed INT-14-01

`include_blocked` is superuser-only (`:111-115`), the effective-policy read returns
`blocked_action_keys` and the unfiltered loaded-provider list only to superusers (`:199-203`), and
blocked providers/capabilities are omitted by default so a picker cannot advertise what execution
would refuse (`:137-164`).

### Identity rules (`api/utils/execution_principal.py`, `lfx/services/connection/base.py`, `services/connection/service.py`) — clean

- The resolver entry point is final: `__init_subclass__` rejects any `resolve` override, and the
  base applies the anonymous/unknown deny floor before the host hook can decrypt or refresh
  anything (`base.py:46-81`). Anonymous principals never resolve user connections.
- Family rules match the contract's section 4 table: public/anonymous families resolve never,
  webhook/deployment families require the per-connection non-interactive opt-in, and the legacy MCP
  transports are owner-only with shares disabled (`execution_principal.py:75-159`). A caller
  identified as the public anonymous actor collapses to `anonymous_public` regardless of the family
  name supplied (`:216-229`).
- Explicit shares are admitted only for `actor` principals on share-permitting families with
  `AUTHZ_ENABLED` and cross-user fetch support, candidates are capped at 50, and more than one
  authorized match fails closed rather than picking by database order (`service.py:633-700`).
- Ownership drift between the metadata lookup and secret access re-checks under the lock and fails
  closed (`service.py:549-575`). A user-owned row shadows an instance row with the same handle, so a
  denied owned connection never silently falls back to the instance credential (`:598-631`).
- Non-interactive opt-in is enforced in the portable floor itself (`base.py:140-151`); enabling it
  is owner-only at the API (`connections.py:223-227`).

### Persistence (`services/database/models/connection/`) — clean

Credential material lives only in `connection_secret.encrypted_payload` (Fernet envelope via the
shared `encrypt_api_key` path), isolated from metadata queries (`model.py:87-103`); the OAuth table
stores digests and the encrypted verifier, never state, browser value, or verifier in plaintext
(`oauth.py`). Check constraints pin ownership-mode/owner consistency and the status/health
vocabularies, and the partial unique indexes guarantee at most one user row and one instance row
per handle (`model.py:39-69`) — the property the shadowing and share-ambiguity rules rely on.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| langflow-base owner | | | |
| lfx owner | | | |
| Enterprise owner | | | |
