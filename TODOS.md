# TODOS

Deferred work captured during engineering reviews.
Format: What / Why / Context / Depends on

---

## Custom AI Provider Management (added 2026-03-21)

### TODO-1: Per-user TTL cache for list_models custom provider query

**What:** Cache `list_for_user(user_id)` results with a ~60s TTL so repeat `GET /api/v1/models/`
requests don't hit the DB for users with no custom providers.

**Why:** `GET /api/v1/models/` is now dynamic (DB query per user). Currently fast for users with
0–5 custom providers, but worth revisiting if load testing reveals latency at scale.

**Pros:** Eliminates repeat indexed scans for the same user in a short window.

**Cons:** Requires cache invalidation on POST/PATCH/DELETE to `/custom-providers/`. Adds complexity
for a query that's currently ~1ms.

**Context:** Start in `models.py` after profiling shows this is a measurable bottleneck. Don't
build until you have evidence. The `list_for_user()` call is in
`src/backend/base/langflow/api/v1/models.py` in the `list_models` handler, after
`replace_with_live_models()`.

**Depends on:** Custom provider v1 shipped and load-tested.

---

### TODO-2: Workspace-level custom provider sharing

**What:** Allow org admins to define a custom provider once and share it across all users in a
workspace (or org). Currently custom providers are per-user only.

**Why:** Enterprise target users (Azure OpenAI with private deployments, internal model gateways)
will want IT to configure the provider once, not require every user to set it up.

**Pros:** Unlocks the primary enterprise use case. Per-user scope (v1) is intentional but the
follow-up is predictable.

**Cons:** Requires new `workspace_custom_provider` table, admin vs. user permission model, and
settings UI for workspace-level management. Significant scope.

**Context:** Approach C from the design doc (data-driven providers — all providers from DB) is the
right long-term architecture; workspace sharing is the v2 wedge toward that end-state. Review
the design at `~/.gstack/projects/langflow-ai-langflow/dak-HEAD-design-20260321-120737.md`
(§ Approach C) before starting.

**Depends on:** v1 custom provider shipped and gathering enterprise feedback.

---

### ~~TODO-3: Confirm run_until_complete() mechanism for nested event loop safety~~ ✅ RESOLVED 2026-03-21

**Finding:** `run_until_complete` lives in `src/lfx/src/lfx/utils/async_helpers.py` and already
handles nested event loops correctly via thread-based fallback:

```python
def run_until_complete(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)          # No loop → fresh loop
    # Loop already running → new thread with its own loop
    def run_in_new_loop():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        return executor.submit(run_in_new_loop).result()
```

- `nest_asyncio` is NOT used anywhere in the codebase
- Already imported at `unified_models.py:28` — custom provider branch just calls
  `run_until_complete()` directly, same as `get_api_key_for_provider()` at line 433
- Safe in pytest-asyncio, FastAPI handlers, and background tasks
