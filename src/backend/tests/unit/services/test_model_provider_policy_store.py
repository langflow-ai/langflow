from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langflow.services import model_provider_policy as policy_store
from langflow.services.database.models.model_provider_policy import ModelProviderPolicy
from langflow.services.task import model_provider_policy_refresh as refresh_module
from lfx.services.catalog_policy import CatalogPolicyService
from lfx.services.model_provider_policy import BaseModelProviderPolicyService, ModelProviderPolicyService
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


class _Result:
    def __init__(self, row, *, rowcount: int = 1):
        self._row = row
        self.rowcount = rowcount

    def one_or_none(self):
        return self._row


class _ReadSession:
    def __init__(self, provider_ids: list[str], *, version: int):
        self._row = SimpleNamespace(approved_provider_ids=provider_ids, version=version)

    async def exec(self, _statement):
        return _Result(self._row)


async def test_hydrate_model_provider_policy_restores_persisted_ceiling(monkeypatch):
    service = ModelProviderPolicyService()
    monkeypatch.setattr(policy_store, "get_model_provider_policy_service", lambda: service)

    state = await policy_store.hydrate_model_provider_policy(_ReadSession(["openai", "anthropic"], version=4))

    assert state == policy_store.PersistedModelProviderPolicy(
        approved_provider_ids=frozenset({"openai", "anthropic"}),
        version=4,
    )
    assert service.approved_provider_ids == state.approved_provider_ids
    assert service.policy_version == 4


async def test_hydrate_empty_store_preserves_allow_all(monkeypatch):
    service = ModelProviderPolicyService()
    service.set_approved_provider_ids({"openai"}, version=1)
    monkeypatch.setattr(policy_store, "get_model_provider_policy_service", lambda: service)

    await policy_store.hydrate_model_provider_policy(_ReadSession([], version=2))

    assert not service.approved_provider_ids
    assert service.policy_version == 2


def test_legacy_third_party_policy_service_is_invalidated_without_replacing_its_source(monkeypatch):
    class LegacyPolicyService(BaseModelProviderPolicyService):
        def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
            _ = (context, purpose)
            return candidate_provider_ids

    service = LegacyPolicyService()
    invalidate = Mock(wraps=service.invalidate)
    monkeypatch.setattr(service, "invalidate", invalidate)
    monkeypatch.setattr(policy_store, "get_model_provider_policy_service", lambda: service)
    state = policy_store.PersistedModelProviderPolicy(
        approved_provider_ids=frozenset({"openai"}),
        version=3,
    )

    assert policy_store.apply_model_provider_policy_state(state)
    invalidate.assert_called_once_with()


@pytest.mark.parametrize("external_ids", [frozenset({"openai"}), frozenset()])
def test_explicitly_external_policy_service_is_not_invalidated(monkeypatch, external_ids):
    class ExternalPolicyService(BaseModelProviderPolicyService):
        def __init__(self) -> None:
            super().__init__()
            self.set_ready()

        @property
        def external_approved_provider_ids(self) -> frozenset[str]:
            return external_ids

        def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
            _ = (context, purpose)
            return candidate_provider_ids & external_ids

    service = ExternalPolicyService()
    invalidate = Mock(wraps=service.invalidate)
    monkeypatch.setattr(service, "invalidate", invalidate)
    monkeypatch.setattr(policy_store, "get_model_provider_policy_service", lambda: service)
    state = policy_store.PersistedModelProviderPolicy(
        approved_provider_ids=frozenset({"anthropic"}),
        version=3,
    )

    assert policy_store.apply_model_provider_policy_state(state) is False
    invalidate.assert_not_called()


def test_explicitly_external_builtin_subclass_does_not_receive_database_state(monkeypatch):
    class ExternalBuiltinPolicyService(ModelProviderPolicyService):
        @property
        def external_approved_provider_ids(self) -> frozenset[str]:
            return frozenset({"openai"})

    service = ExternalBuiltinPolicyService()
    service.set_approved_provider_ids({"openai"}, version=2)
    monkeypatch.setattr(policy_store, "get_model_provider_policy_service", lambda: service)
    state = policy_store.PersistedModelProviderPolicy(
        approved_provider_ids=frozenset(),
        version=3,
    )

    assert policy_store.apply_model_provider_policy_state(state) is False
    assert service.approved_provider_ids == frozenset({"openai"})
    assert service.policy_version == 2


def test_external_provider_does_not_block_database_owned_catalog_bundle_refresh(monkeypatch):
    class ExternalBuiltinPolicyService(ModelProviderPolicyService):
        @property
        def external_approved_provider_ids(self) -> frozenset[str]:
            return frozenset({"openai"})

    provider_service = ExternalBuiltinPolicyService()
    provider_service.set_approved_provider_ids({"openai"}, version=2)
    bundle_service = PolicyBundleService()
    catalog_service = CatalogPolicyService(bundle_service)
    snapshot = PolicyBundleSnapshot(
        revision=3,
        initialized=True,
        source="api",
        approved_provider_ids=frozenset({"anthropic"}),
        blocked_component_keys=frozenset({"PythonREPL"}),
    )
    state = policy_store.PersistedModelProviderPolicy(
        approved_provider_ids=snapshot.approved_provider_ids,
        version=snapshot.revision,
        bundle_snapshot=snapshot,
    )

    monkeypatch.setattr(policy_store, "get_model_provider_policy_service", lambda: provider_service)
    monkeypatch.setattr("lfx.services.deps.get_model_provider_policy_service", lambda: provider_service)
    monkeypatch.setattr("lfx.services.deps.get_policy_bundle_service", lambda: bundle_service)
    monkeypatch.setattr("lfx.services.deps.get_catalog_policy_service", lambda: catalog_service)

    assert policy_store.apply_model_provider_policy_state(state) is True
    assert bundle_service.snapshot is snapshot
    assert catalog_service.is_component_blocked("PythonREPL") is True
    assert provider_service.approved_provider_ids == frozenset({"openai"})


