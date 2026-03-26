# Deployment Boundary and Separation Rules

This document captures the architecture and contract rules
for the deployments implementation.

The goal is strict separation of concerns between:

- Langflow API orchestration (`src/backend/base/langflow/api/v1`)
- Mapper translation/reconciliation layer (`src/backend/base/langflow/api/v1/mappers/deployments`)
- Adapter execution layer (`src/backend/base/langflow/services/adapters/deployment/*`)
- Generic adapter schema/payload contracts (`src/lfx/src/lfx/services/adapters/deployment/*`)

---

## 1) Core Boundary Principles

### 1.1 API route modules must be provider-agnostic

`deployments.py` must not import or branch on provider-specific payload models, constants, slot names, or parser logic.

Allowed in routes:

- Resolve mapper from provider key
- Call mapper public APIs
- Call adapter service APIs
- Apply generic orchestration, transaction, and HTTP error mapping

Not allowed in routes:

- Watsonx (or any provider) specific schema imports
- Direct reads of adapter payload slot internals
- Provider-specific payload shape assumptions
- Mapper-internal validation logic duplicated in route helpers

### 1.2 Mapper is the API-boundary translation and reconciliation owner

The mapper translates API payloads to Adapters and the Langflow DB:

- **API → Adapter** — reshapes the API request's `provider_data` into adapter-layer input models (e.g. `VerifyCredentials`, `AdapterDeploymentCreate`). The adapter then makes the actual provider SDK/network calls.
- **API → DB** — extracts provider-specific fields from the API request and returns a flat `dict[str, Any]` of DB column-value pairs that the route spreads into CRUD kwargs (e.g. `resolve_credential_fields` returns `{"api_key": "..."}`, `resolve_provider_account_update` returns the full update diff).

Mapper responsibility includes:

- API payload validation and translation into adapter payloads
- Provider-specific interpretation of adapter result payloads
- Reconciliation extraction needed by Langflow persistence logic
- Extraction and validation of provider credentials from `provider_data` for DB storage
- Assembly of provider-account update kwargs with provider-specific cross-field logic

Mapper responsibility excludes:

- Network calls
- Provider side effects
- Adapter execution logic

### 1.3 Adapter is provider execution owner

Adapter responsibility includes:

- Provider API/network calls
- Provider semantics and state transitions
- Slot-based validation of adapter payload/result structures

Adapter should not:

- Depend on Langflow flow-version concepts directly
- Encode Langflow DB semantics
- Assume API route-level orchestration details

---

## 2) Langflow vs Adapter Vocabulary Rules

### 2.1 No Langflow-specific identity terms in adapter contracts

Do not expose `flow_version_id` as an adapter contract requirement.

Use adapter-neutral correlation:

- `source_ref: str`

Langflow can choose to populate `source_ref` with serialized flow-version IDs, but this is an implementation decision at the mapper/API boundary.

### 2.2 Clean break for fragile positional mapping

Do not rely on ordering between:

- input `flow_version_ids`
- output provider `snapshot_ids`

Instead require explicit create-time bindings:

- `{ source_ref, snapshot_id }`

---

## 3) Contract and Schema Rules

### 3.1 Explicit reconciliation contracts are required

Mapper reconciliation outputs must have explicit schemas, not ad-hoc dict/list assumptions.

Baseline contracts:

- `CreateFlowArtifactProviderData`
- `CreateSnapshotBinding`
- `CreateSnapshotBindings`
- `CreatedSnapshotIds`
- `FlowVersionPatch`

### 3.2 Public interfaces must document contract shape

Public mapper methods must clearly indicate:

- Return contract model
- Intent (mapping vs utility/reconciliation)
- Default behavior
- Provider override expectations

### 3.3 Generic placement rules for payload typing

Generic provider data typing belongs with payload taxonomy definitions (`payloads.py`) when tied to payload slots.

If a generic is used for slot shape constraints, pair it with a `BaseModel`-bound generic for slot declarations.

### 3.4 Mapper-defined schemas are the final API-boundary contract

Mapper contract models are the last stop before route orchestration consumes data.

Rules:

