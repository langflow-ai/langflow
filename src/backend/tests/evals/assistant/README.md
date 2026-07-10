# Langflow Assistant eval suite

Gating evals for the Assistant flow builder. **Any change to `FLOW_BUILDER_PROMPT`
(`src/backend/base/langflow/agentic/flows/flow_builder_assistant.py`) or to the intent
classifier (TranslationFlow / `classify_intent`) MUST run this suite before AND after the
change, and the after-run must show no pass-rate regression per scenario.** LLM output is
non-deterministic, so a single green run proves capability (pass@k), not stability — use
`--repeat 3` (or more) and compare pass rates, not single outcomes.

## What it is (and is not)

- A **plain runner package**, deliberately NOT a pytest suite: `runner.py` / `scenarios.py`
  contain no `test_*` functions, so neither `make unit_tests` nor a default `uv run pytest`
  collects them. LLM calls never sneak into CI.
- Pass criteria are **objective and structural**: node types present, edge shapes (e.g. a
  loop feedback edge has an output-shaped `targetHandle` with `name` instead of
  `fieldName`), event presence (`flow_update` forbidden on Q&A / off-topic), a single
  attempt, no `error` events, and generous token/duration budgets that act as regression
  tripwires — not tight SLAs.
- The harness itself IS unit-tested deterministically (no LLM) in
  `src/backend/tests/unit/evals/test_assistant_eval_checks.py`, which runs in the normal
  unit suite and proves every check catches the failure class it claims to.

## 1. Start a dev backend

From the repo root (the repo `.env` must contain a valid `OPENAI_API_KEY`):

```bash
EVAL_DIR=$(mktemp -d)
LANGFLOW_DATABASE_URL="sqlite:///$EVAL_DIR/eval.db" \
LANGFLOW_CONFIG_DIR="$EVAL_DIR/cfg" \
LANGFLOW_AUTO_LOGIN=true \
LANGFLOW_DEACTIVATE_TRACING=true \
uv run --no-sync uvicorn --factory langflow.main:create_app \
  --host 127.0.0.1 --port 7899 --env-file .env --loop asyncio
```

Any free port works — pass it via `--base-url` or `LANGFLOW_EVAL_BASE_URL`.
A throwaway SQLite DB keeps eval flows out of your real workspace.

## 2. Run the suite

From `src/backend`:

```bash
cd src/backend
uv run --no-sync python -m tests.evals.assistant.runner --repeat 3
```

Useful flags:

- `--list` — list scenarios and exit.
- `--scenario simple_build --scenario loop_flow` — run a subset (repeatable flag).
- `--base-url http://127.0.0.1:7913` — non-default backend (or `LANGFLOW_EVAL_BASE_URL`).
- `--model gpt-5.5 --provider OpenAI` — assistant model (defaults; or
  `LANGFLOW_EVAL_MODEL` / `LANGFLOW_EVAL_PROVIDER`).
- `--report path/to/report.json` — report location (default
  `assistant_eval_report.json` in the current directory; or `LANGFLOW_EVAL_REPORT`).

Exit code is `0` when every scenario passed at least once (pass@k — capability), `1`
when any scenario had zero passing runs.

## 3. Read the report

The JSON report contains, per scenario: `pass_rate`, `pass_at_k` (any run passed —
capability), `pass_all_k` (every run passed — stability), `avg_tokens`, `avg_duration`,
every failure reason, and a `runs_detail` list with per-run tokens, duration, event
counts, and the backend's `verified` flag (informational — flow verification can fail for
environment reasons, so it does not gate).

## 4. The gating rule

1. **Before** touching `FLOW_BUILDER_PROMPT` or the classifier: run
   `--repeat 3`, commit/keep the report as the baseline.
2. **After** the change: run the identical command against a backend running the new code.
3. **Gate:** no scenario's pass rate may drop vs. the baseline, and no scenario may lose
   `pass_at_k`. Token/duration budget failures count as regressions (they are ceilings on
   cost creep). A genuinely flaky scenario is a finding — fix the prompt or tighten the
   scenario, never delete it to go green.
4. New assistant failure modes become new scenarios (regression evals), permanently.

## Current baseline (2026-07-08, gpt-5.5, single run + loop retries)

10/10 scenarios pass (loop_flow 3/3 on `--repeat 3`). Observed costs sit far below the
ceilings (simple_build ~61k tokens / 14s; if_else_flow ~54k / 11s; loop_flow ~69k / 19s;
off_topic ~4k / 2.2s).

Resolved failure (kept as a regression note): `loop_flow` was 0/3 — the agent hit the
recursion limit ("The agent ran out of steps before finishing") because the prompt's
canonical loop recipe named legacy components (`ParseData`, `MessagetoData`) that
`search_components` hides, and did not cover the Message-consuming body head, so
`L.item -> Agent.input_value` failed on a type mismatch and the agent burned its step
budget re-discovering components. Fixed by modernizing the recipe (ParserComponent
between `Loop.item` and the Agent), adding a deterministic converter hint to the
type-mismatch error, and an anti-churn retry instruction on `build_flow` failures.
`TestFlowBuilderPromptLoopRecipe` pins the recipe to the live registry.

Note: run the eval backend with `LANGFLOW_DEACTIVATE_TRACING=true` if your `.env`
carries partial `LANGFUSE_*` configuration — otherwise the Q&A path can crash with
`LangfuseResourceManager.__new__() missing 3 required keyword-only arguments`.

## Scenarios

Run `--list` for the live list. Coverage: simple build, persona (system_prompt
population), edit-existing-field, model swap, loop flow (LoopComponent + feedback edge),
if-else flow (ConditionalRouter with both branches wired), compound build+describe,
plain question (no canvas mutation), off-topic refusal, short-input robustness.
