# PRD: session memory and context budget for the Agent component

Status: draft, not implemented.
Issue: [#15799](https://github.com/langflow-ai/langflow/issues/15799).
Related: [PR #16515](https://github.com/langflow-ai/langflow/pull/16515),
[Codex harness comparison](codex-harness-comparison.md).

## Decision

Give the Agent one context policy, measured in tokens, over a stored session summary.

The Agent gets a chat history mode named **Auto**. In Auto, the Agent keeps a fact list
and a short summary for the session, sends recent messages as they are, and keeps the
history under a token budget. The flow author does not tune a message count.

This plan keeps the storage design of PR #16515 and replaces its policy.
Nothing in this plan is measured yet. The numbers are start values, and the eval in
phase 1 sets the final ones.

## Problem

From issue #15799. The Agent sends the newest `n_messages` rows (default 100) on every
model call.

1. A long session pays for 100 raw messages on every call.
2. The limit counts rows. It ignores size, so a pasted log and "ok" cost one row each.
3. Messages older than the window are dropped with no trace. Early facts are lost.
4. One setting trades cost against memory.
5. Inside one run, tool results can pass the model context window, and the run fails.
   This problem is not in the issue. It comes from the harness comparison.

## Goals

1. The Agent recalls facts from the start of a session after any number of turns.
2. History cost for each model call has a token bound that does not grow with the session.
3. A run does not fail because the context passed the model window.
4. Auto mode needs no tuning. Existing flows do not change.

## What "good and scalable" means here

Each rule is a check that the design must pass.

1. **Bounded.** Every model request has a token bound, for any session length and any
   tool result size.
2. **One source of truth.** The message table holds the conversation. The summary is
   derived data that can be rebuilt from it.
3. **Stateless workers.** No correctness depends on memory in one process.
4. **Cheap.** One model call for each fold. Between folds, the prompt only grows at the
   end, so the provider prompt cache keeps working.
5. **Fail open.** When a fold or a compaction fails, the turn still runs.
6. **One unit.** Every limit is in tokens.

## Design

### 1. The history for one turn

No model call happens on this path.

```text
[ facts + summary ]  +  [ messages after the cursor, as they are ]  +  [ current input ]
```

- The **cursor** marks the last message that the summary covers.
- Facts and summary travel as one user-role message, marked as background notes and not
  instructions. They merge into the next user message, so no provider sees two user
  messages in a row. The system prompt does not change.
- When the messages after the cursor do not fit the budget, the Agent sends the newest
  ones that fit. This keeps the bound while a fold is late or failing.
- One message above the message cap is cut to its head and tail in the model input.
  The stored row does not change.

### 2. The budget

| Value | Start value | Meaning |
|---|---|---|
| High mark | The smaller of 20% of the model window and 12,000 tokens | A fold is due above this |
| Low mark | Half of the high mark | A fold brings the unfolded messages down to this |
| Message cap | 4,000 tokens | Largest size of one history message in the model input |
| Unknown window | High mark of 8,000 tokens | Auto works for every model |

Tokens are estimated at 4 characters for each token. Codex and the Langflow token
callback use the same estimate. No tokenizer dependency is added.

The gap between the two marks is the reason for two values. The history grows at the end
from the low mark to the high mark, and the prompt prefix stays the same for all those
turns. One fold then resets it.

The absolute cap matters as much as the share. A model with a window of 1,000,000 tokens
must not carry 200,000 tokens of history on each call.

### 3. The fold

- **When:** the unfolded messages pass the high mark.
- **What:** the oldest unfolded messages, enough to return to the low mark. One fold
  reads a bounded number of tokens. A large backlog drains over several turns.
- **Where:** beside the answer, as a background task in the run. The run waits for it at
  the end. This answers question 1 of the issue.
- **Model:** the Agent's model, with streaming off. This answers question 2.
- **Failure:** the turn keeps the previous state, and folding pauses for that session.

### 4. Facts apart from the summary

A summary that the model rewrites on every fold can lose early facts after many folds.
The design keeps facts out of that rewrite.

The summarizer returns three things:

```json
{"set": {"project": "PRJ-123", "cluster": "EU-West"}, "remove": ["old_key"], "summary": "..."}
```

Code merges `set` and `remove` into the stored fact list. The model never rewrites the
list as a whole. `summary` replaces the previous summary and stays under 300 words.

- Limits: 40 facts, 64 characters for a key, 200 characters for a value.
- Above the limit, the fact with the oldest update goes first.
- **Pinned keys** are an optional Agent input, for example `project_id, customer`.
  A pinned fact is never evicted. This is the pinned keys feature of the issue.
- A reply that is not valid counts as a failed fold.

### 5. Storage

One table, `session_memory_state`, one row for each flow, owner, session and context.
This is the table of PR #16515 with one more column for facts.

- Columns: scope, `facts` (JSON), `summary`, cursor message id and timestamp, `version`.
- Writes use compare-and-swap on the row id and `version`. No lock is held during the
  model call.
- An edit, delete or move of a folded message deletes the row. The next turns fold again
  from the start. Deleted content must not stay in facts or summary.
- Session delete, flow delete and the erase steps remove the row.
- Message rows are not changed. Facts and summary do not appear in the playground,
  in raw history or in Memory Base ingestion.
- Standalone `lfx`, with no Langflow database, uses the Last N mode.

Two other storage designs were rejected:

- **A hidden summary row in the message table.** Every reader of the table would need a
  filter, and the issue forbids changes to message rows.
- **A LangGraph checkpointer for each session.** It is a second copy of the conversation.
  Playground edits, session rename, erase and the Message History component would not
  reach it.

### 6. The guard inside one run

Two parts keep one run under the model window.

- **Tool result cap.** Each tool result is cut to 10,000 tokens before it enters the run
  state. The head and the tail stay, with a marker in the middle that states how much was
  cut. The UI and the stored message keep the full result.
- **In-run compaction.** `SummarizationMiddleware` (in the installed `langchain 1.3.14`)
  in the Agent middleware list. Trigger: 80% of the model window. Keep: the newest 25% of
  the window, in tokens. Summary input limit: 60% of the window. It uses the same
  streaming-off model and the same summary format as the fold, plus a "Work in progress"
  block for tool state.

The in-run summary is not stored. It covers tool calls and tool results, which the
message table does not hold as history. When the model window is unknown, in-run
compaction is off and the tool result cap still applies.

### 7. The control

One advanced dropdown on the Agent, **Chat History Mode**:

- **Last N Messages:** the behavior of today. Default, so existing flows do not change.
- **Auto:** this design. `n_messages` is hidden. Pinned Keys is shown.

`n_messages = 0` still turns memory off in the Last N mode. The fold size and the word
budget stay internal. This answers question 3 of the issue.

## How this maps to the issue

| Problem in the issue | Answer in this design |
|---|---|
| Every call carries 100 raw messages | History stays between the low mark and the high mark |
| The limit counts rows, not size | Every limit is in tokens, and one message has a cap |
| Older messages are dropped | They fold into facts and summary |
| No session-level state | `session_memory_state` |
| One setting trades cost against memory | Auto mode has no message count |
| Messages between the window and Memory Base are invisible | The summary covers every message before the cursor |
| Key facts depend on a model search | Facts travel on every turn |

## How the design scales

| Dimension | How it holds | Limit |
|---|---|---|
| Session length | One state row and a bounded message read for each turn. The message table has an index on flow, session and timestamp | A reset on a long session needs several turns to fold again |
| Message and tool result size | Message cap and tool result cap | Images and binary content are not capped |
| Concurrent runs and workers | Compare-and-swap on the state row. In-run state belongs to one run | A fold-failure pause held in process memory applies to one worker only |
| Cost | One model call for each fold. Folds get rarer as messages get shorter | A session of very long messages folds often |
| Prompt cache | The prompt only grows at the end between folds | Each fold changes the prefix once |
| Latency | The fold runs beside the answer | The run waits for the fold at the end. In-run compaction blocks one model call |
| Agents that share a session | One state row and one cursor for the session | Agents with different models apply their own budget on read, and share the facts |

## Requirements

**Must**

1. In Auto, a fact from turn 1 is recalled after 10 folds.
2. In Auto, the history tokens of every model call stay under the high mark plus the
   message cap.
3. A failed fold does not fail the turn.
4. Deleted or edited message content does not stay in facts or summary.
5. No tool result enters the model input above its cap.
6. Fold and compaction text does not appear in the chat stream as part of the answer.
7. Token usage of each fold and compaction is part of the usage shown for the message.
8. Flows in the Last N mode run no new queries on the history path.
9. Each fold and compaction writes one log event with tokens before, tokens after and
   duration. Message content is not logged.

**Should**

10. The playground message shows that a fold or compaction happened.
11. Tool approval (human in the loop) still pauses and resumes after a compaction.

## Non-goals

- A LangGraph checkpointer for each session.
- Replay of tool calls and tool results between runs.
- A separate, cheaper model for summaries.
- A queue or worker service for folds.
- The same mode on the Message History component. This is question 4 of the issue and
  is a follow-up.
- The Langflow Assistant's in-process conversation buffer. It can move to this design later.
- Memory across sessions. Memory Base keeps that role.

## Phase 1: the eval

The design choices in this PRD are judgments. The eval turns them into numbers before
the policy is built.

- **Input:** scripted sessions. For example: 30 turns with facts in turn 1, a session
  with a pasted log, a session where a fact changes, and a tool-heavy run.
- **Compared:** Last N at 100, Last N at 10, PR #16515, and Auto.
- **Measured:** recall of early facts, input tokens for each turn, cached tokens for each
  turn, added latency, and the number of summary calls.
- **Limit:** one run for each case. It is a script, not a CI suite.

The eval decides the start values in the budget table and whether facts apart from the
summary beat a free-text summary.

## Rollout

| Phase | Work | Estimate |
|---|---|---|
| 1 | Eval script and baseline numbers | 2 days |
| 2 | Tool result cap | 1 day |
| 3 | Storage, token budget and fold | 4 to 5 days |
| 4 | Facts, merge and pinned keys | 2 to 3 days |
| 5 | In-run compaction | 2 days |
| 6 | Retry one model call after a provider "context too long" error | 2 to 3 days |

One PR for each phase. Estimates are guesses for one developer, with no spike behind them.
Phase 2 depends on nothing and can start with phase 1.

## Risks to test first

1. **Fact quality.** A model can return noisy or wrong facts, and code then keeps them.
   The eval must count wrong facts, not only recalled ones.
2. **Structured reply.** Not every provider returns valid JSON. Decide between native
   structured output and tolerant parsing after a test on three providers.
3. **Model window lookup.** It is not known how many Langflow providers return
   `model.profile` with `max_input_tokens`, or whether the Agent can reach catalog
   metadata at run time.
4. **Human in the loop.** A compaction replaces the messages in a checkpointed state.
5. **WatsonX.** The Agent adds two WatsonX middleware. Test the order with the new one.

## Open decisions

1. **PR #16515.** Ship it as it is and build this design as its next version, or hold it
   and rework the policy first. Shipping first means the mode changes later for flows
   that turned the switch on.
2. **Default for new flows.** Last N today. Auto can become the default after the eval.
3. **Pinned keys in the first release,** or after facts prove their value in the eval.

## Next step

Write the four scripted sessions for the eval and run them against Last N at 100 for the
baseline numbers.
