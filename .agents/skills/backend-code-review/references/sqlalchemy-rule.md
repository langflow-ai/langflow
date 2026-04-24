# Rule Catalog — SQLAlchemy Patterns

## Scope
- Covers: SQLAlchemy/SQLModel async session and transaction lifecycle, query construction, user scoping, raw SQL boundaries, write-path concurrency safeguards, and async-specific pitfalls.
- Key modules:
  - Session management (canonical source): `lfx.services.deps.session_scope`, `lfx.services.deps.session_scope_readonly`
  - Langflow wrappers (delegates to lfx): `langflow.services.deps.session_scope`, `langflow.services.deps.session_scope_readonly`
  - Injectable dependencies: `lfx.services.deps.injectable_session_scope`, `lfx.services.deps.injectable_session_scope_readonly`
  - Database service: `langflow.services.database.service.DatabaseService`
  - Model CRUD functions: `src/backend/base/langflow/services/database/models/*/crud.py`
- Import preference: Use `from langflow.services.deps import session_scope` in Langflow code for consistency. The Langflow wrappers are thin `@asynccontextmanager` functions that delegate to `lfx.services.deps`. Only import directly from `lfx` when working inside the `lfx` package itself.
- Does NOT cover: table/model schema and migration design details (handled by `db-schema-rule.md`).

## Rules

### Use `session_scope()` context manager with explicit transaction awareness
- Category: best practices
- Severity: critical
- Description: Langflow uses async sessions exclusively. The `session_scope()` context manager provides auto-commit on successful exit and auto-rollback on exception. For read-only paths, use `session_scope_readonly()` which skips commit overhead. In route handlers, use the injectable variants via `Depends(injectable_session_scope)`. Missing commits can silently drop intended updates, while ad-hoc or long-lived transactions increase contention and deadlock risk.
- Suggested fix:
  - For write operations in services/CRUD: use `async with session_scope() as session:` which auto-commits on success.
  - For read-only operations: use `async with session_scope_readonly() as session:` to avoid unnecessary commit calls.
  - In route handlers: use `session: AsyncSession = Depends(injectable_session_scope)` for writes or `Depends(injectable_session_scope_readonly)` for reads.
  - Keep transaction windows short: avoid network I/O, heavy computation, or unrelated work inside the session scope.
- Example:
  - Bad:
    ```python
    # Creating a raw session without the context manager
    from sqlmodel.ext.asyncio.session import AsyncSession
    from langflow.services.deps import get_service

    db_service = get_service(ServiceType.DATABASE_SERVICE)
    session = AsyncSession(db_service.engine)
    flow = (await session.execute(select(Flow).where(Flow.id == flow_id))).scalar_one()
    flow.name = "Updated"
    # Missing commit, session never closed properly
    ```
  - Good:
    ```python
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        flow = (await session.execute(select(Flow).where(Flow.id == flow_id))).scalar_one()
        flow.name = "Updated"
        # session_scope auto-commits on successful exit

    # For read-only operations:
    from langflow.services.deps import session_scope_readonly

    async with session_scope_readonly() as session:
        flows = (await session.execute(select(Flow).where(Flow.user_id == user_id))).scalars().all()
    ```

### Enforce `user_id` scoping on user-owned queries
- Category: security
- Severity: critical
- Description: Reads and writes against user-owned tables must be scoped by `user_id` to prevent cross-user data leakage or corruption. Langflow uses `user_id` (not `tenant_id`) for user-scoped data isolation. Every query on user-owned entities (flows, variables, folders, messages, API keys) must include a `user_id` filter.
- Suggested fix: Add `user_id` predicate to all user-owned entity queries and propagate user context through service interfaces. The `current_user.id` is available from the `get_current_active_user` dependency in route handlers.
- Example:
  - Bad:
    ```python
    # Missing user_id scope: any authenticated user can read any flow
    stmt = select(Flow).where(Flow.id == flow_id)
    flow = (await session.execute(stmt)).scalar_one_or_none()
    ```
  - Good:
    ```python
    stmt = select(Flow).where(
        Flow.id == flow_id,
        Flow.user_id == current_user.id,
    )
    flow = (await session.execute(stmt)).scalar_one_or_none()
    ```

### Prefer SQLAlchemy/SQLModel expressions over raw SQL
- Category: maintainability
- Severity: suggestion
- Description: Raw SQL via `text()` should be exceptional. ORM/Core expressions are easier to evolve, safer to compose, dialect-portable (SQLite + PostgreSQL), and more consistent with the codebase. Langflow uses `sqlmodel.select()` for queries which provides both type safety and dialect portability.
- Suggested fix: Rewrite straightforward raw SQL into SQLModel `select/update/delete` expressions; keep raw SQL only when required by clear technical constraints (e.g., database-specific administrative queries).
- Example:
  - Bad:
    ```python
    from sqlmodel import text

    result = await session.execute(
        text("SELECT * FROM flow WHERE id = :id AND user_id = :user_id"),
        {"id": str(flow_id), "user_id": str(user_id)},
    )
    row = result.first()
    ```
  - Good:
    ```python
    from sqlmodel import select

    stmt = select(Flow).where(
        Flow.id == flow_id,
        Flow.user_id == user_id,
    )
    flow = (await session.execute(stmt)).scalar_one_or_none()
    ```