- Mapper-defined schemas must be complete and explicit for route needs.
- Do not add provider-specific escape hatches (for example opaque passthrough blobs, free-form fallback fields, or "raw provider payload" backdoors) to mapper contracts.
- If new provider behavior is needed, extend/normalize through explicit schema fields and mapper overrides, not contract bypass paths.

---

## 4) Payload Slot Ownership Rules

### 4.1 Slot validation ownership

Validation of provider payload/result shape should happen through configured payload slots in the appropriate layer:

- API payload slots in mapper (API-side schema boundary)
- Adapter payload slots in adapter service (provider execution boundary)

Do not bypass slot validation with plain dict assumptions where a slot exists.

### 4.2 Slot naming conventions

Slot names should be concise and aligned with existing naming conventions.

Example rule applied:

- Prefer `flow_artifact` over verbose suffixes like `flow_artifact_provider_data`

### 4.3 Create/update result slot usage

Provider-specific create/update reconciliation data should be emitted through dedicated result slots:

- `deployment_create_result`
- `deployment_update_result`

Do not stash custom reconciliation fields in untyped generic dicts without slot-backed schemas.

### 4.4 Validation path should not duplicate slot/model work

When a payload/result shape is already represented by a known slot model or explicit schema model:

- Validate by calling slot parse directly, or by validating directly against the known schema model.
- Do not add extra wrapper parse helpers that only re-dispatch to the same slot/model without adding new semantics.
- Do not re-discover adapter payload slots through runtime adapter introspection when mapper/provider selection is already explicit.
- When both adapter service and mapper consume the same provider slots, use one canonical provider payload-schema registry object (for example provider `DeploymentPayloadSchemas`) as the source of truth instead of duplicating free-standing slot constants.

### 4.5 No silent no-op fallback on required reconciliation payloads

For required provider reconciliation/result payloads:

- Missing or malformed payloads must fail fast with explicit boundary errors.
- Do not silently substitute empty/default model instances for required provider result contracts.

### 4.7 No silent compatibility fallback on boundary contract violations

When a mapper/adapter boundary payload is required by the active contract:

- Do not add silent compatibility fallbacks that fabricate/derive substitute values when required fields are missing.
- Do not silently coerce missing/invalid payloads into permissive defaults to "keep the flow moving".
- If compatibility mode is necessary, it must be explicit, narrowly scoped, documented, and still preserve fail-fast behavior for malformed required contracts.

### 4.6 Canonical payload-schema registry naming and consumption

When a provider defines a canonical `DeploymentPayloadSchemas` registry object shared by adapter + mapper:

- First define a provider `payloads.py` module as the canonical ownership location for provider payload/result contract models and the registry instance.
- In the provider payload module, the canonical registry constant name must be `PAYLOAD_SCHEMAS`.
- In cross-module imports (service/mapper), import and reference the registry as `PAYLOAD_SCHEMAS` (no aliasing).
- Do not instantiate duplicate registry objects in consumers; import and reuse the single canonical provider registry.
- Do not scatter free-standing slot constants that can drift from the canonical registry.

### 4.8 PayloadSlot parse contract (hard requirements)

`PayloadSlot.parse` is the canonical boundary for provider payload/result parsing.

Rules:

- `raw=None` must fail fast via `AdapterPayloadMissingError` (no silent defaults).
- For non-`None` input, use direct `adapter_model.model_validate(raw)` as the parse path.
- Do not add ad-hoc pre-parse type branching that bypasses or replaces `model_validate`.
- Treat accepted runtime inputs as whatever `model_validate` supports for the model contract (for example dict or model-like input), while keeping missing-payload behavior explicit.

### 4.9 Mapper imports at adapter boundary

Provider mappers sit at the API boundary and must avoid coupling to adapter-owned model symbols when slot contracts already exist.

Rules:

- Mapper may import and use API-layer provider schemas (for example `WatsonxApi*`) for API input shaping/branching/output.
- Mapper should not import adapter-owned payload/result model classes (for example adapter `Watsonx*ResultData`).
- For adapter boundary parsing, mapper should consume the provider `PAYLOAD_SCHEMAS` slots directly.

### 4.10 Mapper boundary typing

