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

## Auto mode

The Auto variants run the real `lfx.base.memory.session_memory` code and the Agent's Auto middleware
(tool result cap and in-run compaction) on the same store.

- `auto`: the budget from the window of `gpt-4o-mini` (128,000 tokens). High mark 12,000, low mark
  6,000, message cap 4,000.
- `auto_stress`: high mark 2,000, low mark 1,000, message cap 700 (the same ratio as 4,000 to 12,000).
  It forces many folds in one session, for requirement 1.
- `auto_stress_summary`: the same budget, but the fold writes the free-text summary of PR #16515 and
  no facts. This is the A/B test of facts apart from the summary.

The stress variants skip `tool_heavy`, because the history budget does not change one run.

### Two runs, and why

Auto ran twice. Each run is one run for each case.

- **Run 1** found three gaps in the design. The data is kept in the evidence store under `eval/auto_run1/`.
  1. The fold trigger and the send bound were the same number. The fold runs beside the answer, so on
     the turn a fold was due, the messages it folded were in neither the history nor the notes. In
     `pasted_log` the probe landed on that turn and scored 0/4, with all four facts already stored.
  2. One invalid fold reply paused folding for 10 minutes. In `auto_stress/fact_change` the change in
     turn 12 then never reached the facts, and the answer had the old cluster and Postgres version.
  3. Compaction replaced the user request with its summary. `tool_heavy` found the root cause but
     lost the requested reply format and the path, and scored 0/2.
- **Run 2** is after commit `cebe2d6814`, which fixes the three gaps. The eval did not change, except
  that the stress budget got a message cap of 700. Without it the new send bound of high mark plus
  message cap would be 6,000 tokens, three times the stress high mark.

### Recall of early facts

| Session | Last N 100 | Last N 10 | PR #16515 | Auto run 1 | Auto run 2 | Stress, facts run 1 | Stress, facts run 2 | Stress, summary run 1 | Stress, summary run 2 |
|---|---|---|---|---|---|---|---|---|---|
| `long_60` | 0/4 | 0/4, 1 wrong | 4/4 | 3/4 | 3/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| `pasted_log` | 3/4 | 0/4, 2 wrong | 0/4, 1 wrong | 0/4 | 3/4 | 4/4 | 3/4 | 4/4 | 3/4 |
| `fact_change` | 3/3 | 0/3, 1 wrong | 1/3, 2 stale | 3/3 | 3/3 | 1/3, 2 stale | 3/3 | 3/3 | 3/3 |
| Total | 6/11 | 0/11, 4 wrong | 5/11, 3 wrong | 6/11 | 9/11 | 9/11, 2 stale | 10/11 | 11/11 | 10/11 |
| `tool_heavy` | failed | failed | failed | 0/2 (ran) | 2/2 | - | - | - | - |

- `auto/long_60` missed `cluster` in both runs. The fold never extracted `EU-West` as a fact.
- `log_error` is `unknown` for every variant in run 2, also for Last N at 100, which has the full log.
  Run 2 Auto stores the error line as a fact (`orders_service_error`), but the model still answers
  `unknown`.

### Input tokens for each turn (answer calls only, run 2)

| Session | Last N 100 | Last N 10 | PR #16515 | Auto | Stress, facts | Stress, summary |
|---|---|---|---|---|---|---|
| `long_60` | mean 15,046, max 27,337 | mean 2,452, max 2,855 | mean 5,060, max 7,993 | mean 7,287, max 12,565 | mean 1,758, max 2,326 | mean 1,829, max 2,298 |
| `pasted_log` | mean 54,028, max 66,006 | mean 25,415, max 61,097 | mean 25,608, max 61,776 | mean 11,184, max 58,944 | mean 5,443, max 58,944 | mean 5,556, max 58,938 |
| `fact_change` | mean 5,382, max 11,281 | mean 2,267, max 2,969 | mean 4,076, max 7,262 | mean 4,814, max 10,150 | mean 1,538, max 2,280 | mean 1,645, max 2,195 |
| `tool_heavy` | 458,712, failed | same | same | 683,879 in 13 calls, passed | - | - |

The max of `pasted_log` is the turn that pastes the log. That is the current input, not history.

### Cached input tokens for each turn (run 2)

| Session | Last N 100 | Last N 10 | PR #16515 | Auto | Stress, facts | Stress, summary |
|---|---|---|---|---|---|---|
| `long_60` | 72% | 2% | 81% | 93% | 38% | 31% |
| `pasted_log` | 92% | 47% | 79% | 94% | 14% | 8% |
| `fact_change` | 96% | 6% | 92% | 91% | 45% | 42% |
| `tool_heavy` | 80% | 86% | 77% | 74% | - | - |

Auto keeps the prompt prefix stable between folds, so 91% to 94% of its input comes from the cache.
The stress budget folds every two or three turns, so its prefix changes often.

### History tokens sent (estimated at 4 characters for each token, run 2)

| Session | Last N 100 | Last N 10 | PR #16515 | Auto (bound 16,000) | Stress (bound 2,700) |
|---|---|---|---|---|---|
| `long_60` | 33,835 | 3,349 | 9,752 | 15,125 | 2,701 facts, 2,697 summary |
| `pasted_log` | 51,434 | 45,399 | 46,153 | 12,236 | 2,453 facts, 2,702 summary |
| `fact_change` | 13,484 | 3,720 | 8,913 | 12,197 | 2,661 facts, 2,664 summary |

