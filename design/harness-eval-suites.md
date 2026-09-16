# Eval Suites: first execution and review slice

Implemented on `feat/harness-eval-suites`, stacked on `77775b5302` from
`feat/harness-workflow-reliability`. September 16, 2026. No PR is created.

An **Eval Suite** is a project containing cases and a reviewed scorer flow. It
evaluates an exact mounted harness candidate. The desktop page provides case
editing, candidate/scorer selection, retained results and score comparisons.
The subsequent `feat/harness-eval-durability` branch adds background execution,
recovery, cancellation and human approval. See [its contract and evidence](harness-eval-durability.md).
Neither slice certifies the full production release lifecycle.

## Authoring and execution

1. Create an Eval Suite project. Choose an executable candidate mounted on the
   authenticated authoring host. The selected digest is visible in the form.
2. Create a scorer flow. Its baseline connects **Evaluation Input** to
   **Evaluation Result**. Add scoring logic between them and connect its JSON/Data
   judgment to the result's Judgment input. The baseline deliberately has no
   passing default judgment. Ordinary Prompt Template, model, and structured
   output components remain the tools for constructing model-based scorers.
3. Evaluation Input supplies `{ "case": {...}, "response": {...} }`, where
   `response` is the actual v2 Workflows execution response, including its
   outputs and candidate identity. Its editable preview JSON is used only for
   ordinary canvas previews. Suite execution supplies the real payload through
   the reserved `HARNESS_EVAL_INPUT` workflow global.
4. Evaluation Result validates the scorer's judgment:

   ```json
   {
     "score": 0.8,
     "reason": "Explain the assessment against the case and evidence.",
     "claim_support": "supported",
     "policy": "compliant"
   }
   ```

   `score` must be a finite number from 0 to 1. `reason` is required.
   Claim support can be `supported`, `unsupported`, or `not_evaluated`; policy can
   be `compliant`, `violation`, or `not_evaluated`. Omitted optional assessments
   become `not_evaluated`, never an implicit success. Extra fields and malformed
   values fail validation.
5. Save cases, references, score thresholds, artifact/claim/policy requirements
   and optional budgets. Saving resolves permissions and creates server-owned
   FlowVersion references for the scorer and its dependency closure. Caller
   version IDs are not trusted. Keeping the existing selection retains its
   reviewed snapshot even if its canvas draft changes.
6. Run the saved suite. Unsaved edits disable Run. The server checks both the
   suite revision and the expected candidate digest before execution. Both the
   harness and scorer execute using the authenticated Workflows host's existing
   graph execution, policy gates, request scoping and job machinery.

The project API surface is `/api/v1/projects/{id}/evaluations`:

| Method / suffix | Purpose |
| --- | --- |
| GET | Saved config/revision, authorized mounts and compatible local scorer outputs |
| POST `/scorer-baseline` | Prepare the starter graph; ordinary flow creation saves it |
| POST `/runs` | Accept a background run (202) with `run_id`, `expected_revision`, `expected_candidate_digest` |
| GET `/runs` | The caller's latest 20 records in this suite |
| GET `/runs/{run_id}` | Read the caller's retained record and pending approval |
| POST `/runs/{run_id}/cancel` | Persist a cancellation request (202); poll until terminal |

Project configuration still saves through the ordinary project PATCH endpoint.
Execution requires the developer Workflows API to be enabled. Evaluation is an
authoring-host feature; serving end-user identity mode is explicitly rejected.

## What is enforced

- Required claim support must be explicitly `supported`; required policy must
  match the selected outcome. A perfect numeric score cannot override either.
- A required sourced artifact must parse as a SourcedReport, resolve every
  citation to available captured evidence, and belong to the actual workflow's
  flow ID and job ID. A linked citation does not prove claim support: that is a
  separate scorer judgment. The original report's `not_evaluated` claim-support
  field is not rewritten.
- Missing judgments, failed execution, unknown required measurements, invalid
  artifacts and exceeded budgets fail the case. An incomplete parent run cannot
  pass, even if its completed cases passed.
- Scorer output selection requires exactly one Evaluation Input and a reachable
  terminal Evaluation Result with a JSON/Data output. Declared schema checks do
  not certify the scorer's reasoning. Scorers are trusted, reviewed executable
  flows; this is not a sandbox or a guarantee that an LLM judge is correct.
- Authorization is checked for the project, target and scorer dependencies.
  Candidate disablement and current execution rights are checked between cases.
  Request-global header overrides cannot alter a suite run behind its saved
  configuration.