Rules:

- Prefer `DeploymentUpdateResult`, `ExecutionCreateResult`, `ExecutionStatusResult` (or similarly broad contract types) at mapper boundaries.
- Avoid narrowing these to `...[AdapterPayload]` in mapper signatures unless the boundary truly guarantees dict-only inputs.

---

## 5) Mapper API Surface and Naming Rules

### 5.1 Semantic families must be visually distinct

Keep method naming families distinct by purpose:

- `resolve_*` for API input resolution/translation
- `shape_*` for outbound API shaping
- `util_*` for reconciliation/util extraction helpers

Avoid overlapping verbs that blur intent (`resolve` vs `reconcile`, etc.).

### 5.2 Keep utility/reconciliation methods together and explicit

Utility methods used by route orchestration (snapshot bindings, created snapshot IDs, flow-version patch extraction, flow artifact provider data construction) should use the utility naming family consistently.

### 5.3 Registry utility should be separate from mapper base implementation

Do not co-locate registry infrastructure with base mapper behavior when it hurts contract readability.

Keep:

- mapper behavior in `base.py`
- registry implementation in `registry.py`
- contract models in `contracts.py`

---

## 6) Provider-Specific Logic Placement Rules

### 6.1 Provider-specific extraction belongs in provider mapper

Examples:

- Tenant ID derivation from provider URL
- Parsing provider create/update results for reconciliation
- Provider-specific flow-version patch extraction semantics

These must be implemented as mapper overrides, not route conditionals.

### 6.2 Provider-specific helper functions in adapters should be modularized

When adapter service classes become heavy, move private create/update helpers into focused helper modules (for example `core/create.py`) to keep service orchestration lean and readable.

### 6.3 Public schemas must live in schema/payload modules, not random internals

If a schema is part of externally consumed adapter payload/result shape, define it in payload/schema modules (`payloads.py` or `schema.py`), not as ad-hoc local classes in deep internal tool modules.

### 6.4 Public helper result contracts follow the same placement rule

If a helper return type is consumed by adapter service orchestration (for example typed create/update apply results used by `service.py`), treat it as a public boundary contract even if it is not directly serialized over HTTP.

Rules:

- Do not define service-consumed contract classes in helper modules (`*_helpers.py`).
- Place provider-specific execution/payload/result contracts in `payloads.py`.
- Place adapter-neutral/shared domain contracts in `schema.py`.
- Helper modules may use these contracts, but should not own them.

### 6.5 Provider-account credential and update contract

The mapper is the **single** component that understands a provider's credential shape and cross-field update rules. The API schema, the DB model, and the route are all intentionally unaware of provider-specific credential semantics.

**Credential flow (API → DB):**

- The API schema exposes credentials as an opaque `provider_data: dict[str, Any]`. It does not validate the dict's contents.
- The mapper's `resolve_credential_fields(provider_data=...)` validates, extracts, and returns a `dict[str, Any]` of DB column-value pairs (e.g. `{"api_key": "..."}` for WXO today). The route spreads these into the CRUD layer's keyword arguments.
- The DB model keeps a fixed column set (currently `api_key: str`). If a future provider requires a different storage layout (multiple columns, a serialised JSON blob, etc.), only the mapper and CRUD layer need to evolve — the route and schema remain unchanged.

**Update assembly (API → DB):**

- The mapper's `resolve_provider_account_update(payload=..., existing_account=...)` assembles the complete update kwargs dict. Only fields present in `payload.model_fields_set` are included so the CRUD layer receives a minimal diff.
- Provider mappers override this method to add cross-field logic. For example, WXO's override re-derives `provider_tenant_id` whenever `provider_url` changes, because the tenant is embedded in the URL path and the two must stay consistent.
- The base mapper provides a concrete default that handles name, URL, credentials, and tenant independently. Provider overrides call `super()` for the common fields and only add their own cross-field rules.

**Defense-in-depth (DB model validator):**

- The `DeploymentProviderAccount` model has a `model_validator` that calls `validate_tenant_url_consistency()`. This catches inconsistent tenant/URL pairs regardless of entry point — even if a future code path bypasses the mapper.
- The validation logic lives in `deployment_provider_account/utils.py` as the single source of truth. Both the model validator and the WXO mapper's `resolve_provider_tenant_id` delegate to the same `extract_tenant_from_url()` function.

