# Adding a trigger provider

Installed integration bundles can supply server trigger hooks through the
`langflow.trigger_providers` entry point group. The entry point name is the
provider id. Its distribution must already own that provider's validated
integration manifest and loaded components. Conflicting registrations are
unavailable. Removing or reloading a bundle invalidates its runtime hooks.

```toml
[project.entry-points."langflow.trigger_providers"]
example = "langflow.services.triggers.providers.example.runtime:PROVIDER"
```

The entry point exports a `TriggerProvider` instance from
`langflow.services.triggers.providers.registry`. Server hooks can live in the
backend or in a bundle module imported only by the server. Standalone bundle
imports and component tests must continue to work without `langflow-base`.

```python
from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider

PROVIDER = TriggerProvider(
    provider_id="example",
    bundle="example",
    kinds=(
        TriggerKind(
            kind="example.item",
            component="ExampleOnItemTriggerComponent",
            display_name="Example On Item",
            config_fields=("connection", "repository", "delivery_mode"),
            identity="service",
            push_mechanism="example.webhook",
        ),
    ),
    normalize_config=normalize_config,
    verify=verify_delivery,
    provision=provision_webhook,
    revoke=revoke_webhook,
    validate_manual_credential=validate_token,
    api_origins=("https://api.example.com",),
)
```

The component must be present in both the loaded bundle and its capability
catalog. Its provider and mechanisms must use the provider's own namespace.
Configuration fields cannot contain credentials. Components use
`BaseTriggerComponent` and `ConnectionRefInput`. The server owns connection
selection, identity, scopes, background consent, policy, state, and execution.

## Hook contracts

`prepare(session, trigger)` runs inside the enable transaction after shared
authorization and mechanism selection. It can reserve a durable account-wide
receiver claim using already verified connection metadata. Keep this callback
limited to database work. Resolving credentials through the database resolver
opens another transaction and can deadlock the enable writer on SQLite.
Credential resolution and remote provisioning belong after enable commits.

`normalize_config(kind, raw)` validates the declared nonsecret canvas fields and
returns a dictionary containing only those fields. `collect(trigger, lease)`
returns the existing `SourceRound` model. Each canonical item has `provider`,
`resource`, `id`, `version`, and `data` fields. Optional `deleted` and
`session_key` fields preserve deletion and conversation semantics. The shared
runtime binds the result to its original connection, cursor, mechanism, and
configuration before atomically committing events and the new cursor.

`provision(session, trigger)` returns a `TriggerSubscription` or `None`.
`renew(session, subscription)` returns the provider's new expiration.
`revoke(cleanup_task, lease)` deletes the remote subscription. Cleanup intents
survive local pause and deletion. Nonexpiring remote hooks use
`upsert_subscription(..., expires_at=None)` and have no automatic renewal.

Push sources advertise an operator-configured public HTTPS origin through
`LANGFLOW_TRIGGER_INGRESS_ORIGIN`. An existing OAuth callback origin is also
usable. Each trigger gets its own encrypted signing secret. Provisioning can
decrypt that secret internally and use `source_ingress_url(session, trigger)`.
API reads and flow exports do not expose the signing secret.

`verify(request, secrets, tolerance_s=...)` is a pure synchronous function.
It returns `Verified` after checking the provider's actual proof and resource
filters. `IngressSecrets` includes the internal signing secret, `target_kind`,
and nonsecret `target_config`. A provider can supply
`ingress_secrets(session, trigger)` when its provider requires other internal
verification material. Verifiers receive no session or HTTP client.
`target_config` is the exact persisted configuration snapshot used when
committing canonical items. Treat it as read-only and keep provider metadata
in the other internal verification fields.

Ordinary verified payloads go directly to the durable event ledger. Providers
with change-feed wakeups set `ingress_is_hint=True` and supply a collector.
Providers can instead return `Verified.source_items` to share canonical item
deduplication with polling. An empty tuple accepts an ignored notification
without starting a flow. Pure push sources with no collector never enter
periodic source polling.

`verify_get` handles provider verification challenges through the same bounded
target and proof checks. A GET must return a verified handshake and cannot
enqueue an event. Signed POST handshakes also use `Verified.handshake`.
Provider-specific acknowledgments can set `response_body`,
`response_media_type`, and `response_status`. They are returned only after the
ledger commits. Responses are bounded to 4 KiB and status 200, 202, or 204.
Acknowledgment credentials must never be included in the event payload.

`listener_factory` and `listener_mechanism` on a kind install a custom adapter
using the existing `ListenerAdapter` and `ListenerContext` contracts. Polling
change-feed collectors can use `poll_mechanism` and the shared polling adapter.
All listener sources retain per-connection ownership leases.

## Connection authentication

An installed provider's `validate_manual_credential(payload, context=...)` must
validate an entered token and return a `ConnectionCreate` with the actual
executing identity and grants. It cannot change the provider, handle,
ownership, or the user's background consent. The catalog advertises token
profiles only when the manifest declares an applicable `api_key` profile and
the provider supplies this validator. The Connections dialog then supports
token entry without an OAuth registration.

API permissions that are not OAuth scopes must not become invented OAuth
scope grants. The provider still enforces its real permissions on each API
request. Tokens that expire need an explicit expiration and a documented
renewal path. Direct token entry does not imply automatic refresh. The current
manual connection API requires deleting and recreating the same handle to
replace a token, followed by saving and re-enabling its source nodes.

Providers with delegated OAuth supply `TriggerProvider.oauth` as an
`OAuthAdapter` from `langflow.services.connection.oauth.adapter`. It declares
registration validation, endpoint resolution, explicit HTTPS origins,
authorization parameters, PKCE support, form or JSON encoding, and token
response parsing. The broker retains state verification, token encryption,
refresh locking, rotation, and consent checks. Unknown OAuth providers fail
closed. Provider endpoints never fall back to Slack.

`SourceHTTP` accepts extended provider origins only from the runtime's explicit
`api_origins` tuple. Absolute continuation URLs stay on that same origin and
redirects are refused. Tenant-specific API and OAuth origins must come from
operator configuration, never from flow inputs or provider response URLs.

## Packaging and verification

Each provider PR owns its bundle directory, provider server module, fixtures,
and focused tests. Keep root dependency and lockfile changes in one collective
integration change after the provider bundles exist. That change updates
`pyproject.toml`, `uv.lock`, and the selected profiles in
`scripts/ci/bundle_profiles.json`. Run the profile generator through
`uv run python scripts/ci/manage_bundle_profiles.py --help` before choosing the
appropriate lock commands. Generated catalogs and indexes must come from the
repository's bundle tooling rather than hand edits.

Every provider needs packaging validation, backend-free imports, real recorded
signature and payload fixtures, connection failure and identity tests,
owner-scoped reconciliation and activation, redelivery deduplication,
background execution, and durable subscription cleanup. Local fixtures do not
prove live provider registration or a production account's permissions.
