# Executable Harness candidates

Implemented on `feat/harness-runtime-artifacts`, the first capability branch in
[the production plan](harness-production-plan.md). This is the portable sync/stream
boundary; durable releases and approval reconstruction remain the next branch.

## Use

1. Save an Agent Harness with its selected entrypoint and reviewed attachments.
2. Download `GET /api/v1/projects/{project_id}/harness-artifact` with normal Editor
   authentication. The response is `harness-{project_id}.lfpkg`; its ETag is the
   candidate digest. This endpoint requires read/deploy permission on the root
   and every included dependency, plus the snapshot readers' access checks.
3. Provision the destination with the manifest's LFX/package versions and variable
   and connection references. Credential values are never supplied by the package.
4. Run `lfx serve ./harness.lfpkg`. Call `POST /api/v2/workflows` with the existing
   entrypoint ID and the destination API key, using `sync`, `stream` + `langflow`,
   or `stream` + `agui`.

The existing composition ZIP remains the editable handoff. The existing project
artifact/deployment path remains guarded: it does not silently switch to this
format. No publishing UI, deployment promotion, or PRs are introduced here.

## Candidate contract

Manifest version **5**, kind `harness-candidate`, contains one entrypoint, exact
reachable definitions, original source revisions, executable file sizes/hashes,
LFX version, inferred package pins, and resource/capability requirements. The
candidate digest is SHA-256 of the canonical manifest; the manifest hashes every
executable file. Original review identities remain embedded in the executable
configuration. Output-contract validation compares the sanitized executable's
revision while preserving that original identity in recorded configuration.

The source collector uses existing version snapshot readers. It does not select
newer drafts of reviewed dependencies. A live root or unversioned dependency is
rechecked for changes during collection. Conflicting versions, missing references,
cycles, ambiguous names, and unrelated included flows are rejected. Metadata-driven
secret scrubbing operates on detached copies. Source records are not modified.

The reader verifies exact archive membership, UUID paths, sizes, hashes, duplicate
entries/JSON members, closure, reviewed references, and declared requirements before
loading component code. Limits: 500 flows, 8 MiB per flow, 64 MiB expanded flow bytes,
4 MiB manifest. The host mount API also accepts an expected candidate digest.
Integrity is not publisher authentication: operators still decide which code to run.

Only the root is registered with the workflow API. Internal definitions are immutable
JSON bytes with detached reads. Graph copies, run-ID resets, subgraphs, Run Flow,
Instructions, and customization invocations retain the same candidate; mutable run
caches and Skill activation remain isolated. Agent configuration records include
`candidate_digest`, without changing hashes of older records that lack it.

Candidate mounts use startup paths, not the mutable flow store. Each new worker
loads the archive again. Keep that path immutable for a deployment; retained
artifact storage and durable job identity are part of the next branch.

## Host limits and production gates

- Standalone supports sync and both SSE formats. Approval policy, permission flows
  (conservatively, because they can return `ask`), tool approval metadata, and Human
  Input require a durable host and are rejected at preflight. Candidate checkpoints
  also fail explicitly until retained-artifact reconstruction is implemented.
- This initial mount requires destination variables/connections in the server
  environment. Request-only credential provisioning is not a supported mount
  profile yet. `--no-env-fallback` does not bypass missing-resource checks.
- Files and memory/knowledge services are declared but blocked by this standalone
  mount. Packaging does not copy file contents, indexes, or database state.
- Preflight checks provider adapters, declared package versions, variable/reference
  availability, and destination component policy. It is repeated for workflow
  requests; an unavailable destination returns `409 HARNESS_CANDIDATE_NOT_READY`
  before opening an SSE response. Credential validity, granted scopes, connectivity,
  and external service behavior remain runtime checks.
- Package inference reuses the existing AST/provider analysis. Arbitrary Python,
  dynamic imports, and dynamically discovered resources cannot be proven complete
  by inspecting graph JSON. Environment/image certification and live-provider tests
  remain production gates. A matching LFX version is not an image digest.
- The API key authenticates the standalone caller. The candidate does not grant
  access to a source installation or bypass destination policy. Exported copies do
  not inherit live source-share revocation.

## Reader compatibility evidence

Inspected the actual IBM CLI reader at
`ibm-langflow:origin/feat/cli-lfpkg-unpack`, commit
`210bdb3cbeab8b4b518d2a79e0b50b65c0452632`,
`src/deployment/cli/lfpkg.py`. It accepts versions 1–2. A local executable probe
against a newly built candidate confirmed refusal of version 5. Versions 3–4 are
already assigned by the Editor writer to resources and connections.

The Control Plane's `docs/deferred-artifact-deploys.md` records removal of its
archive parser/upload routes. The Editor JSON-deploy adapter reads the existing
builder's flow entries directly, so it must not receive version 5 accidentally.
Keeping `build_project_artifact` unchanged and exposing a separate explicit candidate
builder prevents that bypass. No compatibility claim is made for an uninspected
external reader or for Control Plane deployment of these candidates.

## Verification

- Shared project/serve/checkpoint regression selection: **408 passed, 3 skipped**.
  The three opt-in cases are executed separately by the two-environment test below.
- Backend candidate and existing artifact selection: **64 passed**.
- Final targeted shared checks: **38 passed, 3 skipped**. Backend acceptance rerun:
  **6 passed**, including the subprocess that runs the three opt-in cases. Hosted
  Skill Workflows regression: **6 passed**. These selections overlap the larger
  counts above; they are not additional distinct test totals.
- Real standalone graph: Instructions + Hook + Context + Research Skill + Tool Pack
  + a nested evidence flow; sync and both streams, repeated warm runs, scope denied
  before activation and after finish, successful nested tool while active.
- Real backend-created candidate is passed to a **separate Python environment with
  no `langflow` installed**, then executed through all three Workflows API modes.
  Only the external provider model is substituted. The test initially rejected a
  missing OpenAI adapter and a mismatched SDK version; it passed after provisioning
  the declared versions.
- CLI path loading and reconstruction re-mount the same digest without publishing
  internal flows or flattening the candidate into the flow store.

Run the cross-environment acceptance lane with an LFX-only environment that has
LFX's test dependencies and the candidate's provider packages installed:

```sh
LFX_CANDIDATE_TEST_PYTHON=/path/to/lfx-only/bin/python \
LANGFLOW_UPDATE_STARTER_PROJECTS=false \
uv run --no-sync pytest src/backend/tests/unit/api/v1/test_harness_artifacts.py
```

The existing environment at verification used `langchain-openai==1.4.1` and
`openai==2.48.0`, matching the candidate produced by the Editor environment.

Next: retain candidates by digest in the supported Langflow host and carry that
identity through durable jobs/checkpoints, approval, restart, and reattachment.
Then evaluate and promote those same bytes, as ordered in the production plan.
