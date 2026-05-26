# Multitenant lfx Prototype

A working POC of the multitenant capability boundary applied to the real
lfx codebase. Loads the actual `Basic Prompting` starter project, runs it
through real lfx, and proves the worker process can complete the flow with
**no DB credentials and no provider keys in its env** — only a short-lived
run token.

Design doc: `~/Projects/ideas/2026-05-14-langflow-multitenant-custom-components.md`.

## What it shows

- lfx's existing `VariableServiceProtocol` is the right injection point. A
  capability-backed `CapabilityVariableService` is registered via
  `@register_service(ServiceType.VARIABLE_SERVICE)` and quietly replaces
  lfx's default.
- The actual `src/backend/base/langflow/initial_setup/starter_projects/
  Basic Prompting.json` loads and runs through `lfx.load.aload_flow_from_json`
  → `graph.async_start`.
- The lfx process runs as a **subprocess worker** with `LANGFLOW_DATABASE_URL`,
  `PG*`, `OPENAI_API_KEY` and friends scrubbed from its env. It refuses to
  boot if any of them are present.
- The LanguageModel component's api_key (`load_from_db: true` →
  `value: "OPENAI_API_KEY"`) is fetched through the capability shim →
  Runtime API → returns the seeded value. Verified at the end by checking
  the API's event log for the `variable_read`.
- With a scope-less token, the capability shim returns `PermissionError`,
  lfx surfaces it as `ComponentBuildError: OpenAI API key is required`,
  the flow fails closed.
- Same-process hostile code can still reuse the worker's run token when
  that token carries the model's `variables:read:OPENAI_API_KEY` scope. Run
  `--attack` to make that gap explicit without printing the secret value.
- Split-worker validation shows the per-vertex direction: the prototype
  loads the real lfx graph, derives variable scopes from each vertex's
  `load_from_db` fields, mints per-vertex tokens, denies an untrusted
  custom-component probe, and runs the scoped model worker only to the
  Language Model vertex.

## Run

```bash
cd prototypes/mt-custom-components

# Happy path: scoped token, flow completes against real OpenAI
bash scripts/run.sh

# Boundary refusal: empty-scope token, flow fails closed
bash scripts/run.sh --deny

# Adversarial validation: same-process code reuses the worker token directly
bash scripts/run.sh --attack

# Adversarial refusal: same attack with an empty-scope token is blocked
bash scripts/run.sh --attack --deny

# Graph-aware per-vertex direction: derive scopes and dispatch vertex workers
bash scripts/run.sh --split-workers
```

The orchestrator inherits your shell's `OPENAI_API_KEY` and seeds it into
the Runtime API. The worker subprocess never sees the key in its env. If
you don't have a real key set, the orchestrator seeds the sentinel
`"MOCK-not-a-real-key"` and the lfx run still proceeds (it just fails at
the actual OpenAI HTTP call — the boundary verification still passes
because the variable read was logged).

## Layout

```
runtime_api/                       Control-plane stand-in
  main.py                          FastAPI: variables / memory / artifacts / events
  auth.py                          JWT mint/verify and scope check (HS256, prototype)
  store.py                         In-memory tenant-keyed store

capability_variable_service.py     The shim: implements VariableServiceProtocol,
                                   registered via @register_service. Every
                                   get_variable() call goes to the Runtime API
                                   carrying the worker's run token.

flows/basic_prompting.json         Real Langflow starter project, with the
                                   LanguageModel api_key field set to
                                   value="OPENAI_API_KEY", load_from_db=True so
                                   the variable service is actually consulted.

scripts/
  orchestrator.py                  Control plane: starts the Runtime API,
                                   seeds the variable, mints the run token,
                                   builds a scrubbed env, spawns the worker.
                                   In split-worker mode, imports lfx only
                                   to inspect graph metadata for planning.
  per_vertex_plan.py               Loads the real lfx graph and derives
                                   per-vertex scopes from load_from_db fields.
  worker.py                        Worker subprocess: refuses to boot under
                                   forbidden env, registers the capability
                                   shim, loads + runs the flow, emits a
                                   single JSON outcome line.
  run.sh                           Convenience wrapper.
```

## Where it differs from production

This is a POC. The shape lines up with the design doc; the production
hardening does not:

- **Token signing.** HS256 with a shared secret. Real version wants
  asymmetric signing (control plane signs, workers only verify) and
  mutual TLS on the Runtime API.
- **Runtime API store.** In-memory dict keyed by `(tenant_id, name)`. Real
  version is whatever the control plane's source-of-truth is.
- **Subprocess vs container.** The "worker tier" here is a Python
  subprocess with a scrubbed env. Real multitenant workers belong in
  containers / Firecracker / a managed microVM; the shape of the
  capability boundary doesn't change.
- **One worker per flow.** Per-vertex isolation (a separate worker for
  each component) is the design's stronger story — useful when first-party
  components are trusted but user custom components in the same flow are
  not. The `--attack` mode shows why this matters: process-level isolation
  alone protects the control plane from the worker, but not trusted and
  untrusted components from each other inside that worker. The
  `--split-workers` mode exercises the next boundary by deriving per-vertex
  scopes from the actual flow and giving workers different tokens.
- **Graph partitioning.** The `--split-workers` mode uses lfx graph metadata
  and `stop_component_id` to run the scoped model worker only as far as the
  Language Model vertex. It still does not serialize arbitrary vertex outputs
  between worker processes or replace lfx's core scheduler.
- **Capability surface.** Only `variables:read:*` is exercised because
  Basic Prompting only needs the api_key. Memory / files / artifacts /
  events endpoints exist on the Runtime API and have the same shape.

## One real finding worth flagging

`src/lfx/src/lfx/base/models/unified_models/credentials.py:32` checks
`os.environ.get(var_name)` **before** consulting the variable service. In
this prototype that means the worker env *must* be scrubbed of provider
keys — otherwise the env value silently bypasses the capability boundary.
Real integration should either invert that order in multitenant mode, or
make the variable service the sole resolver. The orchestrator here scrubs
defensively for the same reason.

Separately, `credentials.py:100` catches `(ValueError, Exception)` broadly
when the variable service raises. Our shim's `PermissionError` (scope
denied) gets flattened to "API key is required" — same outcome, lossier
message. Worth letting typed denials bubble.