---

## 7) Route Orchestration Rules

### 7.1 Routes orchestrate; they do not interpret provider payload internals

Routes may:

- call mapper utility methods
- enforce generic invariants (counts, missing bindings, unexpected refs)
- coordinate DB writes and transaction boundaries

Routes must not:

- parse provider-specific nested payloads directly
- inspect adapter slot configuration internals directly

### 7.2 Mapper lookup API should mirror adapter lookup ergonomics

Provide and use a public mapper getter (`get_deployment_mapper(provider_key)`) to preserve a clear and symmetric contract alongside adapter getter usage.

---

## 8) Data Integrity Rules for Deployment Attachments

### 8.1 Source-ref based matching is authoritative

Create-time attachment mapping must use:

- expected `source_ref -> flow_version_id`
- provider returned `source_ref -> snapshot_id`

with strict checks:

- missing bindings => error
- unexpected `source_ref` => error
- count mismatch => error

### 8.2 Update-time attachment changes are explicit patch operations

Flow-version attachment add/remove operations should be represented via explicit patch semantics (`FlowVersionPatch`) and validated for no overlap.

Provider mappers may enforce provider-specific constraints for where patch operations are expressed (for example inside provider operations payload).

---

## 9) Error Handling Rules

### 9.1 Raise boundary-appropriate errors

- Mapper/API boundary violations: HTTP 4xx/5xx with precise detail
- Adapter slot validation failures: adapter payload validation errors translated into deployment-domain errors with context

### 9.2 Do not silently degrade on contract violations

Missing required bindings or malformed provider result contracts should fail fast with explicit error messages.

---

## 10) Testing and Enforcement Rules

### 10.1 Tests must verify boundary contracts, not just happy paths

Required coverage areas:

- base mapper default utility behavior
- provider mapper override behavior
- route reconciliation failure modes (missing/mismatched bindings)
- provider account shaping through mapper API
- registry behavior and singleton accessors

### 10.2 Tests should assert schema model outputs

When mapper methods return contract objects, assert against model types and fields, not raw loosely typed dict/list assumptions.

### 10.3 Keep naming consistency enforced in tests

When method naming families change for semantic clarity, update tests immediately to prevent drift in contract language.

---

## 11) Practical Review Checklist (PRs touching deployments)

Use this checklist before merge:

- [ ] Route module contains no provider-specific payload model imports
- [ ] Route module does not parse provider payload internals directly
- [ ] Mapper owns provider-specific result interpretation
- [ ] Adapter uses payload slots for validation (no bypassed plain dict assumptions)
- [ ] Correlation uses explicit `source_ref` bindings (not positional mapping)
- [ ] Reconciliation outputs use explicit schema models
- [ ] Mapper-defined schemas contain no provider escape hatches/backdoors
- [ ] Validation path uses direct slot/model parse (no redundant wrapper parse helpers)
- [ ] `PayloadSlot.parse` keeps `None` fail-fast + direct `model_validate` path (no ad-hoc pre-parse bypass)
- [ ] Required reconciliation payloads fail fast (no silent default model fallback)
- [ ] Provider defines `payloads.py` as canonical owner of provider payload/result contracts and payload-schema registry
- [ ] Mapper and adapter reuse one canonical provider payload-schema registry (no duplicate slot registries/constants)
- [ ] Mapper must not import adapter-owned payload/result model classes when slot parsing is sufficient, and when not, a slot should be defined.
- [ ] Mapper boundary result signatures are not over-narrowed to dict-only generics without contract guarantees
- [ ] Method names follow semantic families (`resolve_*`, `shape_*`, `util_*`)
- [ ] Registry/contracts/base files remain separated by purpose
- [ ] Provider-account update logic lives in mapper, not in route conditionals
- [ ] Provider-specific cross-field rules (e.g. tenant/URL coupling) are implemented as mapper overrides calling `super()`, not as base-class conditionals
- [ ] Credential extraction uses `resolve_credential_fields`, not route-level assumptions about `provider_data` contents
- [ ] DB-level consistency validators exist as defense-in-depth for cross-field invariants
- [ ] Tests cover both base mapper defaults and provider overrides
- [ ] Failure cases for missing/unexpected bindings are covered

