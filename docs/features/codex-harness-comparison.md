# Codex harness comparison: ideas for the Langflow Agent

This note compares the OpenAI Codex CLI harness with the Langflow Agent harness.
It lists ideas for harness improvements and new components, in recommended order.

- Codex snapshot: `openai/codex` at commit `57b493a` (2026-11-27).
- Langflow snapshot: `main` at commit `ed5f8609b1`.
- Installed LangChain: `langchain 1.3.14`.

## How to read this note

Codex facts come from a code reading of the snapshot. Nobody ran Codex for this note.
Constants can change in later Codex versions.

Langflow facts come from a code reading. A grep over `src/lfx` and `src/bundles` confirmed
that the Agent has no compaction, no tool output limit, and no `cache_control`.

The middleware names in this note import correctly from the installed packages.
Their behavior inside the Langflow Agent is not tested yet.

## Where the Agent is today

The Agent component uses `langchain.agents.create_agent` with a list of middleware.
The list is built in `src/lfx/src/lfx/components/models_and_agents/agent.py` (lines 627 to 672).

- The only context limit is a message count: `n_messages`, default 100.
- The catalog stores `context_window` for each model, but nothing reads it.
- Chat history is replayed as text only. Past tool calls and tool results are not replayed.
- Tool results go to the model at full size.
- `Usage` has `input_tokens`, `output_tokens`, and `total_tokens`. It has no cached-token field.

Most ideas below are one more middleware in that list. That is the main finding:
the harness already has the extension point, so most of the work is wiring and defaults.

## Recommended order

| # | Idea | Type | Ready-made middleware | Estimate |
|---|---|---|---|---|
| 1 | Compaction | Harness | `SummarizationMiddleware` | 1 day |
| 2 | Tool output limit | Harness | None. `ContextEditingMiddleware` covers old results only | 1 day |
| 3 | Prompt caching | Harness | `AnthropicPromptCachingMiddleware` | 2 hours |
| 4 | Cached tokens and context usage in the UI | Harness | None | 1 day |
| 5 | Tool calls in replayed history | Harness | None | 2 to 3 days |
| 6 | Plan and todo tool | Component | `TodoListMiddleware` | 1 day |
| 7 | Tool search | Component | `LLMToolSelectorMiddleware`, `ProviderToolSearchMiddleware` | 2 days |
| 8 | Automatic memory | Component | None. Builds on Memory Base | 1 to 2 weeks |
| 9 | Skills | Component | None | 1 week |
| 10 | Sub-agent with isolated context | Component | None | 2 to 3 days |

Estimates assume one developer and include a focused test.

Items 1 to 3 stop failures and cut cost. Item 4 measures their effect, so it comes before
the larger items. Items 6 to 10 add capability and need product decisions.

## Harness improvements

### 1. Compaction

**Codex.** Codex compacts the history when token usage reaches 90% of the context window.
It also has a manual `/compact` command. The summary is a handoff note for the next model:
progress, decisions, constraints, and next steps. After compaction, Codex keeps the recent
user messages (up to 20,000 tokens) and puts the summary last. A background variant starts
a speculative compaction at 65% so the user does not wait.

**Langflow.** Nothing. A long session exceeds the provider limit and fails.

**Proposal.** Add `SummarizationMiddleware` to the middleware list. Use the model's
`context_window` from the catalog to set the trigger. Add one Agent input to turn it off.

