# Harness production gap and delivery plan

Reassessed September 15, 2026 against `2872d0193d`. This supersedes the ordering in
the [n8n comparison](n8n-harness-gap-analysis.md) and the generic follow-up gates in
[Skill Packs](harness-skill-packs.md). Evidence is code inspection and previously
run tests, not a new production certification.

**Objective:** author an Agent Harness from typed projects, freeze a complete
candidate, evaluate it, and execute/promote/roll back the same candidate through
the Workflows API. Research producing a sourced artifact remains the proof workflow.
Agent Harness, Tool Pack, Skill Pack, and the planned Eval Suite remain the product
model; deployment artifacts and releases are lifecycle records.

## Runtime artifact delivery update

The first branch now implements an explicit v5 candidate writer/reader and LFX
mount through the Workflows API. See [the implementation and verification record](harness-runtime-artifacts.md)
for the shipped contract, reader refusal evidence, clean-process acceptance, and
host restrictions. The assessment below is the pre-implementation baseline.
The second branch, `feat/harness-workflow-reliability`, now adds operator-mounted
candidates on the authenticated Workflows host, atomic job-owned retention, and
approval/service/fresh-process restart coverage. See [its host and rollout
contract](harness-workflow-reliability.md). The next capability branch is
`feat/harness-eval-suites`; production topology/provider acceptance remains open.
Files, memory/knowledge services, and request-only credential provisioning remain
blocked by the initial standalone mount; their production host provisioning still
needs verification. Existing Control Plane deployment is not candidate-aware.

## Revised gap assessment

| Area | What exists | Remaining gap |
|---|---|---|
| Skills | Reviewed packs, copied instructions, enforced scope, approval integration, composition import/export. | Core slice implemented. Assets, `SKILL.md` interchange, dynamic skill flows, and multiple active skills are separate extensions. |
| Hosted Workflows API | Six deterministic cases cover imported sync/two SSE protocols, background approve/reject, duplicate resume, and revoked access. | Combined controls, production topology, providers, and restart during skill approval need proof. Import occurs in the same test installation/user, not a clean deployment. |
| Portable execution | Composition ZIPs relocate editable projects. Run Flow and customization runners support frozen definitions. | No complete immutable candidate connects the root graph, reviewed dependencies, runtime resources, and a verified artifact loader. A replica of the authoring database is not the desired solution. |
| Graph lifetime | Nested graphs inherit frozen definitions. Hosted checkpoints preserve root payload and reviewed binding records. | Copies omit frozen definitions; changing a run ID clears them; checkpoints do not carry an artifact/frozen-definition reference. A ZIP-only fix would lose dependencies during execution or reconstruction. |
| Deployment package | `.lfpkg` writer includes flow files, hashes, variable/connection requirements, and memory/knowledge definitions. Tool Pack references are rejected. | Include reachable reviewed definitions/resources and implement reader compatibility. Bare `lfx serve` loads graphs/files/directories; no `.lfpkg` reader was found in the inspected LFX CLI. |
| Durable execution | Existing platform tests cover restart, resume, stop, submission idempotency, reattachment, and end-user isolation. | Extend these facilities/tests to a pinned Harness candidate. Do not build a second job system or describe existing capabilities as absent. |
| Evaluation | Runtime assertions and sourced-report evidence exist; claim support is `not_evaluated`. | Eval Suite projects and repeatable quality/policy/budget assessment tied to a candidate digest. Citation membership alone does not establish support. |
| Releases | FlowVersion and deployment snapshots/attachments exist. | Complete Harness release, promotion, rollback, retention, and behavior for paused runs during deployment. |

Code evidence: [dependency traversal](../src/lfx/src/lfx/projects/dependencies.py),
[Run Flow resolution](../src/lfx/src/lfx/base/tools/run_flow.py),
[customization resolution](../src/lfx/src/lfx/projects/invocation.py),
[graph copy/reset](../src/lfx/src/lfx/graph/graph/base.py),
[checkpoint schema](../src/lfx/src/lfx/graph/checkpoint/schema.py),
[checkpoint restoration](../src/lfx/src/lfx/graph/checkpoint/resume.py),
[artifact writer](../src/backend/base/langflow/services/deployment_artifacts/builder.py),
[standalone host](../src/lfx/src/lfx/cli/serve_workflow.py), and
[deployment infrastructure](../src/backend/base/langflow/api/v1/deployments.py).

A read-only in-memory probe reproduced the graph-copy/reset loss. Hosted runs
currently re-resolve version snapshots from storage; artifact-backed runs need
the missing preservation described above.

The packaging rejection is a guard, not closure of the gap. Resource definitions
in a manifest are provisioning requirements, not proof that the destination has
provisioned them or copied their underlying data.

