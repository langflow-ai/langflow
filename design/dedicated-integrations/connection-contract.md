# Connection contract: provider-neutral connection reference and credential resolution (INT-2 design)

Status: draft
Decision ID: connection-contract
Applies to: INT-2 (lfx), with the langflow-base obligations INT-4 and INT-5 must meet and the Enterprise seams
Owners (sign-off roles): lfx owner, langflow-base owner, Enterprise owner, frontend owner
Last verified: 2026-09-01

This document is the INT-2 design that the discovery gate asks the lfx, langflow-base, and Enterprise owners to sign
off before INT-2 is built. Each section states the recommended decision, why, and what was rejected. Section 12
lists the questions each owner answers in review. File and line references were verified against `release-1.12.0`
on 2026-09-01.

## 0. Scope and invariants

INT-2 ships provider-neutral contracts in `lfx` and the headless implementation. It does not ship tables, OAuth
callbacks, encryption, refresh coordination, or UI; those are INT-4 and INT-5 in langflow-base and INT-8 in the
frontend, and this document names what they must provide.

Glossary: a **connection** is a stored credential owned by a user or by the instance; a **connection reference**
(handle) is what a flow stores; the **execution principal** is whose identity a run executes as and the **dependency
principal** is whose credentials it may resolve (both from `scripts/ci/execution_principal_matrix.json`); a
**lease** is the in-process object a component holds to obtain a short-lived token.

Security invariants, each mapped to a test in section 11:

1. Components never see refresh tokens.
2. Credentials never enter `graph.context`, `Graph.__getstate__` (`src/lfx/src/lfx/graph/graph/base.py:1571`),
   background job payloads (`services/background_execution/service.py::submit`), trace inputs, telemetry payloads,
   or error messages.
3. Refresh happens only inside the host worker that needs the token, single-flight across workers.
4. User connections resolve only for actor-or-explicit-share dependency principals; anonymous principals never
   resolve user connections.
5. Every new route and execution seam is classified in `scripts/ci/authz_endpoint_matrix.json` and
   `scripts/ci/execution_principal_matrix.json`.

Corrections to the discovery brief, so reviewers are not surprised: the existing `ConnectionInput` is at
`src/lfx/src/lfx/inputs/inputs.py:843` and is Composio's connect widget (used only by
`src/bundles/lfx-bundles/src/lfx_bundles/composio/composio_api.py`); neither `ConnectionInput` nor `AuthInput` is
listed in `BUNDLE_API.md` although Composio imports `ConnectionInput` from `lfx.io`; `IN_SCOPE_PATHS` in
`scripts/migrate/check_bundle_api_changelog.py:43` covers only `lfx/extension/*`, so `lfx.io` and `lfx.inputs` are
not changelog-gated today; no `ExecutionPrincipal` type exists, only `AuthorizationPrincipal(actor_type, actor_id,
user_id)` at `src/lfx/src/lfx/services/authorization/base.py:58` plus `Graph.user_id`, `end_user_id`,
`tracing_user_id`; the `observability.execution_protocol` ContextVar is telemetry-only and must not be used for
authorization.

## 1. Connection reference shape

**Decision: a new parallel channel for semantics, with a variable-compatible encoding for headless transport.**

- Flow JSON stores a string handle `<provider_id>/<name>`, for example `google_workspace/work`. `provider_id`
  reuses `_PROVIDER_ID_RE` from `src/lfx/src/lfx/extension/manifest.py`; `name` is `[A-Za-z0-9_-]{1,64}`. Parsed form
  is a frozen Pydantic `ConnectionRef(provider, name)` with `parse()`, `to_handle()`, `env_key()`.
- The handle is owner-kind-neutral. Resolution tries the dependency principal's user connection with that provider
  and name, then an instance connection with the same name only if host policy allows the fallback (langflow-base
  default: only when the instance connection is flagged referenceable; question 12.b.1).
