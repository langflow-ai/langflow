# Agent model setup

Agent setup reads provider policy, credentials and connection settings before
constructing the model. These database reads must use `await`: the synchronous
bridge waits on a worker future and can block the Agent's event loop while other
tasks need that loop to release database connections.

## What changes

`AgentComponent._aget_llm()` calls `aget_llm()`, which awaits policy and the
owner's credential/connection-variable lookups, then uses `_build_llm()` for
the existing provider-specific constructor logic. The Agent binds that model
to its attempt while calling `create_agent_runnable()` with the original
arguments. A custom override that calls `super()` reuses the awaited model
without an added required keyword or a second credential resolution. Each
built-in retry resolves its own model afresh. The binding is context-local,
checked against the Agent instance, and reset when construction fails.

`aget_api_key_for_provider()` and `aget_all_variables_for_provider()` contain
the original parsing/fallback logic and its documentation, with database calls
changed to native awaits. The synchronous public functions wrap those async
implementations. There is no separate key-source object or normalization path.

## Code moved from `get_llm()`

| Helper | Existing behavior |
| --- | --- |
| `_select_llm()` | Selection checks and connected-model passthrough |
| `_require_llm_provider()` | Policy checks and canonical provider identity |
| `_validate_llm_api_key()` | Missing-key errors and optional-provider placeholder |
| `_build_llm()` | Provider parameters, reasoning/token settings, retry overrides and final endpoint protection |

The original comments remain alongside these extracted blocks. Policy still
runs before secret access. Known providers use registry wiring rather than
saved class hints; environment fallback retains the request's existing setting.
Database/authentication failures propagate instead of switching to server values.

## Existing synchronous extensions

`async_call_method()` awaits the built-in marked async model method, awaits an
async override, or runs a synchronous override in a worker thread with copied
request context. Owner/receiver checks prevent copied decorator attributes from
bypassing custom behavior.

Legacy Agent selections await model choices through the separate model-picker
PR, which this Agent fix depends on. Native credential and model-choice waits
stay on the caller loop. Cancellation closes their active database sessions.
Live model discovery resolves each enabled provider's declared inputs on that
loop before starting its blocking HTTP work. The synchronous variable helper
in a discovery callback reads an immutable owner-scoped snapshot. Undeclared
inputs and another owner's reads fail closed; callbacks must use that helper
rather than opening database sessions directly.
Custom synchronous extensions still run in worker threads; cancellation cannot
stop code already running inside such a thread.

The model-picker helpers are reviewed in their own prerequisite PR. Language
Model, Tool Calling, Batch Run, Lambda Filter and general component policy
changes are reviewed in a separate follow-up. Generated starter
and catalog source is refreshed for Agent only; existing saved flows need the
ordinary component-update action.

## Release validation and rollout

The first two PRs cover model choices and the built-in Agent's model setup.
They do not include the usage-message changes, other component setup paths or
shared TLS-context optimization from the remaining PRs. Do not describe this
subset as a fix for every component or a measured cluster-wide performance
improvement.

Before release, verify the full and backend distribution artifacts and required
CI checks against the release branch. In a staging flow, update existing Agent
components through the usual component-update action, then exercise saved and
legacy selections, connected models, streaming, tool use, structured output,
retries and cancellation. Compare an otherwise identical deployment and
workload against the release baseline, including latency, event-loop progress,
pool timeouts, provider failures and usage accounting. Local SQLite and local
HTTP regressions verify the failure mechanism but do not substitute for a
matching cluster run or an authenticated real-provider check.