## Retention and comparison

An existing EVALUATION job retains the suite inputs/thresholds, suite revision,
candidate digest and scorer digest. The candidate archive and scorer archive are
committed with that job using existing checkpoints. Each case retains workflow
and scorer job IDs, the workflow response, judgment, elapsed time and failures.
No schema migration or second graph engine is introduced.

Client-generated run IDs make retrying a submission idempotent, including
concurrent submissions. They do not automatically retry failed cases or tool
side effects. If the browser loses the response, it displays the run ID and
directs the user to persisted history before starting a new run.

Comparison requires complete runs with matching suite revision and scorer digest.
The suite revision includes the cases, thresholds, workflow ID and reviewed
scorer/dependencies, but excludes the target candidate digest. Changing only the
candidate permits comparison; changing the rubric or scorer does not.

## Explicit limits and remaining work

- External evaluation-platform integrations (Braintrust, LangSmith and Phoenix
  import/export adapters) are postponed by the user as of September 16, 2026.
  They are not acceptance requirements for this native Eval Suite slice.
- At most **10 cases**. Candidate and scorer execute as durable Workflows children
  in the existing bounded worker pool. Each active child pass has a **300-second**
  ceiling (or a smaller configured background timeout). Queue time and approval
  waiting do not consume that execution budget. There is no suite-wide wall-clock
  deadline or distributed suite admission limit.
- Candidate and scorer approvals are supported through the existing Workflows
  resume endpoint. Completed cases and suspended checkpoints survive restarts.
  An interrupted in-flight child fails the evaluation; it is not automatically
  re-executed because its tools may already have acted.
- The candidate's elapsed wall time includes queueing and human approval waiting.
  The optional elapsed budget assesses that value; it is not an execution timeout.
  Provider cost remains **unavailable**. A cost requirement fails closed.
- Responses are retained up to 48 KB each. A larger response fails the case.
  Combined case/reference/response must fit the Workflows global's 64 KiB
  character limit. Larger evidence needs an artifact-reference scoring protocol.
- Generic project import/export refuses Eval Suites instead of copying stale
  candidate/snapshot IDs. Portable suite archives with retained scorer and
  candidate references remain work.
- Live-provider acceptance remains open. Deployed-topology verification is
  deferred at the user's request. The durability follow-up verifies the evaluation lifecycle on local SQLite and
  PostgreSQL. That does not establish the intended deployed topology.
- Evaluation-gated promotion, release retention and rollback follow after these
  evaluation limits are addressed for the intended production profile.

## Original slice verification

These results describe `5cef7a9917`. Current durability verification is recorded
in [the follow-up](harness-eval-durability.md).

- 13 real API/graph tests with deterministic provider replacement: frozen
  candidate and scorer after draft edits; persisted history; repeated and
  concurrent submission; thresholds and missing measurements; stale selections;
  forged scorer versions; unsupported claims; policy violations; malformed
  judgments; timeout; approval preflight; cross-user isolation; generated sourced
  artifacts; refusal of unsafe generic suite archives.
- 42 shared contract/registry tests cover invalid scores, required assessments and artifact
  execution/citation mismatches. Registry tests cover the new built-in type.
- 55 frontend tests cover save-before-run, exact revision/digest submission, missing
  cost guidance, lost-response handling, incompatible comparisons and rendering
  failure evidence. Existing harness form regressions remain included.
- The adjacent project-config/archive/type run passed 50 tests and exposed three
  stale Skill Pack form expectations. All three also failed on the untouched
  base checkout; their corrected assertions pass in a targeted follow-up.
- Desktop browser smoke on an isolated local database: opened the suite, created
  its scorer on the canvas, returned to the suite, selected and saved the scorer.
  No provider run was made by this UI smoke.
- Typecheck compared against a fresh archive of the branch's base: 255 diagnostics
  at both ends, with identical messages after normalizing the temporary checkout
  path. The repository-wide typecheck is still not clean.

Reproduction (from the repository root):

```sh
LANGFLOW_UPDATE_STARTER_PROJECTS=false uv run --no-sync pytest \
  src/backend/tests/unit/api/v1/test_eval_suites.py -q
cd src/frontend
npx jest src/pages/MainPage/pages/harnessPage/__tests__/eval-suite.test.tsx \
  src/pages/MainPage/pages/harnessPage/__tests__/harness-page.test.tsx --runInBand
```