- Not `load_from_db`. The DB path in `src/lfx/src/lfx/interface/initialize/loading.py:310-364` calls `get_variable`
  and raises on a missing variable unless env fallback is on; it returns a bare `str | SecretStr` that cannot carry
  expiry, granted scopes, or account identity; `apply_global_variable_defaults`
  (`api/v1/global_variable_defaults.py:107`) would try to bind `default_fields` onto it; and `is_valid_env_var_name`
  (`src/lfx/src/lfx/cli/validation/_env_validation.py:30`) rejects `/`.
- Headless transport reuses the flat map unchanged: `ConnectionRef.env_key()` is
  `LF_CONNECTION__<PROVIDER>__<NAME>` (uppercase, non-alphanumerics to `_`, double underscore separator so
  `google_workspace/work` and `google/workspace_work` cannot collide). It is a valid env name, so
  `VariableService.get_variable` (`src/lfx/src/lfx/services/variable/service.py:63-110`) already resolves it through
  the five-step order including the `x-langflow-global-var-*` alias and `no_env_fallback`.
- Export and import: handles are portable, non-secret text. `strip_secret_field_values_in_place`
  (`src/backend/base/langflow/utils/flow_secrets.py:361`) gains a `connection_references: set[str] | None` kwarg
  mirroring `variable_references` and preserves `connection_ref`-typed values; the frontend
  `removeGlobalVariableFromComponents` (`src/frontend/src/utils/reactflowUtils.ts:2140`) must not touch them. No
  account identity is ever stored in flow JSON.
- `required_connections`: the deployment artifact manifest adds `required_connections: [{provider, name, scopes}]`
  per flow and aggregated, beside `required_variables`
  (`src/backend/base/langflow/services/deployment_artifacts/builder.py:347`); scopes come from the input's declared
  `required_scopes`. The manifest `schema_version` bump is an INT-4 decision.

Rejected: an opaque connection UUID (does not survive export or `lfx run`, and the UI needs a lookup to display it);
a `SecretStrInput` subclass with a synthetic variable name (password rendering, `load_from_db=True` from
`DatabaseLoadMixin`, the DB-path raise, and the env-name constraint); a dict value (`MCPInput` is precedent, but a
string is simpler for tweaks, env, and manifest sorting; the dict is the parsed form only).

## 2. Input type

**Decision: new `ConnectionRefInput` and `FieldTypes.CONNECTION_REF = "connection_ref"`; do not extend
`ConnectionInput`.**

- `ConnectionRefInput(BaseInputMixin, ConnectionRefMixin, MetadataTraceMixin)` in
  `src/lfx/src/lfx/inputs/inputs.py`; `ConnectionRefMixin` in `input_mixin.py` declares `provider: str` (required),
  `required_scopes: list[str]`, `optional_scopes: list[str]`, `identity_kind: Literal["user", "instance", "any"] =
  "any"`, `capabilities: list[str] = []` (INT-3 capability ids). `track_in_telemetry = False`; `CONNECTION_REF` joins
  `SENSITIVE_FIELD_TYPES` (`input_mixin.py:53`). No `ToolModeMixin`, mirroring `SecretStrInput`: an agent must never
  choose a connection at tool-call time, and a validator rejects `tool_mode=True`. `password=False`; no
  `load_from_db`.
- Registered in the `InputTypes` union (`inputs.py:1064`) and `lfx.io.__init__`; `InputTypesMap` picks it up for
  `instantiate_input`.
- Frontend: an additive `case "connection_ref"` in
  `src/frontend/src/components/core/parameterRenderComponent/index.tsx` and the type list in
  `src/frontend/src/constants/constants.ts:685`; the picker reads `templateData.provider`, `required_scopes`,
  `identity_kind` and shows scope coverage against `granted_scopes` from the connections API (INT-4). The component
  index must be regenerated.
- Why not extend `ConnectionInput`: its `ConnectionMixin` (`input_mixin.py:344`: `options`, `connection_link`,
  `search_category`, `button_metadata`) models Composio's remote toolkit-list-and-authorize flow, and the frontend
  `connect` renderer carries a `connectionLink === "validated"` state machine
  (`connectionComponent/index.tsx:58`) tied to it. Changing the `connect` semantics would silently alter a shipped
  bundle. `AuthInput` is a hidden status field (`show=False`), not a value carrier.