**Related work.** [PR #16515](https://github.com/langflow-ai/langflow/pull/16515) adds a
stored rolling summary of older chat messages between runs. It does not cover overflow
inside one run. See the [compaction PRD](agent-context-compaction-prd.md) for that part.

### 2. Tool output limit

**Codex.** Each model has a truncation policy, 10,000 tokens by default. Codex keeps the head
and the tail of the output and replaces the middle with a marker that says how much it cut.
The full output stays in the session file. Only the live context is truncated.

**Langflow.** Nothing. MCP results, `Data`, and DataFrames go to the model whole.
The only cap is the A2A agent reply at 100,000 characters.

**Proposal.** Truncate tool results in one place before they return to the model, with the
same head-and-tail shape and a marker. Add `ContextEditingMiddleware` to clear old tool
results when the context grows.

### 3. Prompt caching

**Codex.** Codex keeps the prompt prefix stable. It sends a `prompt_cache_key` derived from
the session id. When context changes (instructions, tools, environment), it appends a diff
at the end and does not rewrite earlier content. Compaction requests reuse the same tools
and instructions to keep the cached prefix.

**Langflow.** The system prompt is stable by design, which helps automatic prefix caching
on OpenAI. Anthropic needs explicit `cache_control`, and nothing sets it.

**Proposal.** Add `AnthropicPromptCachingMiddleware` when the model is an Anthropic model.
Then check the OpenAI path for a session-based `prompt_cache_key`.

**Related risk in the Assistant.** The Assistant pastes the history and the canvas summary
into the user message (`agentic/services/assistant_service.py`, lines 204 to 239).
This probably changes the prefix on each turn and defeats caching. This is an inference
and is not measured.

### 4. Cached tokens and context usage in the UI

**Codex.** Codex tracks total usage against the model context window and shows
"% context left" to the user.

**Langflow.** The playground shows input, output, and total tokens. It does not capture
cached tokens and does not compare usage with the context window.

**Proposal.** Add a cached-token field to `Usage` in `src/lfx/src/lfx/schema/properties.py`.
Show cached tokens and context usage in the playground message.

### 5. Tool calls in replayed history

**Codex.** The session file stores every item: messages, tool calls, and tool results.
Resume rebuilds the full history from it.

**Langflow.** `Message.to_lc_message` returns text only. In the next turn the model does not
see which tools ran or what they returned.

**Proposal.** Replay tool calls and tool results from `content_blocks` when the Agent loads
history. Do items 1 and 2 first, because this change adds tokens to every turn.

## New components

### 6. Plan and todo tool

**Codex.** An `update_plan` tool keeps a step list with at most one step in progress.

**Langflow.** Only the Assistant has a planning tool (`ProposePlan`).

**Proposal.** Add `TodoListMiddleware` behind an Agent toggle. Show the plan in the playground.

### 7. Tool search

**Codex.** When a session has many MCP tools, Codex does not load them all. It registers them
as deferred and gives the model a BM25 search tool that returns 8 results.

**Langflow.** All tools load into every prompt.

**Proposal.** Use `LLMToolSelectorMiddleware` or `ProviderToolSearchMiddleware` when the tool
count passes a threshold. This matters most for MCP servers with many tools.

### 8. Automatic memory

**Codex.** A background pipeline reads past sessions in two phases.
Phase 1 extracts a raw memory and a summary from each session.
Phase 2 consolidates them into memory files with a sub-agent.
Each new session gets a memory summary capped at 2,500 tokens, plus tools to search the rest.
The model cites the memories it used. Codex counts those citations and drops memories that
stay unused for 30 days.

**Langflow.** Memory Base already captures flow output and can distill batches with an LLM.
Retrieval is manual: the flow author must wire the `MemoryBase` component.

**Proposal.** Let the Agent load a short memory summary at the start of a session, and expose
Memory Base search as a default tool. Usage counting and forgetting can come later.

### 9. Skills

**Codex.** Only the name, description, and path of each skill go into the prompt, with a
budget of 2% of the context window. The model reads the full `SKILL.md` when it uses the skill.

**Langflow.** Nothing.

**Proposal.** A Skills component that takes a folder or a list of skills and gives the Agent
a catalog plus a tool to load one skill.

### 10. Sub-agent with isolated context

**Codex.** `spawn_agent` controls how much parent history the child inherits.
The child's final message to the parent is capped at 1,000 tokens.

**Langflow.** An Agent can be a tool for another Agent, with no cap on the reply
and no control over inherited history.

**Proposal.** Add a reply cap and a history option to the Agent-as-tool path.

## More ideas, not ranked

- **Project instruction files.** Codex merges `AGENTS.md` files from the project root down,
  with a shared 32 KiB budget.
- **User hooks.** Codex has 14 hook events, such as PreToolUse, PostToolUse, and PreCompact.
  Langflow has internal middleware only.
- **Code mode.** One tool runs JavaScript that calls other tools. Only the printed output
  returns to the model, so intermediate results do not use context.
- **Conversation fork.** Codex can fork a session before a chosen user message.
  Langflow can fork flows, not conversations.
- **Review in a separate context.** Codex runs review in a fresh thread and returns only
  the findings to the parent.
- **History and notes tools.** The model can search its own past history and keep private
  notes that survive a context reset.

## Next step

Wire `SummarizationMiddleware` into the Agent middleware list and test it with a session
that passes the context window of a small model.
