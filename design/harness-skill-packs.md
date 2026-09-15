# Skill Packs and the production path

Status: implemented on `feat/harness-skill-packs`, based on `90a7dd4069`.
This is the first slice following the [n8n comparison](n8n-harness-gap-analysis.md).
Eval Suites and the complete Harness release lifecycle are subsequent slices.

## Authoring and execution

Skill Pack is a project type. A skill has a unique lowercase name, a description
of when to use it, instructions, and reviewed Tool Pack references. The form
validates names and required content; the backend repeats validation and checks
access to every dependency. A pack supports up to 50 skills.

The Harness attaches explicitly reviewed packs. Saving copies their complete
manifests into the selected Agent and creates ordinary Run Flow tool adapters.
The existing canvas-edit protection, restore points, snapshots, and permissions
apply. Later source edits do not silently replace copied skill instructions.
Saving an outdated reference requires another review.

The model initially sees skill names and descriptions. `activate_skill` loads
one skill's instructions and enables its scoped tools; `finish_skill` removes
them again. Both must be called alone, preventing a parallel activation/tool-call
race. Other locally connected tools and globally attached Tool Packs retain their
existing availability. Scope is checked at invocation as well as in the list of
tools offered to the model. Activation does not grant authorization or override
approvals. The blanket Deny tools policy also blocks skill-control calls.

Skill state survives approval checkpoints. Run configuration captures reviewed
manifests, and streaming run traces display activation, completion, and blocked
calls. These controls require a tool-capable model even for instruction-only skills.

There is no new prompt component. Ordinary Prompt Template / Message instructions
continue to work as previously agreed.

## Workflows API acceptance

The production contract is `POST /api/v2/workflows`; Playground success alone is
insufficient. `src/backend/tests/unit/api/v2/test_workflow_skills.py` uses the real
API, authentication, database, graph, Run Flow tools, middleware, event encoding,
and checkpoint/resume machinery. Only the language-model provider is scripted.

| Scenario | Verified behavior |
|---|---|
| Export composition, import, run synchronously | Remapped skills and tools run; the final answer is returned in `output.text`. |
| Imported composition, Langflow SSE | Scope enforcement runs and skill activity appears in the trace. |
| Imported composition, AG-UI SSE | Same execution and activity, with a completed run lifecycle. |
| Background run, approve through resume API | Skill remains active across reconstruction; the reviewed tool executes. |
| Background run, reject through resume API | Skill remains active, and the tool does not execute. |
| Duplicate resume | Returns 409 rather than applying a second decision. |
| Tool access revoked after save | Fails before model execution; the sync response reports `has_errors`. |
| Calls before activation / after finish | Both return tool errors; the same tool succeeds while its skill is active. |

Workflow callers must check `has_errors`/`status` for synchronous execution, and
terminal events or persisted job status for streams/background jobs. HTTP 200
alone is not proof that the graph completed successfully.

## Deployment boundaries

Two archives serve different purposes:

- **Project composition ZIP:** imports reviewed projects, flows, and source versions
  into Langflow storage. This is the tested path for a Harness with Skill Packs and
  Tool Packs on a Langflow host. Configure destination credentials after import.
- **Standalone deployment package (`.lfpkg`):** currently provisions flow files,
  memory, and knowledge resources. It does not provision the project/version store
  required by Tool Pack adapters. Packaging now rejects those references with a
  specific remediation message, including skills that require them. It must not
  silently produce an artifact that cannot run.

Instruction-only skills carry their entire definition in the Agent and run through
standalone `lfx serve`'s Workflows API without project storage. This is exercised by
`src/lfx/tests/unit/cli/test_serve_workflow_skills.py`. Standalone background and
approval/resume support are not claimed; the host has its own mode restrictions.
This slice does not establish standalone portability for every existing Harness
customization or arbitrary dynamic reference.

## Gates for subsequent slices

Every capability branch must preserve the API execution tests and document its
supported hosts. Before calling the complete Harness production-ready:

1. Package the full reviewed dependency closure for standalone deployments, with
   credential placeholders and validation against the actual target host. Exercise
   that artifact in a clean runtime, without access to the author's database.
2. Extend Workflows API scenarios across Instructions, Hooks, Context, Compaction,
   Permissions, tools, skills, and sourced artifacts together. Include stale/missing
   versions, revoked access, malformed outputs, cancellation, timeout, disconnect,
   reconnect, duplicate submission, and service restart during approval.
3. Run the supported production database and worker topology, concurrent sessions,
   and real provider smoke tests. Deterministic provider tests do not prove provider
   availability, model quality, production isolation, or load behavior.
4. Add Eval Suites targeting an exact candidate composition. Quality, policy,
   latency, and budget results must remain attached to that candidate.
5. Publish immutable complete compositions using existing version/deployment
   facilities. Callers pin a release; preview, promotion, rollback, and in-flight
   resume across deployment must have explicit tested semantics. Bound flow
   snapshots alone are not a complete release mechanism.

## Scope and verification limits

This slice has static reviewed instructions and Tool Pack dependencies, one active
skill, composition ZIP portability, and authoring/review UI. `SKILL.md` import/export,
attached assets, dynamic Skill flows, delegation, and simultaneous active skills
are not implemented.

The targeted shared-runtime, project API, artifact, Workflows API, and UI suites
pass. Whole-frontend typecheck retains 255 existing errors, with no diagnostics in
the changed files. The 31 new English strings are not yet translated into the
other locales. Live-provider, browser visual, load, restart, and production-database
verification were not performed for this slice. These are explicit limits, not
evidence of production readiness.