## 3. Resolver protocol and discovery

**Decision: new `ServiceType.CONNECTION_RESOLVER_SERVICE` in both enums, abstract base in lfx, discovered through
`deps.get_connection_resolver()`; the principal rides on the Graph, not on the resolver.**

- `lfx/services/connection/base.py`: `BaseConnectionResolverService(Service, abc.ABC)` with
  `name = ServiceType.CONNECTION_RESOLVER_SERVICE.value`, plus a `ConnectionResolverProtocol` in
  `src/lfx/src/lfx/services/interfaces.py` beside `VariableServiceProtocol`.
- Signature: `async def resolve(self, request: ConnectionResolutionRequest) -> ResolvedCredential`, where the request
  is a frozen dataclass `{ref, principal: ExecutionPrincipal, required_scopes: frozenset[str], component_id,
  flow_id, run_id}`; optional `async def describe(self, ref, principal) -> ConnectionStatus | None` for pickers and
  health (default `None`).
- The member is added to `src/lfx/src/lfx/services/schema.py` and
  `src/backend/base/langflow/services/schema.py`. `deps.get_connection_resolver()` follows the
  `get_checkpoint_service()` pattern (`src/lfx/src/lfx/services/deps.py:204`): registered service, else the built-in
  `EnvConnectionResolver` (section 5).
- langflow-base registers `DatabaseConnectionResolverService` with `override=True` in
  `src/backend/base/langflow/services/utils.py` in the same block as `AUTHORIZATION_SERVICE` (lines 616-640).
  Enterprise overrides through `lfx.toml` `[services] connection_resolver_service = "..."`;
  `_register_service_from_path` (`src/lfx/src/lfx/services/manager.py:501`) gets the same subclass check and
  fail-closed `RuntimeError` used for `MODEL_PROVIDER_POLICY_SERVICE`, because a credential-critical service must
  refuse to start rather than fall back. Enterprise mutation routes use the `external_*` to 409
  `managed_externally` idiom from `api/v1/catalog_policy.py`.
- Explicit shares: the base class exposes `authorize_principal(request, connection_owner_id, owner_kind,
  allow_non_interactive) -> None | IntegrationError` implementing the section 4 table; the langflow-base service
  asks `BaseAuthorizationService.enforce` for resource `connection`, action `execute`, when
  `supports_cross_user_fetch()` is true, matching `get_flow_by_id_or_endpoint_name(widen_for_shares=True)`
  (`helpers/flow.py:580-611`).

Rejected: piggybacking on `VARIABLE_SERVICE` (string-only; the DB variant has no share semantics; a variable named
`LF_CONNECTION__X` could impersonate a connection in DB mode); a callable in `graph.context` (not picklable, copied
by `_copy_graph`, invisible to the CI matrices); a method on `BaseAuthorizationService` (the OSS pass-through may be
the registered authorization service while connections must still work).

## 4. Principal-aware resolution

**Decision: introduce `ExecutionPrincipal`, stamped on the Graph by each route family; deny in the resolver as
defense in depth and pre-flight in interactive routes for UX.**

- `ExecutionPrincipal` is a frozen dataclass in `src/lfx/src/lfx/services/authorization/base.py` beside
  `AuthorizationPrincipal`: `kind` drawn from the matrix vocabulary in
  `scripts/ci/check_execution_principal_matrix.py` (`actor | flow_owner | deployment_owner | job_owner |
  anonymous_public`) plus `headless_operator` for lfx CLI and embedded use; `user_id`, `actor_id`, `family`,
  `interactive: bool`, `end_user_id`, `actor_label` (the serve identity string).
