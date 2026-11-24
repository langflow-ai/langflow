# Rule Catalog — DB Schema Design

## Scope
- Covers: SQLModel model definitions, schema boundaries in model properties, user-scoped schema design, index redundancy checks, dialect portability in models (SQLite + PostgreSQL), and cross-database compatibility in Alembic migrations.
- Key directories:
  - Models: `src/backend/base/langflow/services/database/models/`
  - Migrations: `src/backend/base/langflow/alembic/versions/`
- Does NOT cover: session lifecycle, transaction boundaries, and query execution patterns (handled by `sqlalchemy-rule.md`).

## Rules

### Do not query other tables inside `@property`
- Category: [maintainability, performance]
- Severity: critical
- Description: A model `@property` must not open sessions or query other tables. This hides dependencies across models, tightly couples schema objects to data access, and can cause N+1 query explosions when iterating collections. Langflow uses SQLModel which combines SQLAlchemy table models with Pydantic validation; properties should only derive values from already-loaded fields.
- Suggested fix:
  - Keep model properties pure and local to already-loaded fields.
  - Move cross-table data fetching to service methods or CRUD functions under the model's module (e.g., `models/flow/utils.py`).
  - For list/batch reads, fetch required related data explicitly (join/preload/bulk query) before rendering derived values.
- Example:
  - Bad:
    ```python
    class Flow(FlowBase, table=True):
        __tablename__ = "flow"

        @property
        def folder_name(self) -> str:
            from lfx.services.deps import session_scope
            import asyncio
            loop = asyncio.get_event_loop()
            async def _get():
                async with session_scope() as session:
                    folder = (await session.execute(
                        select(Folder).where(Folder.id == self.folder_id)
                    )).scalar_one()
                    return folder.name
            return loop.run_until_complete(_get())
    ```
  - Good:
    ```python
    class Flow(FlowBase, table=True):
        __tablename__ = "flow"

        @property
        def display_name(self) -> str:
            return self.name or "Untitled Flow"

    # Service or CRUD layer performs explicit fetch for related Folder rows.
    async def get_flow_with_folder(flow_id: UUID, session: AsyncSession) -> tuple[Flow, Folder]:
        stmt = select(Flow, Folder).join(Folder, Flow.folder_id == Folder.id).where(Flow.id == flow_id)
        result = (await session.execute(stmt)).one_or_none()
        return result
    ```

### Use `user_id` for user-scoped data
- Category: maintainability
- Severity: suggestion
- Description: Langflow scopes user-owned data by `user_id` (not `tenant_id`). When an entity belongs to a specific user, include `user_id` in the model definition. This improves data isolation safety and keeps future multi-user or partitioning strategies practical. The `user_id` column should reference `user.id` via a foreign key where appropriate.
- Suggested fix:
  - Add a `user_id` column and ensure related unique/index constraints include the user dimension when applicable.
  - Propagate `user_id` through service interfaces to keep access paths user-scoped.
  - Exception: if a table is explicitly designed as globally shared metadata (e.g., system settings), document that design decision clearly.
- Example:
  - Bad:
    ```python
    class CustomComponent(SQLModel, table=True):
        __tablename__ = "custom_component"
        id: UUID = Field(default_factory=uuid4, primary_key=True)
        name: str = Field(index=True)
        code: str = Field(sa_column=Column(Text))
        # Missing user_id: any user can see/modify any custom component
    ```
  - Good:
    ```python
    class CustomComponent(SQLModel, table=True):
        __tablename__ = "custom_component"
        id: UUID = Field(default_factory=uuid4, primary_key=True)
        user_id: UUID = Field(foreign_key="user.id", index=True)
        name: str = Field(index=True)
        code: str = Field(sa_column=Column(Text))
    ```

