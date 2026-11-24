# Rule Catalog — Service Abstraction

## Scope
- Covers: when to reuse existing service abstractions, when to introduce new services, how to preserve dependency direction between route handlers and service/infrastructure implementations, and the ServiceFactory pattern.
- Key directories:
  - Services: `src/backend/base/langflow/services/` (each service has `service.py` and `factory.py`)
  - Model CRUD functions: `src/backend/base/langflow/services/database/models/*/crud.py`
  - Service base class: `langflow.services.base.Service`
  - Service factory base: `langflow.services.factory.ServiceFactory`
  - Service registry: `langflow.services.manager.ServiceManager`
  - Service types: `langflow.services.schema.ServiceType`
  - Dependency helpers: `langflow.services.deps` (provides `get_service()`, `get_xxx_service()` functions)
- Does NOT cover: SQLAlchemy session lifecycle and query-shape specifics (handled by `sqlalchemy-rule.md`), and table schema/migration design (handled by `db-schema-rule.md`).

## Rules

### Use existing services for DB operations; do not bypass with ad-hoc queries
- Category: maintainability
- Severity: suggestion
- Description: Langflow uses a service layer pattern rather than a repository pattern. Each service under `src/backend/base/langflow/services/` encapsulates business logic and data access for its domain. If a service already handles operations for a given model/table, all reads/writes/queries for that table should go through the existing service (or its associated CRUD module). Additionally, many models have CRUD utility functions in `src/backend/base/langflow/services/database/models/<model>/crud.py` that should be reused rather than duplicated.
- Suggested fix:
  - First check `src/backend/base/langflow/services/` and `src/backend/base/langflow/services/database/models/<model>/crud.py` to verify whether the table/model already has a service or CRUD abstraction. If it exists, route all operations through it and add missing methods instead of bypassing it with ad-hoc SQLAlchemy queries.
  - If no service or CRUD module exists, add methods to the most closely related existing service or CRUD module rather than scattering inline queries across route handlers.
- Example:
  - Bad:
    ```python
    # Route handler bypasses the existing variable service with inline queries
    @router.get("/variables")
    async def list_variables(
        session: AsyncSession = Depends(injectable_session_scope_readonly),
        current_user: User = Depends(get_current_active_user),
    ):
        stmt = select(Variable).where(Variable.user_id == current_user.id)
        variables = (await session.execute(stmt)).scalars().all()
        return [VariableRead.model_validate(v, from_attributes=True) for v in variables]
    ```
  - Good:
    ```python
    # Route handler delegates to the variable service
    @router.get("/variables")
    async def list_variables(
        session: AsyncSession = Depends(injectable_session_scope_readonly),
        current_user: User = Depends(get_current_active_user),
    ):
        variable_service = get_variable_service()
        variables = await variable_service.list_variables(user_id=current_user.id, session=session)
        return [VariableRead.model_validate(v, from_attributes=True) for v in variables]
    ```

### Follow the ServiceFactory pattern for new services
- Category: best practices
- Severity: critical
- Description: Langflow manages services through `ServiceManager` which uses `ServiceFactory` instances to create and configure services. Each service consists of:
  1. A base class or protocol (optional, for abstraction) inheriting from `langflow.services.base.Service`
  2. A concrete implementation in `service.py`
  3. A factory class in `factory.py` inheriting from `langflow.services.factory.ServiceFactory`
  4. A `ServiceType` enum entry in `langflow.services.schema`
  5. A `get_xxx_service()` function in `langflow.services.deps`

  New services must follow this pattern to integrate with the dependency injection system. The factory's `create()` method receives other services as arguments (resolved by name from the ServiceManager).
- Suggested fix: When introducing a new service, create all required files following the existing pattern. Register the factory in `ServiceManager.get_factories()` and add a convenience getter in `langflow.services.deps`.
- Example:
  - Bad:
    ```python
    # Ad-hoc singleton without factory integration
    class NotificationService:
        _instance = None

        @classmethod
        def get_instance(cls):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

        def notify(self, user_id: UUID, message: str):
            ...
    ```
  - Good:
    ```python
    # src/backend/base/langflow/services/notification/service.py
    from langflow.services.base import Service

    class NotificationService(Service):
        name = "notification_service"

        def __init__(self, settings_service: SettingsService):
            self.settings_service = settings_service

        async def notify(self, user_id: UUID, message: str, session: AsyncSession) -> None:
            ...

    # src/backend/base/langflow/services/notification/factory.py
    from langflow.services.factory import ServiceFactory
    from langflow.services.notification.service import NotificationService

    class NotificationServiceFactory(ServiceFactory):
        def __init__(self) -> None:
            super().__init__(NotificationService)

        def create(self, settings_service: SettingsService):
            return NotificationService(settings_service)

    # Register in ServiceManager.get_factories() and add getter in deps.py
    ```