- Stamped as `graph.execution_principal` by `build_graph_from_data` and `build_graph_from_db*`
  (`src/backend/base/langflow/api/utils/flow_utils.py:47-84`), `serve_app.py`, and `run/base.py`; propagated by
  `_copy_graph` and `copy_for_run`; excluded from `__getstate__` and recomputed on workers from `job.user_id` plus
  family. Unset resolves to `ExecutionPrincipal.unknown()`, which denies user connections. Today `graph.user_id`
  already is the execution principal id per family (the `PUBLIC_ANONYMOUS_ACTOR_ID` check at `graph/base.py:1858`;
  webhook uses `flow.user_id`), so this formalizes rather than re-plumbs.
- The table below is encoded once and added to `execution_principal_matrix.json` as a `connection_resolution`
  dimension with a checker update:

| Family | Dependency principal | User connections | Instance connections |
|---|---|---|---|
| interactive_chat, v1_run, openai_responses, voice, workflow_v2 | actor_or_explicit_share | owner or explicit share | per policy |
| legacy_mcp | actor | owner only (no shares) | per policy |
| mcp_projects | actor | owner only; project auth `none` runs as the owner non-interactively, so it requires the per-connection opt-in | per policy |
| webhook | flow_owner | only with per-connection `allow_non_interactive` | per policy |
| deployments | deployment_owner | only with per-connection `allow_non_interactive` | per policy |
| workflow_hitl_v2 | job_owner | as the job owner who started it; re-resolved on the worker, never persisted | per policy |
| legacy_public_chat, a2a (anonymous), workflow_public_v2 | anonymous_public | never | deny by default; Enterprise policy may allow flagged instance connections |
| a2a authenticated sub-path | actor | owner only | per policy |
| lfx run, embedded, lfx serve | headless_operator | not applicable (no database) | environment-provisioned only |

## 5. Headless implementations

**Decision: one `EnvConnectionResolver` in lfx serves `lfx run`, embedded Python, and `lfx serve`, because the serve
request scope is already a ContextVar the variable service reads.**

- `lfx/services/connection/env_resolver.py`: `resolve()` computes `ref.env_key()` and calls
  `get_variable_service().get_variable(key)`. That one call already implements request scope
  (`activate_request_variables` in `src/lfx/src/lfx/cli/common.py:447-449`, `LANGFLOW_REQUEST_VARIABLES` JSON via
  `runtime_variables.py`, the `x-langflow-global-var-*` alias), then `safe_getenv` with reserved names denied,
  skipped under `no_env_fallback`. No new ContextVar. If the owners want the ticket's two names,
  `RequestScopedConnectionResolver` is a trivial subclass (question 12.a.1).
- Wire format for the value: a bare access token (`scopes_verified=False`, `expires_at=None`) or a JSON object
  `{"access_token", "token_type", "expires_at", "scopes", "account": {"id", "display", "tenant_id"}}`;
  `normalize_parsed_variables` (`request_scope.py:28`) already serializes nested JSON, so detection is "starts with
  `{`". Refresh is the injector's job (`refreshable=False`).
- Failure: `ConnectionUnresolvedError` names the handle, the env key, and the JSON form, never a value. `lfx run`
  gains `validate_connection_refs_for_env` beside `validate_global_variables_for_env` so the run fails before
  execution under `--check-variables`. `lfx serve` surfaces the typed error through the normal component-error path.
- Identity: the `serve_identity.py` label becomes `ExecutionPrincipal(kind="headless_operator", actor_label=...)`;
  the `run/_defaults.py` throwaway UUID maps to the same kind. The resolver treats both as instance-or-environment
  only.

## 6. Credential object and the MCP seam

**Decision: components receive a `CredentialLease`, not a token; resolution is lazy inside the component and never
happens in `update_params_with_load_from_db_fields`.**

- `ResolvedCredential` (frozen, slots): `access_token: SecretStr`, `token_type`, `expires_at`, `granted_scopes:
  frozenset`, `scopes_verified`, `account: ConnectionAccount | None`, `connection_id`, `owner_kind: user | instance |
  env`, `provider`, `name`. `__repr__` redacts; `__reduce__` raises so it can never be pickled into a job payload or
  cache.
