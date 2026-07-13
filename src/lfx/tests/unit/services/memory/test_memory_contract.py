"""Run the shared MemoryService contract against every implementation.

The whole point of the contract is that the *same* behavioral suite passes for
both the zero-dependency in-memory default and the database-backed Tier 2
service. That equivalence is what lets langflow (DB-backed) and a bare
``lfx run`` (in-memory) share the same engine code — they differ in capabilities,
not behavior.

``TestDatabaseMemoryContract`` also exercises the Option B wiring end to end: it
constructs a real (sqlite) Tier 1 database service and lets the service manager
inject it into ``DatabaseMemoryService``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from lfx.services.capabilities import Capability, Tier
from lfx.services.database.models.message import MessageTable
from lfx.services.database.session import session_scope_for, session_scope_readonly_for
from lfx.services.manager import ServiceManager
from lfx.services.memory.contract import MemoryServiceContract
from lfx.services.memory.database import DatabaseMemoryService
from lfx.services.memory.service import InMemoryMemoryService
from lfx.services.schema import ServiceType
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession


class _SqliteDatabaseService:
    """Minimal real Tier 1 database service over an in-memory sqlite engine.

    Implements exactly the port surface DatabaseMemoryService uses: ``_with_session``
    plus the promoted ``session_scope`` / ``session_scope_readonly`` methods. Declares
    ``PERSISTENT`` — within the test process the sqlite db genuinely round-trips.
    """

    name = "database_service"
    tier = Tier.INFRASTRUCTURE
    capabilities = frozenset({Capability.PERSISTENT})

    def __init__(self, engine) -> None:
        self._engine = engine
        self._ready = False

    def set_ready(self) -> None:  # created via the factory path in the manager
        self._ready = True

    async def teardown(self) -> None:
        await self._engine.dispose()

    @asynccontextmanager
    async def _with_session(self):
        async with SQLModelAsyncSession(self._engine, expire_on_commit=False) as session:
            yield session

    def session_scope(self):
        return session_scope_for(self)

    def session_scope_readonly(self):
        return session_scope_readonly_for(self)


async def _make_sqlite_db_service() -> _SqliteDatabaseService:
    """Create a StaticPool in-memory sqlite engine with the message table."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        # Only the message table is needed (it has no cross-table FKs).
        await conn.run_sync(lambda c: SQLModel.metadata.create_all(c, tables=[MessageTable.__table__]))
    return _SqliteDatabaseService(engine)


class TestInMemoryMemoryContract(MemoryServiceContract):
    """The bare-lfx in-memory default satisfies the contract."""

    async def build_memory_service(self):
        return InMemoryMemoryService()


class TestDatabaseMemoryContract(MemoryServiceContract):
    """The DB-backed Tier 2 service satisfies the same contract over real sqlite."""

    async def build_memory_service(self):
        db_service = await _make_sqlite_db_service()
        return DatabaseMemoryService(database_service=db_service)


async def test_manager_injects_database_service_option_b():
    """The manager resolves and injects the Tier 1 db dependency (Option B)."""
    db_service = await _make_sqlite_db_service()

    class _FixedDBFactory:
        service_class = _SqliteDatabaseService

        def __init__(self):
            self.dependencies = []

        def create(self):
            return db_service

    mgr = ServiceManager()
    mgr.factories[ServiceType.DATABASE_SERVICE.value] = _FixedDBFactory()
    mgr.register_service_class(ServiceType.MEMORY_SERVICE, DatabaseMemoryService, override=True)

    memory = mgr.get(ServiceType.MEMORY_SERVICE)
    assert isinstance(memory, DatabaseMemoryService)
    # The injected dependency is the exact Tier 1 instance the manager resolved.
    assert memory.database_service is db_service


async def test_bare_lfx_memory_requires_no_database():
    """InMemoryMemoryService declares no requirements and needs no DB to wire."""
    mgr = ServiceManager()
    mgr.register_service_class(ServiceType.MEMORY_SERVICE, InMemoryMemoryService, override=True)
    memory = mgr.get(ServiceType.MEMORY_SERVICE)
    assert isinstance(memory, InMemoryMemoryService)


@pytest.mark.parametrize(
    ("impl", "expected_caps"),
    [
        (InMemoryMemoryService, {Capability.QUERYABLE}),
        (DatabaseMemoryService, {Capability.QUERYABLE, Capability.PERSISTENT}),
    ],
)
def test_memory_impls_declare_expected_capabilities(impl, expected_caps):
    """Both memory backends are Tier 2 and advertise the intended capabilities."""
    assert impl.tier == Tier.COMPOSED
    assert set(impl.capabilities) == expected_caps