---

## 12) Change Management Rules for Contract Evolution

Use this workflow for any deployments change that alters payload shape, reconciliation semantics, or ownership boundaries.

### 12.1 Classify the change before coding

Identify the change category first:

- contract addition (new explicit field/model)
- contract tightening (stricter validation or invariants)
- contract replacement (old path superseded by new explicit shape)
- ownership move (logic moved route -> mapper, helper -> payload/schema module, etc.)

The category determines whether compatibility bridges are required.

### 12.2 Contract-first implementation order

Apply changes in this order:

1. Define/update explicit contract schemas (API mapper contracts + adapter payload/schema contracts).
2. Update mapper interpretation/utilities to consume/emit those contracts.
3. Update adapter service/helper orchestration to emit slot-backed results matching the new contracts.
4. Rewire routes/services to call mapper public APIs only (no provider payload probing).
5. Add/update tests for both valid flows and boundary failures.
6. Remove legacy compatibility paths when the rollout mode allows it.

This keeps every boundary explicit while code is in transition.

### 12.3 Compatibility mode must be intentional

For each contract evolution, explicitly choose one mode:

- **Clean break:** old shape is rejected immediately with explicit errors.
- **Transitional compatibility:** old shape is temporarily accepted through a narrow, documented fallback.

Default policy:

- Prefer **clean break** for changes internal to Langflow/adapter implementation layers when public API contracts are unchanged.
- Use transitional compatibility only when required to preserve public API behavior or external integration expectations.

Rules:

- Transitional fallbacks must be minimal, local, and easy to delete.
- Transitional behavior must not bypass slot validation.
- Every fallback must include a removal condition (test or TODO note tied to cleanup).

### 12.4 Public contract placement and naming during migrations

When introducing new public contract types during refactors:

- service-consumed/public helper result contracts belong in `payloads.py` (provider-specific) or `schema.py` (adapter-neutral/shared)
- do not define public contracts in helper modules
- provider-specific public contract names should carry provider prefix (for example `Watsonx...`) to prevent ambiguity

### 12.5 Required test deltas for contract changes

Any contract evolution PR must include tests that prove:

- new contract models are used (not ad-hoc dict assumptions)
- route/service behavior no longer depends on provider payload internals directly
- invariant enforcement for reconciliation (missing bindings, unexpected refs, count mismatch, overlap, etc.)
- compatibility behavior (if transitional mode is chosen) and eventual clean-break expectations

Following this process keeps layering explicit, reduces leakage during migrations, and makes cleanup predictable.

---

## 13) Rollback and Synchronization Rules

### 13.1 Write-path rollback ownership

Both create and update follow a **provider-first** strategy: the provider is called first, then the Langflow DB is updated and committed. If the DB commit fails, the route issues a best-effort compensating call to the provider.

- **Create rollback:** the route issues a compensating `adapter.delete()` to remove the provider resource. Secondary resources (snapshots, configs) are intentionally not cascade-deleted because they may be shared across deployments; they remain as orphaned provider-side resources.
- **Update rollback:** the route asks the mapper to build a compensating update payload via `resolve_rollback_update()`, then issues `adapter.update()`. If the mapper returns `None` (no rollback possible for this provider), provider state may diverge until it is independently detected (e.g., lazily synced in a read path).

Provider-first write is used uniformly. For create, the provider assigns the resource ID and snapshot IDs that the DB needs to store, so calling the provider first is the natural fit. For update, provider-first could be replaced with DB-first since the `resource_key` already exists, but provider-first was chosen for simplicity: both strategies need the pre-update state for rollback, but with provider-first that state already lives in the DB — the mapper can query `flow_version_deployment_attachment` rows at rollback time — whereas DB-first would require explicitly capturing name, description, and every removed attachment's `provider_snapshot_id` into memory before mutating. Provider-first also avoids the two-commit flow that DB-first requires (one commit before the provider call, a second to fill in `provider_snapshot_id` values from the response), and eliminates the consistency window where other readers could observe DB state the provider hasn't processed yet. Since both compensating actions are best-effort either way, the simpler single-commit flow is preferred.