### Detect and avoid duplicate/redundant indexes
- Category: performance
- Severity: suggestion
- Description: Review index definitions for leftmost-prefix redundancy. For example, index `(a, b, c)` can safely cover most lookups for `(a, b)`. Keeping both may increase write overhead and can mislead the optimizer into suboptimal execution plans. This applies to both SQLModel `Field(index=True)` declarations and explicit `__table_args__` index definitions.
- Suggested fix:
  - Before adding an index, compare against existing composite indexes by leftmost-prefix rules.
  - Drop or avoid creating redundant prefixes unless there is a proven query-pattern need.
  - Apply the same review standard in both model `__table_args__` and Alembic migration index DDL.
- Example:
  - Bad:
    ```python
    class Message(SQLModel, table=True):
        __tablename__ = "message"
        __table_args__ = (
            sa.Index("idx_msg_user_flow", "user_id", "flow_id"),
            sa.Index("idx_msg_user_flow_created", "user_id", "flow_id", "created_at"),
        )
    ```
  - Good:
    ```python
    class Message(SQLModel, table=True):
        __tablename__ = "message"
        __table_args__ = (
            # Keep the wider index unless profiling proves a dedicated short index is needed.
            sa.Index("idx_msg_user_flow_created", "user_id", "flow_id", "created_at"),
        )
    ```

### Avoid dialect-specific constructs directly in models; use portable types
- Category: maintainability
- Severity: critical
- Description: Langflow supports both SQLite (development) and PostgreSQL 15+ (production). Model/schema definitions should avoid PostgreSQL-only or SQLite-only constructs directly in business models. When database-specific behavior is required, encapsulate it behind a portable abstraction. SQLModel's `Field()` and `Column()` already provide most portability, but direct use of dialect-specific types (e.g., `postgresql.JSONB`, `postgresql.ARRAY`) breaks SQLite compatibility.
- Suggested fix:
  - Use SQLModel's `JSON` column type (which maps to the appropriate dialect type) instead of `postgresql.JSONB`.
  - Use `sa.Text` or `sa.String` instead of dialect-specific text types.
  - If a dialect-specific feature is truly needed, add a conditional wrapper and document the rationale.
- Example:
  - Bad:
    ```python
    from sqlalchemy.dialects.postgresql import JSONB

    class ToolConfig(SQLModel, table=True):
        __tablename__ = "tool_config"
        id: UUID = Field(default_factory=uuid4, primary_key=True)
        config: dict = Field(sa_column=Column(JSONB, nullable=False))  # Breaks on SQLite
    ```
  - Good:
    ```python
    from sqlmodel import JSON

    class ToolConfig(SQLModel, table=True):
        __tablename__ = "tool_config"
        id: UUID = Field(default_factory=uuid4, primary_key=True)
        config: dict | None = Field(default=None, sa_column=Column(JSON))  # Works on both dialects
    ```

### Guard migration incompatibilities with dialect checks
- Category: maintainability
- Severity: critical
- Description: Alembic migration scripts under `src/backend/base/langflow/alembic/versions/` must account for SQLite/PostgreSQL incompatibilities explicitly. SQLite has limited ALTER TABLE support (no DROP COLUMN before 3.35, no ADD CONSTRAINT). For dialect-sensitive DDL or defaults, branch on the active dialect or use `op.batch_alter_table()` for SQLite compatibility.
- Suggested fix:
  - In migration upgrades/downgrades, bind connection and branch by dialect for incompatible SQL fragments.
  - Use `op.batch_alter_table()` for column modifications on SQLite.
  - Avoid one-dialect-only migration logic unless there is a documented, deliberate compatibility exception.
- Example:
  - Bad:
    ```python
    def upgrade():
        op.add_column("flow", sa.Column(
            "access_type",
            sa.String(50),
            server_default=sa.text("'PRIVATE'::character varying"),  # PostgreSQL-only cast
            nullable=False,
        ))
    ```
  - Good:
    ```python
    def upgrade():
        conn = op.get_bind()
        if conn.dialect.name == "postgresql":
            default_expr = sa.text("'PRIVATE'::character varying")
        else:
            default_expr = sa.text("'PRIVATE'")

        with op.batch_alter_table("flow") as batch_op:
            batch_op.add_column(sa.Column(
                "access_type",
                sa.String(50),
                server_default=default_expr,
                nullable=False,
            ))
    ```

