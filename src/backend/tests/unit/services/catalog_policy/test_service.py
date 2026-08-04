"""Database-backed catalog-policy service tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.services.catalog_policy import service as catalog_policy_service_module
from langflow.services.catalog_policy.factory import CatalogPolicyServiceFactory
from langflow.services.catalog_policy.service import LangflowCatalogPolicyService
from langflow.services.database.models.catalog_policy import (
    CatalogPolicyMode,
    CatalogPolicyRule,
    CatalogResourceKind,
)
from langflow.services.schema import ServiceType
from lfx.services.catalog_policy import BaseCatalogPolicyService
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


class _Database:
    def __init__(self, engine) -> None:
        self.engine = engine

    @asynccontextmanager
    async def session_scope(self):
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def session_scope_readonly(self):
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            yield session


@pytest.fixture
async def catalog_database(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: SQLModel.metadata.create_all(
                sync_connection,
                tables=[CatalogPolicyRule.__table__],
            )
        )
    database = _Database(engine)
    monkeypatch.setattr(catalog_policy_service_module, "session_scope", database.session_scope)
    monkeypatch.setattr(catalog_policy_service_module, "session_scope_readonly", database.session_scope_readonly)
    yield database
    await engine.dispose()


@pytest.mark.asyncio
async def test_unhydrated_service_is_fail_open_then_hydrates_global_blocks(catalog_database):
    async with catalog_database.session_scope() as session:
        session.add_all(
            [
                CatalogPolicyRule(
                    resource_kind=CatalogResourceKind.COMPONENT.value,
                    resource_key="OpenAIModel",
                ),
                CatalogPolicyRule(
                    resource_kind=CatalogResourceKind.TEMPLATE.value,
                    resource_key="starter-template",
                ),
                CatalogPolicyRule(
                    resource_kind=CatalogResourceKind.COMPONENT.value,
                    resource_key="future-allow",
                    mode=CatalogPolicyMode.ALLOW.value,
                ),
            ]
        )
        await session.commit()

    service = LangflowCatalogPolicyService(catalog_database)
    assert service.hydrated is False
    assert service.enabled is False
    assert service.is_component_allowed("OpenAIModel") is True

    snapshot = await service.hydrate()

    assert service.hydrated is True
    assert snapshot.blocked_component_keys == frozenset({"OpenAIModel"})
    assert snapshot.blocked_template_keys == frozenset({"starter-template"})
    assert service.is_component_blocked("OpenAIModel") is True
    assert service.is_template_blocked("starter-template") is True
    assert service.is_component_blocked("future-allow") is False


@pytest.mark.asyncio
async def test_whole_set_replace_normalizes_and_preserves_other_resource_kind(catalog_database):
    actor_id = uuid4()
    async with catalog_database.session_scope() as session:
        session.add(
            CatalogPolicyRule(
                resource_kind=CatalogResourceKind.TEMPLATE.value,
                resource_key="keep-template",
            )
        )
        await session.commit()

    service = LangflowCatalogPolicyService(catalog_database)
    await service.hydrate()

    update = await service.replace_blocked_component_keys(
        [" OpenAIModel ", "Agent", "OpenAIModel"],
        actor_user_id=actor_id,
    )

    assert update.added == frozenset({"Agent", "OpenAIModel"})
    assert update.removed == frozenset()
    assert update.snapshot.blocked_component_keys == frozenset({"Agent", "OpenAIModel"})
    assert update.snapshot.blocked_template_keys == frozenset({"keep-template"})
    assert service.blocked_component_keys(["Agent", "Other"]) == frozenset({"Agent"})

    second = await service.replace_blocked_component_keys(["Agent"], actor_user_id=actor_id)
    assert second.added == frozenset()
    assert second.removed == frozenset({"OpenAIModel"})

    async with catalog_database.session_scope_readonly() as session:
        rows = list((await session.exec(select(CatalogPolicyRule))).all())
    persisted = sorted((row.resource_kind, row.resource_key, row.created_by) for row in rows)
    assert persisted == [
        (CatalogResourceKind.COMPONENT.value, "Agent", actor_id),
        (CatalogResourceKind.TEMPLATE.value, "keep-template", None),
    ]


@pytest.mark.asyncio
async def test_replace_rejects_empty_keys_before_opening_a_transaction(catalog_database):
    service = LangflowCatalogPolicyService(catalog_database)

    with pytest.raises(ValueError, match="must not be empty"):
        await service.replace_blocked_template_keys(["valid", "   "], actor_user_id=None)

    assert service.snapshot.blocked_template_keys == frozenset()
    assert service.hydrated is False


class _Result:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, *, commit_error: Exception | None = None) -> None:
        self.commit_error = commit_error
        self.added = []
        self.rolled_back = False
        self.before_commit = None

    async def exec(self, _statement):
        return _Result([])

    def add(self, row) -> None:
        self.added.append(row)

    async def delete(self, _row) -> None:
        return None

    async def commit(self) -> None:
        if self.before_commit is not None:
            self.before_commit()
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.rolled_back = True


class _SingleSessionDatabase:
    def __init__(self, session) -> None:
        self.session = session

    @asynccontextmanager
    async def session_scope(self):
        try:
            yield self.session
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @asynccontextmanager
    async def session_scope_readonly(self):
        yield self.session


def _patch_session_scopes(monkeypatch, database) -> None:
    monkeypatch.setattr(catalog_policy_service_module, "session_scope", database.session_scope)
    monkeypatch.setattr(catalog_policy_service_module, "session_scope_readonly", database.session_scope_readonly)


@pytest.mark.asyncio
async def test_snapshot_is_published_only_after_commit(monkeypatch):
    session = _Session()
    database = _SingleSessionDatabase(session)
    _patch_session_scopes(monkeypatch, database)
    service = LangflowCatalogPolicyService(database)
    session.before_commit = lambda: (
        pytest.fail("snapshot published before commit") if service.is_component_blocked("new") else None
    )

    await service.replace_blocked_component_keys(["new"], actor_user_id=None)

    assert service.is_component_blocked("new") is True


@pytest.mark.asyncio
async def test_failed_commit_rolls_back_and_keeps_fail_open_snapshot(monkeypatch):
    session = _Session(commit_error=RuntimeError("commit failed"))
    database = _SingleSessionDatabase(session)
    _patch_session_scopes(monkeypatch, database)
    service = LangflowCatalogPolicyService(database)

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.replace_blocked_component_keys(["new"], actor_user_id=None)

    assert session.rolled_back is True
    assert service.hydrated is False
    assert service.is_component_allowed("new") is True


@pytest.mark.asyncio
async def test_failed_hydration_keeps_fail_open_snapshot(monkeypatch):
    class _UnavailableSession(_Session):
        async def exec(self, _statement):
            message = "database unavailable"
            raise RuntimeError(message)

    database = _SingleSessionDatabase(_UnavailableSession())
    _patch_session_scopes(monkeypatch, database)
    service = LangflowCatalogPolicyService(database)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.hydrate()

    assert service.hydrated is False
    assert service.enabled is False
    assert service.is_component_allowed("anything") is True
    assert service.is_template_allowed("anything") is True


def test_factory_uses_database_dependency_and_canonical_service_type():
    database = SimpleNamespace()
    factory = CatalogPolicyServiceFactory()

    service = factory.create(database)

    assert isinstance(service, BaseCatalogPolicyService)
    assert isinstance(service, LangflowCatalogPolicyService)
    assert service.database_service is database
    assert factory.name == ServiceType.CATALOG_POLICY_SERVICE.value


def test_backend_dependency_uses_validated_lfx_catalog_policy(monkeypatch):
    from langflow.services import deps as langflow_deps
    from lfx.services import deps as lfx_deps

    service = SimpleNamespace()
    monkeypatch.setattr(lfx_deps, "get_catalog_policy_service", lambda: service)

    assert langflow_deps.get_catalog_policy_service() is service


@pytest.mark.asyncio
async def test_startup_hydration_failure_logs_and_continues(monkeypatch):
    from langflow.services import deps, utils

    service = SimpleNamespace(hydrate=AsyncMock(side_effect=RuntimeError("database unavailable")))
    warning = AsyncMock()
    monkeypatch.setattr(deps, "get_catalog_policy_service", lambda: service)
    monkeypatch.setattr(utils.logger, "awarning", warning)

    await utils.hydrate_catalog_policy()

    service.hydrate.assert_awaited_once_with()
    warning.assert_awaited_once()
    assert "continuing with allow-all policy" in warning.await_args.args[0]