- `CredentialLease` (mutable, in-process): `await lease.get_token()` re-calls the resolver when `expires_at - now <
  60s` (constants from `OAuthConnectorBase`: `MIN_EXPIRES_IN_SECONDS` and the 60-second margin in
  `src/lfx/src/lfx/base/knowledge_bases/ingestion_sources/connector_base.py:140-260`); in-process single flight via
  `asyncio.Lock`. Cross-worker single flight is the host's refresh coordinator (langflow-base), triggered by
  `resolve()`.
- `Component.resolve_connection(field_name) -> CredentialLease` (additive method on `Component`) reads the handle
  from the input, builds the request from `self.graph.execution_principal`, and calls
  `get_connection_resolver()`. Lazy because `set_attributes(params)` would put the value in `_inputs[...].value`
  within reach of trace and telemetry serialization, and because tokens must not be minted for vertices that never
  run.
- MCP: a bundle subclasses `MCPPresetComponent`, declares a `ConnectionRefInput`, and implements
  `async def _mcp_server_config(self)` (`src/lfx/src/lfx/base/mcp/preset.py:127`) returning
  `headers={"Authorization": f"Bearer {await lease.get_token()}"}`. Recorded caveat: `_get_server_key` hashes
  `url|sorted(headers)` (`src/lfx/src/lfx/base/mcp/util.py:1290`), so token rotation creates a new session and
  orphans the old one until idle cleanup; an optional `session_scope` key in `server_config` is proposed (question
  12.a.7).
- Migration: `OAuthConnectorBase` and the Google bundle's `GoogleOAuthToken` and Gmail `SecretStrInput` JSON
  (`src/bundles/google/src/lfx_google/components/google/gmail.py:30`) keep working; a later phase can accept a
  `ConnectionRef` in `KBConnectorSource` (see `decisions/kb-oauth-connector-adoption.md`).

## 7. Typed integration errors

**Decision: an `IntegrationError` hierarchy with kebab-case codes and a normalization helper, sanitized by
construction.**

- `lfx/integrations/errors.py`: `IntegrationError(code, message, hint, provider, retryable, http_status,
  safe_message, details)`; subclasses `ConnectionUnresolvedError` (`connection-unresolved`),
  `ConnectionNotAuthorizedError` (`connection-not-authorized`), `AuthExpiredError` (`auth-expired`),
  `ScopeMissingError` (`scope-missing`, with `missing: frozenset`), `RateLimitedError` (`rate-limited`, with
  `retry_after`), `ProviderUnavailableError` (`provider-unavailable`), `ActionUnsupportedError`
  (`action-unsupported`). `INTEGRATION_ERROR_CODES` is a frozenset and the contract, with the same rule as
  `ERROR_CODES` in `extension/errors.py`: adding is additive, removing bumps `BUNDLE_API_VERSION`.
- `normalize_integration_error(exc, *, provider)` maps HTTP status via `extract_http_status` (already unwraps anyio
  ExceptionGroups, `base/mcp/util.py`), scrubs with `redact_urls_in_text`, and consults
  `register_error_normalizer(provider, fn)` so bundles map SDK exceptions without lfx depending on SDKs.
- UI and HTTP mapping: `error_details_for_client`
  (`src/backend/base/langflow/api/utils/execution_errors.py:20`) gains an `IntegrationError` branch that always emits
  `{code, safe_message, hint, provider, retryable, retry_after}` under every `error_policy`
  (`owner_debug_delegated_sanitized`, `sanitized`, `provider_sanitized`) and adds `details` and traceback only when
  `expose_details=True`. The frontend keys calls to action on `code`: `auth-expired` reconnects, `scope-missing`
  grants, `connection-unresolved` connects.

Rejected: plain `ValueError` strings (the current `OAuthConnectorBase` style, not machine-readable); reusing
`lfx.services.auth.exceptions.TokenExpiredError` (it means the Langflow session JWT); reusing the `ExtensionError`
dataclass (not an `Exception`; loader-specific code namespace).