## First production host contract

The full production path is a Langflow host with its supported durable database,
job execution, authentication, and resource services. Keep `/api/v2/workflows` and
its job routes. Bind an existing workflow identifier to the candidate server-side;
avoid a parallel Harness execution API.

Standalone LFX remains a narrower profile: sync and stream, with required resources
available locally. It currently rejects background mode and several request
overrides. A shared URL does not imply identical host capabilities. Standalone
durable approval/background parity is not required for the first hosted release.

Candidates declare required host capabilities. Preflight must reject unsupported
approval paths, permission flows that can ask, missing providers/resources,
unsupported artifact versions, and unresolved dependencies before execution.
Dynamic dependencies need explicit declarations; inspecting arbitrary component
code cannot prove them complete. Keep packaging guards until the relevant writer,
loader, and clean-runtime execution checks pass.

## Design decisions

1. **Separate editable composition from executable candidate.** Keep composition
   ZIP import for authoring. A candidate contains the selected root and reachable
   reviewed definitions: Instructions, Hooks, Context, Compaction, Permissions,
   local tools, Tool Packs, and copied skills. Reuse traversal, validation, and
   snapshot readers. Exclude unrelated flows and never silently select newer drafts.
2. **Resolve an immutable definition map.** Extend existing frozen lookups through
   a shared resolver. Missing IDs fail without falling back to the authoring DB or
   an unrelated same-name flow. Preserve reviewed provenance. Register only declared
   entrypoints with the API; internal tool/customization flows must not become public
   endpoints simply because they were packaged.
3. **Carry candidate identity through the run.** Copies, nested calls, run resets,
   warm caches, job records, checkpoints, and outputs retain the same digest. Resolve
   retained artifacts by digest on resume, separately from mutable run caches.
   Missing/expired artifacts and incompatible runtimes fail explicitly; they never
   fall back to today's draft. Existing checkpoints remain readable.
4. **Define sanitization and resource identity.** Validate reviewed source versions
   before normalization. Compute the executable digest over canonical sanitized
   definitions and their manifest, preserving linked original review identity.
   Credentials remain destination-bound references. Declare required variables,
   connections, providers/components, files, memory, and knowledge; pin runtime/package
   compatibility. Graph JSON alone is not the execution environment.
5. **Preserve authorization at each boundary.** Source export/deploy permissions
   govern candidate creation; destination deployment, caller, tool policy, and
   resource permissions govern execution. An artifact is not an authorization grant.
   Hosted authoring runs retain current dependency checks. Exported copies cannot
   promise automatic revocation when a source installation deletes a share; destination
   administrators must be able to disable a release.
6. **Evaluate and promote identical content.** Candidate identity precedes Eval
   Suites. Promotion changes a pointer without rebuilding content; rollback selects
   a retained candidate. New runs use the selected release; paused runs retain their
   original candidate and compatible runtime. Block promotion or explicitly terminate
   affected runs when compatible resume cannot be provided; do not silently migrate.

## Four sequential capability branches

Proposed branches are created when implementation starts, with small commits within
each. Push branches without PRs; this plan does not need its own branch.

| Order / proposed branch | Deliverable | Acceptance gate |
|---|---|---|
| 1. `feat/harness-runtime-artifacts` | Candidate schema/digest, authorized dependency materialization, host preflight, writer/reader integration, artifact-backed resolution across graph copy/reset. | Build once; load in a fresh runtime without the authoring DB; run a tool-bearing Research Skill through sync and both SSE formats. Scope/provenance remain correct. Missing/tampered definitions, unavailable resources, and incompatible runtimes fail before execution. Only declared entrypoints are exposed. |
| 2. `feat/harness-workflow-reliability` | Candidate identity in durable jobs/checkpoints, combined Harness API tests, supported topology/provider validation using existing infrastructure. | Full Research Harness runs before/after restart and approval through the API, without candidate drift, cross-user/session leaks, stale approval reuse, or lost terminal/error events. |
| 3. `feat/harness-eval-suites` | Eval Suite project type: cases, scorer flows/contracts, expected artifacts/policy results, latency/cost budgets, candidate comparison. | Evaluate a specific candidate through Workflows API execution; retain inputs, scorer revision, candidate digest, results, and thresholds. Unsupported claims and policy violations demonstrably fail evaluations. |
| 4. `feat/harness-releases` | Draft/candidate/live UI and API, preflight/release contents, evaluation-gated promotion, rollback, retention, runtime compatibility using existing version/deployment facilities. | Promote evaluated bytes, edit drafts without changing live behavior, roll back, and resume an older paused run against its retained candidate. Complete staging acceptance on the production topology. |