### When to introduce a new service vs. extend an existing one
- Category: best practices
- Severity: suggestion
- Description: Not every new feature needs a new service. Introduce a new service only when:
  1. The domain is distinct enough that mixing it into an existing service would violate single responsibility.
  2. The service manages its own lifecycle (e.g., connections, background tasks, caches).
  3. Multiple other services or route modules need to depend on this functionality.
  4. The data access patterns are sufficiently different from existing services.

  Otherwise, extend an existing service by adding methods to its `service.py` and corresponding CRUD functions.
- Suggested fix:
  - For small, related features: add methods to the closest existing service.
  - For distinct domains with their own lifecycle: create a new service following the ServiceFactory pattern.
  - When in doubt, start by extending an existing service; extract into a new service later when complexity warrants it (YAGNI principle).
- Example:
  - Bad:
    ```python
    # Unnecessary new service for a simple feature that belongs in an existing service
    # src/backend/base/langflow/services/flow_stats/service.py
    class FlowStatsService(Service):
        name = "flow_stats_service"

        async def get_flow_component_count(self, flow_id: UUID, session: AsyncSession) -> int:
            flow = (await session.execute(select(Flow).where(Flow.id == flow_id))).scalar_one()
            return len(flow.data.get("nodes", []))
    ```
  - Good:
    ```python
    # Add to existing flow-related code or a utility function
    # src/backend/base/langflow/services/database/models/flow/utils.py
    def count_components(flow_data: dict | None) -> int:
        if not flow_data:
            return 0
        return len(flow_data.get("nodes", []))
    ```

### Access services through `get_service()` or dependency getters, not direct instantiation
- Category: maintainability
- Severity: critical
- Description: Services are singletons managed by `ServiceManager`. They must be accessed through `get_service(ServiceType.XXX)` or the convenience functions in `langflow.services.deps` (e.g., `get_settings_service()`, `get_variable_service()`). Direct instantiation bypasses the factory pattern, ignores lifecycle management, and can create multiple conflicting instances.
- Suggested fix: Always use the provided dependency functions. In route handlers, use FastAPI's `Depends()` with the appropriate getter. In service-to-service calls, use `get_service()` or accept the dependency through the factory's `create()` method.
- Example:
  - Bad:
    ```python
    # Direct instantiation bypasses the service manager
    from langflow.services.variable.service import DatabaseVariableService

    async def some_function():
        settings = get_settings_service()
        variable_service = DatabaseVariableService(settings)  # Wrong: creates a new instance
        await variable_service.get_variable(...)
    ```
  - Good:
    ```python
    # Use the dependency getter
    from langflow.services.deps import get_variable_service

    async def some_function():
        variable_service = get_variable_service()
        await variable_service.get_variable(...)

    # In route handlers, use Depends()
    @router.get("/variables/{variable_id}")
    async def get_variable(
        variable_id: UUID,
        session: AsyncSession = Depends(injectable_session_scope_readonly),
        current_user: User = Depends(get_current_active_user),
    ):
        variable_service = get_variable_service()
        return await variable_service.get_variable(variable_id, current_user.id, session)
    ```

### CRUD modules complement services, not replace them
- Category: best practices
- Severity: suggestion
- Description: Many Langflow models have a `crud.py` file alongside their model definition (e.g., `models/message/crud.py`, `models/user/crud.py`). These CRUD modules contain reusable async functions for common database operations (get, list, create, update, delete). They are lower-level building blocks that services call internally. Route handlers should prefer calling service methods rather than CRUD functions directly, unless the operation is trivially simple and the model has no associated service.
- Suggested fix:
  - Services should call CRUD functions internally to avoid duplicating query logic.
  - Route handlers should call services, not CRUD functions, to maintain the layering.
  - New CRUD functions should accept an `AsyncSession` parameter and stay stateless (pure data access, no business logic).
- Example:
  - Bad:
    ```python
    # Route handler calling CRUD directly, bypassing any business logic layer
    from langflow.services.database.models.message.crud import get_messages_by_flow_id

    @router.get("/flows/{flow_id}/messages")
    async def list_messages(
        flow_id: UUID,
        session: AsyncSession = Depends(injectable_session_scope_readonly),
        current_user: User = Depends(get_current_active_user),
    ):
        # No authorization check, no business logic, direct CRUD call
        return await get_messages_by_flow_id(flow_id, session)
    ```
  - Good:
    ```python
    # Service wraps CRUD with authorization and business logic
    class ChatService(Service):
        async def get_messages(self, flow_id: UUID, user_id: UUID, session: AsyncSession):
            # Verify user owns the flow
            flow = await get_flow_by_id_and_user(flow_id, user_id, session)
            if not flow:
                raise FlowNotFoundError(f"Flow {flow_id} not found")
            return await get_messages_by_flow_id(flow_id, session)

    # Route handler delegates to service
    @router.get("/flows/{flow_id}/messages")
    async def list_messages(flow_id: UUID, ...):
        chat_service = get_chat_service()
        return await chat_service.get_messages(flow_id, current_user.id, session)
    ```