## 8. Capability metadata types shared with INT-3

**Decision: frozen Pydantic models in `lfx/integrations/capabilities.py`; reserve `ExtensionManifest.integrations`
now.**

- `IntegrationProvider{provider_id, display_name, icon, auth: OAuthProfile, capabilities, docs_url}`;
  `OAuthProfile{kind: oauth2_auth_code | oauth2_client_credentials | api_key, authorization_url, token_url,
  supports_pkce, supports_refresh, scope_separator, default_scopes, identity_kinds, desktop_loopback_ok,
  tenant_param}` (covers the Tauri public-client loopback and Microsoft's `{tenant}` authority);
  `IntegrationCapability{id, display_name, required_scopes, optional_scopes, risk: read | write | destructive,
  component_ref, mcp_tool}`; `ScopeSet.covers(required, granted) -> missing` with provider-aware normalization
  (Google URL scopes, Graph short names, Slack bot versus user scopes), used by both the resolver's `scope-missing`
  check and the picker API. The capability ids are the matrices' `action_id` values.
- `ExtensionManifest.integrations: tuple[IntegrationProvider, ...] | None` is added as an optional field (additive;
  `manifest.py` is in the changelog gate); loader wiring is INT-3.

Rejected: reusing `ProviderManifestEntry` (model-provider registry semantics would route integrations into
model-provider policy); JSON-schema only (the resolver and the picker need the same scope math in Python).

## 9. Telemetry hooks

**Decision: reuse tracing spans for latency and add one small telemetry payload for the error class, with no
identifiers.**

- `IntegrationActionPayload(BasePayload)` in `src/lfx/src/lfx/services/telemetry/schema.py` (mirrored in
  langflow-base): `provider`, `capability`, `ms`, `success`, `error_code` (from `INTEGRATION_ERROR_CODES` or
  `other`), `owner_kind`, `principal_kind`. Fits the 2 KB Scarf GET budget like `MCPToolPayload`. Never: connection
  id, account, handle, token.
- `lfx/integrations/telemetry.py: integration_action(component, *, provider, capability, owner_kind)` is an async
  context manager that measures latency, normalizes and re-raises via section 7, emits the payload, opens a child
  OTel span under tracer `APPLICATION_TRACER_NAME` (`observability.py:78`, so it passes the export allowlist) with
  closed-vocabulary attributes `integration.provider`, `integration.capability`, `integration.error_code`,
  `integration.owner_kind`, and appends a redacted log to the current component trace via `add_log` so LangSmith and
  Langfuse users see it. `track_in_telemetry` gating (`component.py:705`) already excludes the input by type.

## 10. Bundle API impact

- New public surface: `lfx.io.ConnectionRefInput`; `lfx.integrations` (`ConnectionRef`, `ResolvedCredential`,
  `CredentialLease`, the `IntegrationError` family, `INTEGRATION_ERROR_CODES`, `normalize_integration_error`,
  `register_error_normalizer`, `IntegrationProvider`, `OAuthProfile`, `IntegrationCapability`, `ScopeSet`,
  `integration_action`); `Component.resolve_connection()`; `ExtensionManifest.integrations`. All additive:
  `BUNDLE_API_VERSION` stays 1; `BUNDLE_API.md` gains an "Integrations" table and a changelog entry.
- Gate hygiene: add `src/lfx/src/lfx/integrations/*.py` (and arguably `inputs/inputs.py`, `inputs/input_mixin.py`,
  `io/__init__.py`) to `IN_SCOPE_PATHS` in `scripts/migrate/check_bundle_api_changelog.py`; list `ConnectionInput`
  in the Inputs table as-is since Composio already depends on it.
- lfx floor: bundles that import `ConnectionRefInput` pin `lfx>=1.13` through `scripts/ci/sync_bundle_lfx_pin.py`;
  `lfx.compat` is unchanged.

## 11. Test plan for INT-2

- `src/lfx/tests/unit/integrations/`: `ConnectionRef` parse, handle, and `env_key` round trips including
  `is_valid_env_var_name`; `ConnectionRefInput` wire type, `tool_mode` rejection, `SENSITIVE_FIELD_TYPES` membership,
  `instantiate_input` round trip, exclusion from `create_input_schema`; `INTEGRATION_ERROR_CODES` snapshot and
  `normalize_integration_error` status mapping including ExceptionGroup unwrapping and URL and email redaction;
  `ScopeSet.covers` per provider; manifest `integrations` validation under `extra="forbid"`; `integration_action`
  payload and span attributes contain no handle or token.
- `src/lfx/tests/unit/services/connection/`: env resolver bare versus JSON value; request scope beats env (extend
  `test_request_scope_isolation.py`); `no_env_fallback` blocks env (extend `test_no_env_fallback_credentials.py`);
  reserved names denied; the unresolved error contains no value; `ResolvedCredential` repr and pickle refusal;
  `CredentialLease` refresh-before-expiry with a fake clock and in-process single flight; table-driven
  `authorize_principal` over the 13 families times owner kind times opt-in, loading
  `execution_principal_matrix.json` so every family must appear.
- CLI: `lfx run` pre-flight fails with the typed error before execution; `lfx serve` error events are sanitized
  (extend `test_serve_app.py`).
- Specified here, built in INT-4 and INT-5: the matrix JSON `connection_resolution` dimension and checker update;
  an `authz_endpoint_matrix.json` `connections` family; additions to
  `src/backend/tests/unit/api/v1/test_execution_principal_contract.py`; the `error_details_for_client`
  `IntegrationError` branch under all three policies.

## 12. Open questions by sign-off owner

### a. lfx owner

1. One `EnvConnectionResolver` with documented modes, or two named classes as the ticket text says?
2. Approve `CONNECTION_RESOLVER_SERVICE` in both enums and the fail-closed behavior when an `lfx.toml` class cannot
   be loaded.
3. Home of `ExecutionPrincipal`, and whether `headless_operator` joins the matrix vocabulary or lfx stays outside
   the matrix.
4. `Component.resolve_connection` as a method versus a free function (Bundle API surface).
5. Extend `IN_SCOPE_PATHS` to `lfx/integrations` and the input modules.
6. Package name `lfx.integrations` versus `lfx.services.connection`.
7. An MCP `session_scope` key so token rotation does not orphan sessions.

### b. langflow-base owner

1. Handle-only versus handle plus owner kind, and the default user-to-instance fallback policy.
2. Connection as a new share resource type for explicit shares.
3. Per-connection `allow_non_interactive` semantics, including `mcp_projects` with auth `none`.
4. Cross-worker single-flight refresh: a DB lease column versus a Redis lock; the `background_execution`
   lease-claim code is the precedent.
5. Encryption envelope: extend the `sso_secret.py` HKDF scheme with a new info label, or the Fernet
   `encrypt_api_key` path used by MCP and variables.
6. Artifact manifest schema version for `required_connections`.
7. Desktop: the same `GET /api/v1/connections/{provider}/callback` on `localhost:7860` with a PKCE public client,
   and the redirect allowlist.
8. Frontend export keeps handles.

### c. Enterprise owner

1. Override through an `lfx.toml` subclass plus `external_connections` to 409 `managed_externally` on OSS mutation
   routes.
2. Instance-connection policy: who provisions, and which flows or tenants may reference.
3. Anonymous and public paths: hard deny versus policy-allowed flagged instance connections.
4. Component-level audit for resolution denials (today `audit_decision` is route-only).
5. Bring-your-own provider app registration per tenant versus the Langflow-hosted app.
6. Token residency and KMS expectations for the envelope.

### d. frontend owner

1. The `connection_ref` renderer and picker API shape (`GET /api/v1/connections?provider=`) with scope coverage.
2. The `code` to call-to-action mapping.
3. The export scrubbing rule for `connection_ref`.
4. Component index regeneration and i18n.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| lfx owner | | | |
| langflow-base owner | | | |
| Enterprise owner | | | |
| frontend owner | | | |
