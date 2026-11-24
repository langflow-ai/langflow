# Rule Catalog — Architecture

## Scope
- Covers: route handler/service/model layering, dependency direction, responsibility placement, helper module purity, and observability-friendly flow.
- Key directories:
  - Routes: `src/backend/base/langflow/api/v1/`, `src/backend/base/langflow/api/v2/`
  - Services: `src/backend/base/langflow/services/`
  - Models: `src/backend/base/langflow/services/database/models/`
  - Helpers: `src/backend/base/langflow/helpers/`
  - Components: `src/backend/base/langflow/components/`

## Rules

### Keep business logic out of route handlers
- Category: maintainability
- Severity: critical
- Description: Route handlers (FastAPI endpoint functions) should parse input, delegate to a service, and return a serialized response. Business decisions inside route handlers make behavior hard to reuse, test, and maintain. Langflow uses FastAPI with `Depends()` for dependency injection and async handlers throughout.
- Suggested fix: Move domain/business logic into the appropriate service under `src/backend/base/langflow/services/`. Keep route handlers thin and orchestration-focused.
- Example:
  - Bad:
    ```python
    @router.post("/flows/{flow_id}/publish")
    async def publish_flow(
        flow_id: UUID,
        session: AsyncSession = Depends(injectable_session_scope),
        current_user: User = Depends(get_current_active_user),
    ):
        stmt = select(Flow).where(Flow.id == flow_id, Flow.user_id == current_user.id)
        flow = (await session.execute(stmt)).scalar_one_or_none()
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        if flow.access_type == AccessTypeEnum.PUBLIC:
            raise HTTPException(status_code=400, detail="Already published")
        flow.access_type = AccessTypeEnum.PUBLIC
        flow.updated_at = datetime.now(timezone.utc)
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        return FlowRead.model_validate(flow, from_attributes=True)
    ```
  - Good:
    ```python
    @router.post("/flows/{flow_id}/publish")
    async def publish_flow(
        flow_id: UUID,
        session: AsyncSession = Depends(injectable_session_scope),
        current_user: User = Depends(get_current_active_user),
    ):
        flow = await flow_service.publish_flow(
            flow_id=flow_id, user_id=current_user.id, session=session
        )
        return FlowRead.model_validate(flow, from_attributes=True)
    ```

### Preserve layer dependency direction
- Category: best practices
- Severity: critical
- Description: Routes may depend on services, and services may depend on models and domain abstractions. Reversing this direction (for example, a model or service importing from `langflow.api`) creates cycles and leaks transport concerns into domain code. The dependency flow must be: Routes -> Services -> Models (never reverse).
- Suggested fix: Extract shared contracts into service-level or model-level modules and make upper layers depend on lower, not the reverse.
- Example:
  - Bad:
    ```python
    # src/backend/base/langflow/services/database/models/flow/model.py
    from langflow.api.v1.schemas import FlowListCreate  # Model importing from API layer

    class Flow(FlowBase, table=True):
        def to_api_response(self) -> FlowListCreate:
            return FlowListCreate(...)
    ```
  - Good:
    ```python
    # src/backend/base/langflow/services/database/models/flow/model.py
    class Flow(FlowBase, table=True):
        pass  # No API-layer imports

    # src/backend/base/langflow/api/v1/flows.py (route layer handles serialization)
    flow = await get_flow(flow_id, session)
    return FlowRead.model_validate(flow, from_attributes=True)
    ```

### Keep helpers business-agnostic
- Category: maintainability
- Severity: critical
- Description: Modules under `src/backend/base/langflow/helpers/` should remain reusable, business-agnostic building blocks. They must not encode product/domain-specific rules, workflow orchestration, or business decisions. Helpers may contain thin wrappers for user lookups or data transformation but must not implement business policy.
- Suggested fix:
  - If business logic appears in `src/backend/base/langflow/helpers/`, extract it into the appropriate service under `src/backend/base/langflow/services/` and keep helpers focused on generic, cross-cutting utilities.
  - Keep helper dependencies clean: avoid importing service or route modules into helpers.
- Example:
  - Bad:
    ```python
    # src/backend/base/langflow/helpers/flow.py
    from langflow.services.variable.service import DatabaseVariableService

    def should_archive_flow(flow: Flow, user_id: UUID) -> bool:
        # Domain policy and service dependency are leaking into helpers.
        service = DatabaseVariableService(get_settings_service())
        if service.has_premium_plan(user_id):
            return flow.idle_days > 90
        return flow.idle_days > 30
    ```
  - Good:
    ```python
    # src/backend/base/langflow/helpers/flow.py (business-agnostic helper)
    def is_older_than_days(updated_at: datetime, threshold_days: int) -> bool:
        delta = datetime.now(timezone.utc) - updated_at
        return delta.days > threshold_days

    # src/backend/base/langflow/services/flow_service.py (business logic stays in service)
    from langflow.helpers.flow import is_older_than_days

    async def should_archive_flow(flow: Flow, user_id: UUID) -> bool:
        threshold_days = 90 if await has_premium_plan(user_id) else 30
        return is_older_than_days(flow.updated_at, threshold_days)
    ```

