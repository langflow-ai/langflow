# Eval: session memory and context budget for the Agent

This note records the eval from phase 1 of the
[PRD](agent-context-compaction-prd.md). The script lives in
`scripts/evals/agent_session_memory/`.

## Method

- **Model:** `gpt-4o-mini`, temperature 0, through `langchain.agents.create_agent`, as in the
  Agent component. The history goes through the Agent's own `build_initial_messages`.
- **Store:** an in-memory message list with the same calls as `lfx.memory`.
- **Runs:** one run for each variant and session. The variants run in parallel.
- **Score:** the last turn asks for facts as `key=value` lines. Each key is correct, unknown,
  stale (an old value) or wrong (any other value). The tool session passes when the reply has the
  root cause and all 12 services of the path.
- **Cached tokens:** `input_token_details.cache_read` as OpenAI reports it.
- **Added latency:** the time the turn waits for the fold after the answer is ready.

### Sessions

| Session | Turns | What it tests |
|---|---|---|
| `long_60` | 60 | Facts in turn 1, 58 troubleshooting turns with distractors, then a probe. This is the scenario of issue #15799. |
| `pasted_log` | 15 | Facts in turn 1, a pasted log of about 42,000 tokens in turn 3, then a probe for the facts and for the last log line. |
| `fact_change` | 24 | Facts in turn 1 that change in turn 12. The probe must return the new values. |
| `tool_heavy` | 1 | One run that follows a chain of 12 services. Each tool result is about 13,000 tokens. |

## Baseline: Last N at 100, Last N at 10, PR #16515

PR #16515 runs with `n_messages=10` and its switch on, as the issue suggests.
The PR code is a copy of its compressor at commit `470605f47d`, with storage moved to the eval store.

### Recall of early facts

| Session | Last N 100 | Last N 10 | PR #16515 |
|---|---|---|---|
| `long_60` | 0/4 | 0/4, 1 wrong | 4/4 |
| `pasted_log` | 3/4 | 0/4, 2 wrong | 0/4, 1 wrong |
| `fact_change` | 3/3 | 0/3, 1 wrong | 1/3, 2 stale |
| `tool_heavy` | failed | failed | failed |

### Input tokens for each turn (answer calls only)

| Session | Last N 100 | Last N 10 | PR #16515 |
|---|---|---|---|
| `long_60` | mean 15,046, max 27,337 | mean 2,452, max 2,855 | mean 5,060, max 7,993 |
| `pasted_log` | mean 54,028, max 66,006 | mean 25,415, max 61,097 | mean 25,608, max 61,776 |
| `fact_change` | mean 5,382, max 11,281 | mean 2,267, max 2,969 | mean 4,076, max 7,262 |
| `tool_heavy` | 458,712 before the failure | same | same |

### Cached input tokens for each turn

| Session | Last N 100 | Last N 10 | PR #16515 |
|---|---|---|---|
| `long_60` | mean 10,816 (72%) | mean 53 (2%) | mean 4,111 (81%) |
| `pasted_log` | mean 49,929 (92%) | mean 11,921 (47%) | mean 20,113 (79%) |
| `fact_change` | mean 5,152 (96%) | mean 133 (6%) | mean 3,744 (92%) |

### Added latency and summary calls

| Session | Last N 100 | Last N 10 | PR #16515 |
|---|---|---|---|
| `long_60` | none | none | 5 folds, 27,909 fold input tokens. Added latency mean 0.16 s, max 5.3 s |
| `pasted_log` | none | none | 0 folds |
| `fact_change` | none | none | 1 fold, 5,059 fold input tokens. No added latency |

Answer time is about 5 to 6 seconds for each turn in every variant. The tool run takes about
16 seconds before it fails.

### What the baseline shows

- **Last N at 100 loses turn 1 at 60 turns.** The window holds 100 messages, and the session
  has 118 before the probe. It also pays the most: a mean of 15,046 input tokens for each turn.
- **Last N at 10 forgets everything early and answers with distractors.** For example, it names
  `Contoso` as the customer and `AP-South` as the region.
- **PR #16515 keeps turn-1 facts in a plain long session** at a third of the cost of Last N at 100.
- **PR #16515 loses facts in two cases.**
  - `pasted_log`: a fold needs 20 messages outside the window, and the session never reaches it.
    The gap holds the log, so it passes 24,000 characters and is dropped. The facts of turn 1 reach
    the model through neither path.
  - `fact_change`: the gap that holds the change in turn 12 passes 24,000 characters and is dropped.
    The summary still has the old values, and the model answers with them.
- **No variant survives the tool run.** The 9th model call needs 130,878 tokens. The window of
  `gpt-4o-mini` is 128,000.
- **History size is not bounded by any variant.** One pasted log puts 45,000 tokens or more into the
  history of PR #16515 and of Last N at 10.

The raw results, one JSON file for each run, are in the evidence store of the worktree under
`eval/baseline/`.