Branch 1 excludes publishing UI and standalone durable jobs. Branch 2 reuses platform
facilities and fixes failures exposed by the Harness. Branches 3–4 add the product
surfaces once candidate identity is stable.

## First branch: implementation-sized steps

1. Add failing fixtures for a saved Harness using a Skill Pack, a Tool Pack with a
   nested call, and representative bound customization flows. Prove missing
   definitions, graph-copy/reset loss, and an incompatible approval host. Extend
   existing project/API fixtures instead of creating a fake execution path.
2. Add a storage-independent candidate schema/materializer in `lfx.projects`, fed
   authorized exact definitions by backend snapshot resolvers. Record root,
   reviewed bindings, executable hashes, requirements, entrypoints, and runtime
   compatibility. Test cycles, closure limits, conflicting revisions, missing files,
   concurrent source edits, and secret scrubbing.
3. Locate and verify the actual deployment package consumer before selecting a new
   manifest version; versions 1–4 already have meanings in the writer. Extend writer
   and reader together, retaining old-reader refusal and archive size/path/integrity
   protections. Implement the LFX mount adapter needed for clean-runtime tests;
   do not assume `lfx serve file.lfpkg` already exists.
4. Bind verified immutable definitions at the workflow host boundary. Preserve them
   across graph copy/reset and nested calls while isolating mutable state. Internal
   dependencies are lookup entries, not automatically registered API workflows.
5. Run clean-process API acceptance with authoring helpers unavailable and only
   destination credentials/resources. Remove the Tool Pack packaging rejection only
   for supported artifact/host combinations. Gate durable approval candidates until
   branch 2 verifies reconstruction.

## Combined Workflows API acceptance matrix

Use one canonical Research fixture and targeted variants that isolate each control.
Execute the actual API/graph, substituting only external services in deterministic
CI. Extend existing real-services/live-provider lanes where available.

| Dimension | Required evidence |
|---|---|
| Composition | Instructions → context/compaction → hooks → skill → reviewed tool → permissions → sourced artifact; recorded versions match the candidate. |
| Sync / streams | Consistent final outcome across sync and both SSE protocols; explicit errors and one terminal outcome. Include malformed tool/hook output and provider failure. |
| Background / resume | Persist, disconnect, reattach, restart the service, then approve/reject/edit the same call. Test duplicate/stale decisions and changed hook arguments. |
| Identity / concurrency | Users, sessions, and candidates cannot share activation, memory, credentials, outputs, or approval rights. Exercise cold and warm graph paths. |
| Cancellation / budgets | Stop around approval, timeout during nested execution, bounded model/tool calls, and documented disconnect behavior. Committed external effects cannot be undone. |
| Submission / effects | Existing idempotent submission prevents duplicate jobs. Define hook/tool idempotency across retries/resume; do not promise blanket exactly-once external effects. |
| Artifact / access | Missing/modified/inaccessible dependencies fail; incompatible readers/resources are caught at preflight; destination release disablement blocks new execution. |
| Production topology | Supported DB, actual process restart, deployed image, resource/secret provisioning, bounded concurrency, and live-provider tool/stream behavior. Set measurable latency/error/budget thresholds from the fixture baseline before promotion. |
| Release / provenance | Evaluated digest equals deployed digest; drafts cannot alter live/paused runs; rollback/retention work; reports retain candidate/source identity. |

Extend [Skill Workflows](../src/backend/tests/unit/api/v2/test_workflow_skills.py),
[standalone skills](../src/lfx/tests/unit/cli/test_serve_workflow_skills.py),
[artifact tests](../src/backend/tests/unit/services/deployment_artifacts/test_project_artifact.py),
[checkpoint restart](../src/backend/tests/unit/background_execution/test_durable_checkpoint_store.py),
[real-services execution](../src/backend/tests/unit/background_execution/test_facade_real_services.py),
[submission idempotency](../src/backend/tests/unit/api/v2/test_workflow_facade.py), and
[end-user isolation](../src/backend/tests/unit/api/v2/test_workflow_end_user_isolation.py).

## Deferred work and release bookkeeping

Defer delegation, channels/schedules, broader knowledge/memory authoring, skill
assets/interchange, and simultaneous skills until this path is sound. Keep contract
examples and actionable preflight errors in the relevant Harness UI. Reuse ordinary
Prompt Template/Message types. Desktop remains the primary target.

Track the existing frontend typecheck baseline, untranslated strings, base-branch
integration, and manual desktop review separately from execution readiness. Give
each an explicit release disposition; targeted API success does not turn unrelated
repository gates green. Production/provider coverage and actual package-reader
compatibility remain unverified until their acceptance runs occur.
