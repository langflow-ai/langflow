# Retained Harness execution through the Workflows API

Implemented on `feat/harness-workflow-reliability`, based on `21b9db6ee7`.
This adds a durable Langflow host for the v5 candidates described in
[harness-runtime-artifacts.md](harness-runtime-artifacts.md). The product remains
Agent Harness + its reviewed project attachments. There is no additional execution
API, new job system, publishing UI, or database migration in this branch.

## Host selection and use

The authenticated `POST /api/v2/workflows` host can bind an **existing destination
workflow UUID** to a verified archive through operator configuration:

```json
{
  "<entrypoint UUID>": {
    "path": "/srv/langflow/candidates/research.lfpkg",
    "digest": "<64 lowercase hexadecimal characters from the artifact ETag>",
    "enabled": true
  }
}
```

Supply this JSON as `LANGFLOW_HARNESS_CANDIDATE_MOUNTS`. The destination workflow
record must exist with that same UUID and its intended owner/project/workspace.
It supplies current access and provider-policy scope; it does not supply executable
graph bytes. The mount is trusted operator configuration, never request data or an
editable flow field. No internal dependency is registered as another API entrypoint.

Download the archive using the existing authorized
`GET /api/v1/projects/{project_id}/harness-artifact`. Provision the declared runtime,
packages, environment variable/connection references, and the destination workflow
record before configuring the mount. The archive is not a credential or access grant.

Call the usual Workflows API with the root UUID (or its existing endpoint name).
`input_value`, `session_id`, `globals`, and existing sync-only `output_ids` keep their
normal meanings. Candidate runs reject graph data, tweaks, file overrides, and
partial-run boundaries. These would change the reviewed executable. Credentials
must still be provisioned for preflight; request-only provisioning is not yet a
supported profile.

Candidates without suspension requirements support sync and both SSE protocols.
Root Agent approval/permission paths and root Human Input require `mode=background`.
They are rejected before a sync/stream response starts. Approval inside a nested
flow is explicitly unsupported. Files and memory/knowledge requirements remain
blocked by this initial host profile. Standalone LFX still rejects durable approval.

This mount applies to the authenticated v2 Workflows host. It does not convert v1,
public/share, A2A, MCP, or Control Plane deployment routes into candidate release
endpoints. Authoring remains separate; the later release branch owns those product
surfaces and serving exposure decisions.

## Retention and reconstruction

- A job's `candidate_digest` and its `job_checkpoints[kind=harness-candidate]`
  archive are committed in the **same transaction** as the QUEUED job. Archive
  encoding uses bounded workers. A failed archive-row insert rolls back the job.
- The runner resolves the archive from that job, checks its digest and entrypoint,
  and rechecks runtime/resources and current destination component policy. Every
  included definition is prepared before a provider call. It never substitutes a
  newer mount or falls back to a source flow lookup.
- Graph checkpoints carry `candidate_digest`. Restoration requires matching
  retained bytes and uses their root definition, not the checkpoint's executable
  payload or today's draft. Existing checkpoints with no digest remain readable.
- Instructions and other Run Flow/customization invocations inherit the candidate
  and destination provider scope. Nested flows also inherit end-user identity,
  ephemeral-message behavior, and detached request variables.
- Resume validates retained bytes and preflight before claiming the pause. Missing,
  corrupt, disabled, or incompatible candidates return `409
  HARNESS_CANDIDATE_NOT_READY`; they do not consume the decision. The existing
  single-flight/stale-decision, ownership, end-user, stop, and deadline machinery
  remains in charge. A worker-side preparation failure produces a durable terminal
  error, including after queued-job recovery.
- `candidate_digest` appears on candidate sync/job/status responses; it is omitted
  on legacy responses. Live SSE responses include `X-Langflow-Candidate-Digest`.
  Agent configuration already records the same digest. Completed status reconstructs
  from stored outputs, or the retained root for the vertex-build fallback.

Selection changes affect **new jobs**. Existing queued/paused jobs retain their
original executable even if the archive file is deleted. The database retention
record must outlive those jobs. This implementation deliberately duplicates the
archive per job; content deduplication and lifecycle retention belong to the release
slice. An artifact digest does not pin external model behavior, credentials, or data.

An explicit `enabled: false` blocks new candidate execution and continuation for
that workflow, while allowing authorized historical reads and cancellation. Removing
a mapping returns **new submissions** to normal authoring behavior; it is not a
release-disable operation. Old candidate jobs still resolve their retained bytes.
Source-installation share revocation cannot revoke an exported copy; destination
workflow permissions and mount disablement are the controls on this host.

## Rollout and rollback contract

The feature is opt-in; the default mapping is empty. Deploy the code with candidate
mounts absent, retain the existing durable job schema, and upgrade **all** execution
processes before enabling a mount. All processes must share the same configuration,
durable job database, encryption key, and compatible runtime/package environment.
The initial verification used the existing single-process asyncio executor with
SQLite. The September 16 follow-up below adds actual local PostgreSQL evidence.
Neither local test arrangement establishes deployed-image or scaled Redis worker
support.