### SQLModel-specific patterns
- Category: best practices
- Severity: suggestion
- Description: Langflow uses SQLModel which merges SQLAlchemy ORM and Pydantic validation into a single class hierarchy. Follow these conventions for model definitions:
  - Use `SQLModel` as the base class with `table=True` for database-backed models.
  - Use `SQLModel` without `table=True` for schema/validation-only models (e.g., `FlowCreate`, `FlowRead`, `FlowUpdate`).
  - Use `Field()` for column definitions; use `sa_column=Column(...)` only when `Field()` alone cannot express the constraint.
  - Use `Relationship()` for ORM relationships; put related model type hints behind `TYPE_CHECKING` to avoid circular imports.
- Suggested fix: Follow the existing patterns in `src/backend/base/langflow/services/database/models/flow/model.py` for reference on how to define base models, table models, and CRUD schema models.
- Example:
  - Bad:
    ```python
    # Mixing table model and API schema in one class
    class Flow(SQLModel, table=True):
        id: UUID = Field(default_factory=uuid4, primary_key=True)
        name: str
        data: dict | None = None
        # API-only fields mixed in
        component_count: int = 0  # Not a DB column, computed at API time
    ```
  - Good:
    ```python
    # Table model: only DB columns
    class Flow(FlowBase, table=True):
        id: UUID = Field(default_factory=uuid4, primary_key=True)
        user_id: UUID = Field(foreign_key="user.id", index=True)

    # Schema model: includes computed fields for API responses
    class FlowRead(FlowBase):
        id: UUID
        user_id: UUID
        component_count: int = 0
    ```

### Follow the Base → Table → Create → Read → Update schema pattern
- Category: best practices
- Severity: suggestion
- Description: Langflow uses a layered SQLModel schema pattern. `{Entity}Base(SQLModel)` defines shared fields, validators (`@field_validator`), and serializers (`@field_serializer`). `{Entity}(Base, table=True)` adds primary key and relationships. Separate `Create`, `Read`, and `Update` schemas control API boundaries. Use `model_dump(exclude_unset=True, exclude_none=True)` for partial updates. Use `FlowRead.model_validate(db_flow, from_attributes=True)` to convert ORM→schema while session is active.
- Suggested fix:
  - Define Base → Table → Create → Read → Update for every entity.
  - Put `@field_validator` and `@field_serializer` on the Base so they apply everywhere.
  - Never return the Table model directly from a route — always convert to the Read schema.
- Example:
  - Bad:
    ```python
    # Returning the table model directly (leaks internal fields, relationships)
    @router.get("/{flow_id}")
    async def get_flow(flow_id: UUID, session: DbSession) -> Flow:
        return (await session.execute(select(Flow).where(Flow.id == flow_id))).scalar_one()
    ```
  - Good:
    ```python
    class FlowBase(SQLModel):
        name: str = Field(index=True)
        description: str | None = Field(default=None)

        @field_validator("endpoint_name")
        @classmethod
        def validate_endpoint_name(cls, v):
            if v is not None and not re.match(r"^[a-zA-Z0-9_-]+$", v):
                raise HTTPException(status_code=422, detail="Invalid endpoint name")
            return v

        @field_serializer("updated_at")
        def serialize_datetime(self, value):
            if isinstance(value, datetime):
                return value.replace(microsecond=0).isoformat()
            return value

    class Flow(FlowBase, table=True):
        id: UUID = Field(default_factory=uuid4, primary_key=True)
        user_id: UUID = Field(foreign_key="user.id")

    class FlowCreate(FlowBase):
        user_id: UUID | None = None
        folder_id: UUID | None = None

    class FlowRead(FlowBase):
        id: UUID
        user_id: UUID | None = Field()

    @router.get("/{flow_id}", response_model=FlowRead)
    async def get_flow(*, flow_id: UUID, session: DbSession, current_user: CurrentActiveUser) -> FlowRead:
        flow = (await session.execute(select(Flow).where(Flow.id == flow_id, Flow.user_id == current_user.id))).scalar_one()
        return FlowRead.model_validate(flow, from_attributes=True)
    ```
