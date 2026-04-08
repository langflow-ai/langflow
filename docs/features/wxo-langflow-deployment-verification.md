# Langflow ↔ Watsonx Orchestrate (wxO) deployment flow — verification

This document records how the **Langflow repository** implements wxO Langflow tool deployment and execution, compared to a **reference architecture** (tool registration → object storage → TRM / Tools Runtime → `lfx`). It is scoped to code under `src/backend/base/langflow/services/adapters/deployment/watsonx_orchestrate/` and related clients.

**Out of scope for verification in this repo:** wxo-server internals, TRM (Go), Tools Runtime (`server-lite.py`), MinIO path layout, PostgreSQL schemas, Redis, and credential-prefix behavior (e.g. PR #1343). Those must be validated in the respective platform repositories.

---

## Phase 1: Deployment (upload and registration)

### Summary

| Reference diagram | Implemented in Langflow |
|-------------------|-------------------------|
| Flow JSON + `requirements.txt` + connection config | Yes: flow from deployment payload; requirements from `generate_requirements_from_flow` plus explicit `lfx` line; connections bound on the tool and draft credentials pushed via wxO connections APIs. |
| CLI: `orchestrate tools deploy --langflow` | Same HTTP outcome via **IBM Python SDK** (`ToolClient.create` + artifact upload), invoked from Langflow’s deployment service—not the ADK CLI entrypoint. |
| `POST /api/v1/tools` (and follow-up upload) | **Developer Edition:** tool client base is `{origin}/api/v1`; create uses the SDK; upload uses `POST .../tools/{tool_id}/upload`. **SaaS:** upload may go through the orchestrate `base` client—see `WxOClient.upload_tool_artifact` in `types.py`. |

### Artifact zip contents

Built in `build_langflow_artifact_bytes` (`core/tools.py`):

- **Flow JSON** — filename is `{tool_spec_name}.json`, not a fixed `flow.json`. The diagram often uses `flow.json` as a conceptual name; the uploaded bundle uses the tool-derived name unless `flow_filename` is passed.
- **`requirements.txt`** — includes pinned or minimum `lfx` (see below) plus flow-derived dependencies.
- **`bundle-format`** — plain text file with `2.0.0`; not always called out in high-level diagrams but present in the bundle.

### Tool metadata and connections

- Tool shape is produced by `ibm_watsonx_orchestrate_core` (`create_langflow_tool`), with Langflow adding **`binding.langflow.project_id`** from flow provider data.
- Connection IDs are supplied as the `connections` mapping into `create_langflow_tool`; **`binding.langflow.connections`** is the canonical place to read them back (`ensure_langflow_connections_binding` / `extract_langflow_connections_binding`).

### Upload sequence

Langflow registers the tool first, then uploads the zip:

1. `clients.tool.create(tool_payload)` → obtain `tool_id`
2. `upload_tool_artifact_bytes` → multipart upload of `{tool_id}.zip`

Implemented in `upload_wxo_flow_tool` in `core/tools.py`.

### Connection credentials from Langflow

`create_config` (`core/config.py`) resolves Langflow-side environment variables into **`runtime_credentials`** and posts them to wxO (paths differ for Developer Edition vs SaaS: single create vs multi-step `create` / `create_config` / `create_credentials`). This aligns with “store connection mappings / credentials on the platform” even though exact storage (Postgres vs object store) is not defined here.

### `lfx` versioning behavior

- **Pinned mode** (default for non-loopback instances): `_resolve_lfx_requirement()` pins to the installed `lfx` version, or falls back to `lfx>=0.3.0` if discovery fails.
- **Unpinned mode** (loopback / local wxO URL): uses `_LFX_MINIMUM_REQUIREMENT` (`lfx>=0.3.0`) to avoid macOS/Linux wheel mismatches when TRM runs `uv install`—see comments in `build_langflow_artifact_bytes`.

**Implementation note:** As of the verification pass, `core/tools.py` also contained a string replace forcing a nightly `lfx` spec and a `print(requirements)` call. Those are atypical for production and should be reviewed before treating the diagram’s generic `lfx>=0.3.0` story as the only behavior.

---

## Phase 2: Execution (runtime)

### What the reference diagram describes

A chain such as: User/Agent → wxO Server → TRM → Tools Runtime → subprocess `python -m lfx run ...` with env vars from connection details.

### What Langflow implements

**Langflow does not implement TRM, Tools Runtime, or direct Langflow-tool execution.** There is no `server-lite.py` or Go TRM in this repository.

Langflow’s wxO **execution** path is **orchestrated agent runs**:

- `WxOClient.post_run` → `POST .../runs` with message / `agent_id` / optional `thread_id`
- `WxOClient.get_run` → poll run status and result

See `types.py` (`post_run`, `get_run`) and `core/execution.py` (`create_agent_run`, `get_agent_run`).

That implies: when an agent uses a Langflow tool, **wxO is expected** to invoke TRM / Tools Runtime / `lfx` internally. Langflow only starts and observes **agent** runs for “execute deployment” style flows—not a duplicate of steps 2–9 in a platform sequence diagram.

---

## Reference diagram “key components” vs this repo

| Component | In Langflow adapter |
|-----------|---------------------|
| PostgreSQL (tool metadata) | Not referenced; platform concern. |
| MinIO / S3 (`/shared-data/{tool_id}/`, `.venv`) | Not referenced; platform concern. |
| Redis | Not referenced; platform concern. |
| Connection Manager → TRM credential shaping (prefixed / unprefixed `OPENAI_API_KEY`) | Not implemented here. |
| Logging in TRM `connection.go` or Tools Runtime `server-lite.py` | Not in this repo. |

---

## Local debugging aids

- **`LANGFLOW_WXO_DUMP_TOOL_ARTIFACTS`** — if set to a directory, the adapter writes each uploaded tool zip there for inspection (same flow JSON + `requirements.txt` as sent to wxO). See `_maybe_dump_wxo_tool_artifact_zip` in `core/tools.py`.

---

## Conclusion

- **Phase 1:** Langflow’s wxO adapter **matches the intended pattern**: tool spec creation, zip bundle (flow + requirements + bundle format marker), connection binding, create-then-upload. Differences from a minimal diagram are mainly **dynamic flow filename**, the **`bundle-format`** file, **SDK vs CLI** entrypoint, and **SaaS vs DE** URL layout for some calls.
- **Phase 2:** The TRM → Tools Runtime → `lfx` pipeline is **not missing from Langflow**—it is **owned by wxO**. Validate end-to-end behavior in platform repos and integration tests there.
- **Housekeeping:** Review any temporary `lfx-nightly` substitution and debug `print` in `build_langflow_artifact_bytes` if production artifacts must match standard `lfx` pinning semantics.

---

## Primary source files

| Area | Path |
|------|------|
| Artifact build / upload / tool create | `src/backend/base/langflow/services/adapters/deployment/watsonx_orchestrate/core/tools.py` |
| wxO HTTP client facade | `src/backend/base/langflow/services/adapters/deployment/watsonx_orchestrate/types.py` |
| Connection / credentials create | `src/backend/base/langflow/services/adapters/deployment/watsonx_orchestrate/core/config.py` |
| Agent run execution | `src/backend/base/langflow/services/adapters/deployment/watsonx_orchestrate/core/execution.py` |
| Flow requirements generation | `src/lfx/src/lfx/utils/flow_requirements.py` |