Do not run candidate jobs on mixed old/new binaries: older runners do not understand
the candidate marker and could select authoring graphs. Before rolling back to a
pre-candidate binary, stop new submissions and finish or explicitly cancel every
queued/paused candidate job. Keep the compatible binary for retained continuations.
A selection rollback to another archive on this binary does not rewrite old jobs.

Before enabling production traffic, run the candidate matrix on the deployed image,
actual durable database, and live provider, with the intended authentication and
secret provisioning. Preserve the candidate, graph, and agent checkpoint rows
through backup/restore and retention. Verify pause → restart → resume and event
reattachment on that topology. External side effects are not exactly-once: existing
provider/tool retry and approval semantics still apply. No silent migration of
paused runs or blanket production certification is claimed here.

## Verification

Provider models are deterministic substitutes; API routing, authorization, graph
execution, project export, database jobs/checkpoints, signals, and event replay are
real. The fresh-process case starts a separate Python process against the persisted
database, with no original candidate file or in-memory service state.

- Hosted candidate suite: **10 passed**, covering repeated sync/two streams against
  erased drafts; Instructions/context/hooks with skill-scoped reviewed tools;
  approval/rejection; service and fresh-process restart; stale/duplicate decisions;
  unavailable/tampered bytes; disabled mount; end-user isolation; cancellation;
  queued-job recovery; idempotent submission; terminal error replay.
- Shared candidate/checkpoint/standalone/converter selection: **193 passed,
  3 skipped** (the existing opt-in cross-environment artifact-export cases).
- Durable store selection: **19 passed, 16 skipped**. The skips are unavailable
  PostgreSQL cases; SQLite includes atomic job/candidate commit and rollback on
  candidate persistence failure.
- Existing hosted skill/facade/end-user/resume regression: **44 passed, 14 skipped**
  initially, plus one legacy response-shape failure fixed by omitting an unset
  candidate field. The follow-up helper/policy/reconstruction/compatibility selection
  passed **63 tests**, including that corrected response case. Counts overlap.

Remaining production evidence: actual provider calls/streaming and the intended
deployed topology, combined compaction/permission/error variants and sourced artifact
quality, workload thresholds, and release lifecycle/retention. Production verification
now takes priority over starting Eval Suites.

### September 16: PostgreSQL verification correction

The existing background-execution fixture assigned `settings.database_url` directly.
Its validator selected the environment URL or default SQLite instead, so a test
parameter named `postgres` could pass without accessing PostgreSQL. An initial
16-pass run was discarded after an independent connection found the test PostgreSQL
database empty. That result is **not** PostgreSQL evidence.

The fixture now sets the production environment variable for its lifetime and
asserts the engine dialect and complete destination URL before migrations or writes.
A regression test checks the JobService's actual session, queries PostgreSQL's
server version, and reads the committed job through an independent connection.
SQLite now uses its intended temporary database too.

The candidate API suite is parameterized over SQLite and PostgreSQL. Each PostgreSQL
API case creates and deletes its own randomly named database; the supplied test URL
is an administrative connection, never a database to truncate. Its role needs
`CREATEDB`. Tests skip PostgreSQL when `LANGFLOW_TEST_DATABASE_URI` is absent; a
configured but broken database fails. The existing migration CI job now runs these
candidate API cases against its PostgreSQL 16 service as well. That CI change has
not yet been executed remotely.

Reproduce with a disposable PostgreSQL service and the PostgreSQL dependency extra:

```sh
LANGFLOW_UPDATE_STARTER_PROJECTS=false uv run --no-sync pytest \
  src/backend/tests/unit/background_execution -m real_services -k postgres -v
LANGFLOW_UPDATE_STARTER_PROJECTS=false uv run --no-sync pytest \
  src/backend/tests/unit/api/v2/test_workflow_candidates.py -k postgres -v
```

Set `LANGFLOW_TEST_DATABASE_URI` in the environment before either command. The first
command migrates and writes the supplied disposable database; the second creates
isolated databases on that service. Do not point the first command at application
data.

Local verification uses Homebrew PostgreSQL **17.11**, psycopg **3.3.4**, and Python
**3.13**, with deterministic provider replacements:

- **133 passed** in the PostgreSQL background-execution selection, including
  candidate retention, atomic rollback, concurrency, signals, replay, resume,
  deadline handling, orphan reconciliation, and submission deduplication.
- **10 passed** in the PostgreSQL candidate API selection, including a new database
  for each case and approval → fresh Python process → resume with the original
  archive deleted. The application is exercised with ASGI transport, not a deployed
  HTTP proxy/image.
- The earlier **18-pass** focused store/fixture result is included in the 133;
  these counts must not be added together.
- **28 passed** in the SQLite candidate API, store, and fixture regression selection
  after the database fixture changes.

Live-provider acceptance still
needs a selected provider/model and configured credentials. Deployed-topology
acceptance still needs the intended process/worker arrangement and image/runtime.
Neither gate is satisfied by the local PostgreSQL run.