The eval counts the notes after they merge into the next user message, with a `\n\n` join and one
rounding for each message. That is where the 1 or 2 tokens above 2,700 come from. The module's own
count stays under the bound.

### Added latency and summary calls (run 2)

| Session | PR #16515 | Auto | Stress, facts | Stress, summary |
|---|---|---|---|---|
| `long_60` | 5 folds, 27,909 input tokens; added mean 0.16 s, max 5.3 s | 5 folds (2 invalid replies), 30,217 input tokens; added 0 s | 19 folds, 40,711; added max 0.1 s | 24 folds, 47,112; added max 7.3 s |
| `pasted_log` | 0 folds | 1 fold, 8,345; added 0 s | 6 folds, 14,913; added max 1.4 s | 6 folds, 11,742; added max 5.0 s |
| `fact_change` | 1 fold, 5,059; added 0 s | 1 fold, 5,466; added 0 s | 7 folds, 13,625; added 0 s | 7 folds, 15,052; added max 6.3 s |
| `tool_heavy` | failed | 1 compaction; answer 39.9 s against 16 s before the failure | - | - |

Answer time is 5 to 6 seconds for each chat turn in every variant.

### Fact quality (PRD risk 1)

- **Wrong facts in answers:** 0 for Auto in run 2. In run 1 the stress variant answered with 2 stale
  facts, because folding paused after one invalid reply.
- **Missed facts:** `cluster=EU-West` in `auto/long_60`, in both runs.
- **Noise:** the stress runs fill the list with one fact for each troubleshooting step
  (`issue_4` to `issue_16`, `payments_api_exit_code`, and so on). Run 1 stored the distractor
  `checkout_web_old_runbook: PRJ-090`, and run 2 stored `vendor_contact: Marcus Lee`. The user said
  both are not theirs.
- **Invalid replies:** 2 of 44 fold replies in run 2. Both are from `auto/long_60`, and both are JSON with
  Python `True` in place of `true`.

### Facts against the free-text summary

Under the same token policy and the same stress budget, facts kept apart from the summary do not beat
the free-text summary. Run 1: summary 11/11, facts 9/11. Run 2: 10/11 each. The facts add an invalid
reply rate, noise in the list and one missed fact. The free-text summary folds a little more often
and costs 2% to 7% more input tokens for each turn.

The gain over PR #16515 comes from the token policy, not from facts: a fold that a token mark
triggers, a bounded send window that keeps every unfolded message, and the tool result cap and
in-run compaction for one run.

## Providers and the fold reply (PRD risk 2)

A separate probe sends two folds of `fact_change` to each model. The second batch holds the change.
Only an OpenAI key was available. Ollama ran in Docker on CPU.

| Model | Valid JSON replies | Facts after two folds |
|---|---|---|
| `gpt-4o-mini` | 2/2 | Correct: `cluster: US-East`, `db_version: Postgres 16`, `customer: Initech`. No stale value |
| `gpt-4.1-nano` | not run | OpenAI returned 404: the model is deprecated |
| `qwen2.5:1.5b` (Ollama) | 2/2 | Not useful: one fact, `exit_code_137: OOM condition`, which is an assistant guess. Customer, cluster and version are lost |
| `llama3.2:3b` (Ollama) | not run | Timed out after 600 seconds on CPU |

In the eval, `gpt-4o-mini` returned 2 invalid replies of 44, both with Python `True`.

- Tolerant parsing accepts fences and text around the JSON. It does not repair `True`.
- A small local model returns valid JSON with poor facts. A free-text summary has the same quality
  limit, but a bad summary does not stay in a list that code keeps across folds.
- In the second fold, `gpt-4o-mini` put `cluster` in both `set` and `remove`. The merge applies
  `remove` first, so the new value stays.

## Run 3: the free-text summary design

After run 2, phase 4 was replaced: the fold writes the free-text summary of PR #16515, and the JSON
facts, the merge and Pinned Keys are gone. Run 3 measures that design once, with the same eval. The
raw data is in the evidence store under `eval/auto_run3/`.

| Session | Auto run 2 (facts) | Auto run 3 (summary) | Stress run 3 (summary) |
|---|---|---|---|
| `long_60` | 3/4 | 4/4 | 4/4 |
| `pasted_log` | 3/4 | 3/4 | 4/4 |
| `fact_change` | 3/3 | 3/3 | 3/3 |
| Total | 9/11 | 10/11 | 11/11 |
| `tool_heavy` | 2/2 | 2/2 | - |

| Measure (run 3, Auto) | `long_60` | `pasted_log` | `fact_change` |
|---|---|---|---|
| Mean input tokens for each turn | 6,888 | 11,235 | 4,880 |
| Cached share of input | 90% | 59% | 91% |
| Largest history sent (bound 16,000) | 12,970 | 12,383 | 12,163 |
| Folds (fold input tokens) | 4 (22,415) | 1 (8,265) | 1 (5,277) |
| Added latency | 0 s | 0 s | 0 s |

No invalid fold reply is possible now: any reply that is not empty is a summary.

The stress `pasted_log` run sent 2,716 history tokens against a bound of 2,700. The cap marker in the
middle of a cut message adds about 15 tokens, and the budget counted only the cap. The next commit
counts the marker too. This also explains the 1 or 2 tokens above the bound in run 2.