### Domain logic must not import from FastAPI/HTTP layers
- Category: best practices
- Severity: critical
- Description: Service classes and model definitions must never import FastAPI-specific constructs such as `Request`, `Response`, `HTTPException`, `APIRouter`, or `Depends`. This keeps the domain layer transport-agnostic and testable without spinning up an HTTP server. Langflow services inherit from `langflow.services.base.Service` and receive dependencies through their factory's `create()` method or via constructor injection, not through FastAPI's `Depends()`.
- Suggested fix: Raise domain-specific exceptions in services (e.g., `FlowNotFoundError`, `PermissionDeniedError`) and let the route handler translate them into HTTP responses.
- Example:
  - Bad:
    ```python
    # src/backend/base/langflow/services/variable/service.py
    from fastapi import HTTPException

    class DatabaseVariableService(VariableService, Service):
        async def get_variable(self, variable_id: UUID, user_id: UUID, session: AsyncSession):
            variable = await session.get(Variable, variable_id)
            if not variable or variable.user_id != user_id:
                raise HTTPException(status_code=404, detail="Variable not found")
            return variable
    ```
  - Good:
    ```python
    # src/backend/base/langflow/services/variable/service.py
    class VariableNotFoundError(Exception):
        pass

    class DatabaseVariableService(VariableService, Service):
        async def get_variable(self, variable_id: UUID, user_id: UUID, session: AsyncSession):
            variable = await session.get(Variable, variable_id)
            if not variable or variable.user_id != user_id:
                raise VariableNotFoundError(f"Variable {variable_id} not found for user {user_id}")
            return variable

    # src/backend/base/langflow/api/v1/variables.py (route translates to HTTP)
    @router.get("/variables/{variable_id}")
    async def get_variable(variable_id: UUID, ...):
        try:
            return await variable_service.get_variable(variable_id, current_user.id, session)
        except VariableNotFoundError:
            raise HTTPException(status_code=404, detail="Variable not found")
    ```

### Components are leaf nodes in the dependency graph
- Category: best practices
- Severity: suggestion
- Description: Components under `src/backend/base/langflow/components/` represent flow nodes and are instantiated dynamically by the graph engine. They should depend on services and models but no other component should import from them. Component class names are stable identifiers used to match components in saved flows; renaming a component class is a breaking change.
- Suggested fix: If shared logic exists between components, extract it into a helper or a base class under `src/backend/base/langflow/custom/` rather than creating cross-component imports.

### Use Google-style docstrings
- Category: best practices
- Severity: suggestion
- Description: The project enforces Google-style docstrings via Ruff (`pydocstyle.convention = "google"`). Public functions and classes should have docstrings with `Args:`, `Returns:`, and `Raises:` sections. Route handlers need at minimum a one-line summary. Private helpers (`_func`) can use simpler docstrings.
- Example:
  - Bad:
    ```python
    def timestamp_to_str(timestamp):
        # converts timestamp to string
        ...
    ```
  - Good:
    ```python
    def timestamp_to_str(timestamp: datetime | str) -> str:
        """Convert timestamp to standardized string format.

        Args:
            timestamp: Input timestamp as datetime object or string.

        Returns:
            Formatted timestamp string in 'YYYY-MM-DD HH:MM:SS UTC' format.

        Raises:
            ValueError: If string timestamp is in invalid format.
        """
        ...
    ```

### Use the async logger from `lfx.log.logger`
- Category: best practices
- Severity: critical
- Description: Langflow uses an async-aware logger from `lfx.log.logger`. In async code, always use the `a`-prefixed methods (`adebug`, `ainfo`, `awarning`, `aerror`, `aexception`) to avoid blocking the event loop. Never use `print()` or stdlib `logging` directly. Use `aexception` for errors (auto-includes traceback). Use `{e!s}` for string representation of exceptions.
- Example:
  - Bad:
    ```python
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Processing flow {flow_id}")
    print(f"Error: {e}")
    ```
  - Good:
    ```python
    from lfx.log.logger import logger

    await logger.ainfo(f"Processing flow {flow_id}")
    await logger.aexception(f"Error processing flow {flow_id}: {e!s}")
    await logger.adebug("Skipping environment variable storage.")
    await logger.awarning(f"Session rolled back during {var_name} query.")
    ```

### Use Python 3.10+ type syntax and FastAPI DI aliases
- Category: best practices
- Severity: suggestion
- Description: Use modern Python 3.10+ union syntax (`X | Y` instead of `Union[X, Y]`, `X | None` instead of `Optional[X]`). Use `TYPE_CHECKING` guard for imports only needed for type annotations (prevents circular imports). Use `Annotated[Type, Depends(...)]` for FastAPI dependency injection with project type aliases like `CurrentActiveUser`, `DbSession`, `DbSessionReadOnly`.
- Example:
  - Bad:
    ```python
    from typing import Optional, Union
    from fastapi import Depends

    async def get_flow(
        flow_id: UUID,
        session: AsyncSession = Depends(injectable_session_scope),
        user: User = Depends(get_current_active_user),
    ) -> Optional[Flow]:
        ...
    ```
  - Good:
    ```python
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from langflow.services.database.models.user.model import User

    async def get_flow(
        *,
        flow_id: UUID,
        session: DbSession,          # Annotated[AsyncSession, Depends(injectable_session_scope)]
        current_user: CurrentActiveUser,  # Annotated[User, Depends(get_current_active_user)]
    ) -> Flow | None:
        ...
    ```