### Do not run blocking operations inside async session scopes
- Category: performance
- Severity: critical
- Description: Langflow runs on an async event loop (uvicorn + FastAPI). Blocking calls inside a session scope (synchronous I/O, `time.sleep()`, CPU-bound computation, synchronous HTTP requests) block the entire event loop and starve other coroutines. This also extends transaction duration unnecessarily, increasing lock contention.
- Suggested fix:
  - Move blocking operations outside the session scope.
  - Use `asyncio.to_thread()` or `anyio.to_thread.run_sync()` for CPU-bound or synchronous I/O work.
  - Perform external API calls before or after the database transaction, not inside it.
- Example:
  - Bad:
    ```python
    async with session_scope() as session:
        flow = (await session.execute(select(Flow).where(Flow.id == flow_id))).scalar_one()
        # Blocking HTTP call inside transaction scope
        import requests
        response = requests.post("https://external-api.com/validate", json=flow.data)
        flow.validated = response.ok
    ```
  - Good:
    ```python
    async with session_scope_readonly() as session:
        flow = (await session.execute(select(Flow).where(Flow.id == flow_id))).scalar_one()
        flow_data = flow.data

    # External call outside transaction scope
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post("https://external-api.com/validate", json=flow_data)

    async with session_scope() as session:
        flow = (await session.execute(select(Flow).where(Flow.id == flow_id))).scalar_one()
        flow.validated = response.is_success
    ```

### Protect write paths with concurrency safeguards
- Category: quality
- Severity: critical
- Description: Multi-writer paths without explicit concurrency control can silently overwrite data. Choose the safeguard based on contention level, lock scope, and throughput cost instead of defaulting to one strategy. Langflow's async architecture means multiple coroutines may attempt concurrent writes.
- Suggested fix:
  - **Optimistic locking**: Use when contention is usually low and retries are acceptable. Add a version or `updated_at` guard in `WHERE` and treat `rowcount == 0` as a conflict.
  - **SELECT ... FOR UPDATE**: Use when contention is high on the same rows and strict in-transaction serialization is required. Keep transactions short to reduce lock wait/deadlock risk.
  - In all cases, scope by `user_id` and verify affected row counts for conditional writes.
- Example:
  - Bad:
    ```python
    # No user scope, no conflict detection on a contested write path
    async with session_scope() as session:
        await session.execute(
            update(Flow).where(Flow.id == flow_id).values(name="Updated")
        )
    ```
  - Good:
    ```python
    # Optimistic lock (low contention, retry on conflict)
    from sqlmodel import update

    async with session_scope() as session:
        result = await session.execute(
            update(Flow)
            .where(
                Flow.id == flow_id,
                Flow.user_id == user_id,
                Flow.updated_at == expected_updated_at,
            )
            .values(name="Updated", updated_at=datetime.now(timezone.utc))
        )
        if result.rowcount == 0:
            raise FlowStateConflictError("Flow was modified concurrently, retry")

    # Pessimistic lock with SELECT ... FOR UPDATE (high contention)
    async with session_scope() as session:
        flow = (await session.execute(
            select(Flow)
            .where(Flow.id == flow_id, Flow.user_id == user_id)
            .with_for_update()
        )).scalar_one()
        flow.name = "Updated"
        flow.updated_at = datetime.now(timezone.utc)
    ```

### Keep transactions short; no I/O inside transactions
- Category: performance
- Severity: suggestion
- Description: Long transactions hold database locks and increase contention, especially on SQLite where write locking is database-wide. Structure code so that data is fetched, external operations are performed, and then the write transaction is opened as late as possible and closed as early as possible.
- Suggested fix:
  - Read data in one session scope, perform computation or external calls, then write results in a separate session scope.
  - Avoid nesting `session_scope()` calls (the context manager is not reentrant).
  - Batch related writes into a single session scope rather than opening multiple sequential scopes for related changes.
- Example:
  - Bad:
    ```python
    async with session_scope() as session:
        flows = (await session.execute(select(Flow).where(Flow.user_id == user_id))).scalars().all()
        for flow in flows:
            # Expensive computation inside transaction
            analysis = await analyze_flow_complexity(flow.data)
            flow.complexity_score = analysis.score
            flow.updated_at = datetime.now(timezone.utc)
    ```
  - Good:
    ```python
    # Read phase
    async with session_scope_readonly() as session:
        flows = (await session.execute(select(Flow).where(Flow.user_id == user_id))).scalars().all()
        flow_data = [(f.id, f.data) for f in flows]

    # Compute phase (outside transaction)
    updates = {}
    for flow_id, data in flow_data:
        analysis = await analyze_flow_complexity(data)
        updates[flow_id] = analysis.score

    # Write phase (short transaction)
    async with session_scope() as session:
        for flow_id, score in updates.items():
            await session.execute(
                update(Flow)
                .where(Flow.id == flow_id, Flow.user_id == user_id)
                .values(complexity_score=score, updated_at=datetime.now(timezone.utc))
            )
    ```