def test_replacement_is_one_atomic_versioned_update():
    statement = policy_store._replace_policy_statement(["openai"])
    postgres_sql = str(statement.compile(dialect=postgresql.dialect()))
    sqlite_sql = str(statement.compile(dialect=sqlite.dialect()))

    for compiled in (postgres_sql, sqlite_sql):
        assert compiled.startswith("UPDATE model_provider_policy SET")
        assert "version=(model_provider_policy.version + " in compiled
        assert "RETURNING" not in compiled


async def test_concurrent_sqlite_replacements_keep_complete_sets_and_distinct_versions(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'model-provider-policy.db'}",
        connect_args={"timeout": 30},
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(ModelProviderPolicy.__table__.create)
        async with session_maker() as session:
            session.add(ModelProviderPolicy())
            await session.commit()

        async def replace(provider_ids: set[str]):
            async with session_maker() as session:
                return await policy_store.replace_model_provider_policy_state(session, provider_ids)

        first, second = await asyncio.gather(
            replace({"openai"}),
            replace({"anthropic"}),
        )

        async with session_maker() as session:
            persisted = await policy_store.get_model_provider_policy_state(session)

        assert {first.version, second.version} == {1, 2}
        assert persisted.version == 2
        assert persisted.approved_provider_ids in (
            frozenset({"openai"}),
            frozenset({"anthropic"}),
        )
    finally:
        await engine.dispose()


async def test_missing_sqlite_singleton_is_never_treated_as_unrestricted(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'missing-model-provider-policy.db'}")
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(ModelProviderPolicy.__table__.create)

        async with session_maker() as session:
            with pytest.raises(policy_store.ModelProviderPolicyNotInitializedError, match="migrations"):
                await policy_store.get_model_provider_policy_state(session)
            with pytest.raises(policy_store.ModelProviderPolicyNotInitializedError, match="migrations"):
                await policy_store.replace_model_provider_policy_state(session, {"openai"})
    finally:
        await engine.dispose()


async def test_replace_refreshes_a_row_already_loaded_in_the_identity_map(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'fresh-model-provider-policy.db'}")
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(ModelProviderPolicy.__table__.create)

        async with session_maker() as session:
            session.add(ModelProviderPolicy())
            await session.commit()
            cached = await session.get(ModelProviderPolicy, 1)
            assert cached is not None

            state = await policy_store.replace_model_provider_policy_state(session, {"openai"})

            assert state == policy_store.PersistedModelProviderPolicy(
                approved_provider_ids=frozenset({"openai"}),
                version=1,
            )
            assert cached.approved_provider_ids == ["openai"]
            assert cached.version == 1
    finally:
        await engine.dispose()


async def test_second_worker_refreshes_a_committed_policy_version(monkeypatch):
    state = policy_store.PersistedModelProviderPolicy(
        approved_provider_ids=frozenset({"openai"}),
        version=8,
    )
    handling_worker = ModelProviderPolicyService()
    other_worker = ModelProviderPolicyService()

    monkeypatch.setattr(policy_store, "get_model_provider_policy_service", lambda: handling_worker)
    policy_store.apply_model_provider_policy_state(state)

    @asynccontextmanager
    async def session_scope():
        yield _ReadSession(["openai"], version=8)

    monkeypatch.setattr(refresh_module, "session_scope", session_scope)
    monkeypatch.setattr(policy_store, "get_model_provider_policy_service", lambda: other_worker)

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert changed is True
    assert handling_worker.approved_provider_ids == frozenset({"openai"})
    assert other_worker.approved_provider_ids == frozenset({"openai"})
    assert other_worker.policy_version == 8


async def test_refresh_skips_unchanged_version_without_invalidating_cache(monkeypatch):
    service = ModelProviderPolicyService()
    service.set_approved_provider_ids({"openai"}, version=8)

    @asynccontextmanager
    async def session_scope():
        yield _ReadSession(["openai"], version=8)

    monkeypatch.setattr(refresh_module, "session_scope", session_scope)
    monkeypatch.setattr(policy_store, "get_model_provider_policy_service", lambda: service)
    invalidate = Mock(wraps=service.invalidate)
    monkeypatch.setattr(service, "invalidate", invalidate)

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert changed is False
    invalidate.assert_not_called()


async def test_refresh_failure_denies_all_until_the_store_recovers(monkeypatch):
    service = ModelProviderPolicyService()
    service.set_approved_provider_ids({"openai", "anthropic"}, version=8)
    error_message = "policy store unavailable"

    @asynccontextmanager
    async def failing_session_scope():
        raise ConnectionError(error_message)
        yield

    monkeypatch.setattr(refresh_module, "session_scope", failing_session_scope)
    monkeypatch.setattr(refresh_module, "get_model_provider_policy_service", lambda: service)
    monkeypatch.setattr(
        refresh_module.logger,
        "aerror",
        AsyncMock(side_effect=RuntimeError(error_message)),
    )

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert changed is True
    assert service.policy_source_available is False