Rollback calls are always best-effort and wrapped in their own exception handling. A failed rollback must never mask the original commit error.

### 13.2 Rollback payload construction belongs in the mapper

The mapper is responsible for constructing provider-specific rollback payloads from current DB state. The mapper reads the `flow_version_deployment_attachment` table to determine the pre-update attachment state and builds an adapter update payload that would restore the provider to that state.

The base mapper returns `None` (no generic rollback). Provider mappers override `resolve_rollback_update` when they can construct meaningful reverse operations.

### 13.3 Read-path synchronization layers

Read-path synchronization operates at two levels and is an independent mechanism from write-path rollback. Synchronization detects and reconciles stale DB data caused by provider-side deletions — it does not undo or compensate for failed write-path operations.

- **Deployment-level:** on list and get paths, the route verifies that deployment resource keys exist in the provider. Stale DB rows for deleted provider resources are removed (FK CASCADE handles attachment cleanup).
- **Snapshot-level:** after deployment-level sync, the route verifies that `provider_snapshot_id` values in `flow_version_deployment_attachment` still exist in the provider. Stale attachment rows are removed to keep `attached_count` accurate.

### 13.4 Rollback and synchronization are independent

Rollback and synchronization address different consistency problems:

- **Rollback** compensates for a provider-side change that the Langflow DB failed to record (write-path problem). Its goal is to undo the provider-side change so that both sides remain consistent.
- **Synchronization** detects provider-side deletions (and maybe mutations) that the Langflow DB hasn't been notified about (read-path problem). Its goal is to remove (or update, respectively) stale DB rows that no longer correspond to (or accurately represent, respectively) provider resources.

When rollback is unavailable or fails, provider state may diverge from the DB. Synchronization operates from DB rows outward (checking whether each row's resource still exists in the provider), so it can only detect stale DB rows for deleted provider resources. It cannot detect orphaned provider resources that were never recorded in the DB (e.g. a failed create rollback), nor can it detect that an existing provider resource's state diverged after a failed update rollback.

### 13.5 Explicit session commit for write-path rollback

Routes that perform write-path rollback must call `session.commit()` explicitly after staging all DB writes, rather than relying on `session_scope()` auto-commit. This allows the route to catch commit failures and issue compensating provider calls before re-raising.

## 14) API Response Ownership Boundaries

### 14.1 Do not mix Langflow-owned and provider-owned fields at the same level

API response schemas must keep a clear ownership boundary between Langflow-managed data and provider-managed data.

- **Top-level fields** should be Langflow-owned: identifiers that Langflow persists and controls (e.g. `deployment_id`, `name`, `created_at`).
- **Provider-owned data** (execution identifiers, agent metadata, status, timestamps, errors) belongs inside the `provider_data` dict.

This prevents future collisions — for example, if Langflow starts persisting its own execution records, a top-level `execution_id` would be ambiguous against the provider's opaque run identifier.

### 14.2 Classification of fields

**Langflow-owned** — fields derived from the Langflow database or assigned by Langflow logic:

- `deployment_id` (DB UUID), `id`, `name`, `description`, `type`
- `created_at`, `updated_at` (DB timestamps)
- `resource_key` — provider-originated but stored and indexed by Langflow, so treated as Langflow-owned once persisted.

**Provider-owned** — values returned by the external provider that Langflow passes through without persisting or interpreting:

- `execution_id` (the provider's opaque run identifier)
- `agent_id`, `status`, `result`, `started_at`, `completed_at`, `failed_at`, `cancelled_at`, `last_error`
- Any other fields the provider returns in its response payload.

### 14.3 Decision checklist for new response fields

When adding a new field to an execution or deployment response:

1. Is Langflow the source of truth for this value? → top level.
2. Does this value come from the provider and Langflow just relays it? → inside `provider_data`.
3. Does the provider supply it but Langflow persists and indexes it (like `resource_key`)? → top level is acceptable.
