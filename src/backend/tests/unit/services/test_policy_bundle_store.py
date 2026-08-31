"""Atomic store and cross-worker runtime tests for shared policy bundles."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from langflow.services import deps as langflow_service_deps
from langflow.services import policy_bundle as policy_store
from langflow.services.database.models.catalog_policy import CatalogPolicyRule, CatalogResourceKind
from langflow.services.database.models.model_provider_policy import ModelProviderPolicy
from langflow.services.database.models.policy_bundle import PolicyBundleActive, PolicyBundleRevision
from langflow.services.database.models.user.model import User
from langflow.services.task import model_provider_policy_refresh as refresh_module
from lfx.services import deps as lfx_service_deps
from lfx.services.catalog_policy import CatalogPolicyService
from lfx.services.catalog_policy.base import BaseCatalogPolicyService, CatalogPolicySnapshot
from lfx.services.model_provider_policy import ModelProviderPolicyService
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

_INITIAL_PROVIDERS = frozenset({"openai"})
_INITIAL_COMPONENTS = frozenset({"OldComponent"})
_INITIAL_TEMPLATES = frozenset({"old-template"})


def test_policy_bundle_revision_resolves_created_by_for_validation_and_schema():
    actor_id = uuid4()
    revision = PolicyBundleRevision.model_validate(
        {
            "revision": 1,
            "initialized": True,
            "approved_provider_ids": [],
            "blocked_component_keys": [],
            "blocked_template_keys": [],
            "content_hash": "0" * 64,
            "created_by": str(actor_id),
        }
    )

    assert revision.created_by == actor_id
    assert "created_by" in PolicyBundleRevision.model_json_schema()["properties"]
    assert all(foreign_key.parent.name != "created_by" for foreign_key in PolicyBundleRevision.__table__.foreign_keys)


@pytest.fixture
async def bundle_session_maker(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'policy-bundle.db'}",
        connect_args={"timeout": 30},
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: SQLModel.metadata.create_all(
                sync_connection,
                tables=[
                    User.__table__,
                    ModelProviderPolicy.__table__,
                    CatalogPolicyRule.__table__,
                    PolicyBundleRevision.__table__,
                    PolicyBundleActive.__table__,
                ],
            )
        )

    initial_hash = policy_store.policy_bundle_content_hash(
        approved_provider_ids=_INITIAL_PROVIDERS,
        blocked_component_keys=_INITIAL_COMPONENTS,
        blocked_template_keys=_INITIAL_TEMPLATES,
    )
    async with session_maker() as session:
        session.add_all(
            [
                PolicyBundleRevision(
                    revision=1,
                    initialized=True,
                    approved_provider_ids=sorted(_INITIAL_PROVIDERS),
                    blocked_component_keys=sorted(_INITIAL_COMPONENTS),
                    blocked_template_keys=sorted(_INITIAL_TEMPLATES),
                    content_hash=initial_hash,
                    source="migration",
                    reason="initial",
                ),
                PolicyBundleActive(revision=1, initialized=True),
                ModelProviderPolicy(
                    approved_provider_ids=sorted(_INITIAL_PROVIDERS),
                    version=1,
                ),
                CatalogPolicyRule(
                    resource_kind=CatalogResourceKind.COMPONENT.value,
                    resource_key="OldComponent",
                ),
                CatalogPolicyRule(
                    resource_kind=CatalogResourceKind.TEMPLATE.value,
                    resource_key="old-template",
                ),
            ]
        )
        await session.commit()

    yield session_maker
    await engine.dispose()


async def _read_active(session_maker) -> PolicyBundleSnapshot:
    async with session_maker() as session:
        return await policy_store.get_policy_bundle_state(session)


def _bundle_value(snapshot: PolicyBundleSnapshot) -> tuple:
    """Compare persisted semantics without depending on SQLite timezone reflection."""
    timestamp = snapshot.created_at.replace(tzinfo=None) if snapshot.created_at is not None else None
    return (
        snapshot.revision,
        snapshot.approved_provider_ids,
        snapshot.blocked_component_keys,
        snapshot.blocked_template_keys,
        snapshot.content_hash,
        snapshot.created_by,
        timestamp,
        snapshot.reason,
        snapshot.rollback_of_revision,
    )


async def test_concurrent_cas_replacements_commit_one_complete_bundle_without_mixing_facets(
    bundle_session_maker,
):
    actor_id = uuid4()
    proposals = [
        {
            "approved_provider_ids": {"anthropic"},
            "blocked_component_keys": {"AnthropicModel"},
            "blocked_template_keys": {"anthropic-template"},
            "reason": "anthropic policy",
        },
        {
            "approved_provider_ids": {"google.generativeai"},
            "blocked_component_keys": {"GoogleModel"},
            "blocked_template_keys": {"google-template"},
            "reason": "google policy",
        },
    ]

    async def replace(proposal):
        async with bundle_session_maker() as session:
            return await policy_store.replace_policy_bundle_state(
                session,
                expected_revision=1,
                actor_user_id=actor_id,
                **proposal,
            )

    results = await asyncio.gather(*(replace(proposal) for proposal in proposals), return_exceptions=True)
    committed = [result for result in results if isinstance(result, PolicyBundleSnapshot)]
    conflicts = [result for result in results if isinstance(result, policy_store.PolicyBundleRevisionConflictError)]

    assert len(committed) == 1
    assert len(conflicts) == 1
    assert conflicts[0].expected_revision == 1
    assert conflicts[0].active_revision == 2

    persisted = await _read_active(bundle_session_maker)
    complete_states = {
        (
            frozenset(proposal["approved_provider_ids"]),
            frozenset(proposal["blocked_component_keys"]),
            frozenset(proposal["blocked_template_keys"]),
        )
        for proposal in proposals
    }
    assert persisted.revision == 2
    assert persisted.initialized is True
    assert persisted.source == "api"
    assert (
        persisted.approved_provider_ids,
        persisted.blocked_component_keys,
        persisted.blocked_template_keys,
    ) in complete_states
    assert _bundle_value(persisted) == _bundle_value(committed[0])

    async with bundle_session_maker() as session:
        history = await policy_store.list_policy_bundle_history(session)
        legacy_provider = await session.get(ModelProviderPolicy, 1)
        legacy_rules = list((await session.exec(select(CatalogPolicyRule))).all())

    assert [snapshot.revision for snapshot in history] == [2, 1]
    assert legacy_provider is not None
    assert legacy_provider.version == persisted.revision
    assert frozenset(legacy_provider.approved_provider_ids) == persisted.approved_provider_ids
    assert {
        row.resource_key for row in legacy_rules if row.resource_kind == CatalogResourceKind.COMPONENT.value
    } == persisted.blocked_component_keys
    assert {
        row.resource_key for row in legacy_rules if row.resource_kind == CatalogResourceKind.TEMPLATE.value
    } == persisted.blocked_template_keys


async def test_rollback_copies_old_content_into_a_new_immutable_revision(bundle_session_maker):
    first_actor = uuid4()
    rollback_actor = uuid4()
    async with bundle_session_maker() as session:
        revision_two = await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=1,
            approved_provider_ids={"anthropic"},
            blocked_component_keys={"SecondComponent"},
            blocked_template_keys={"second-template"},
            actor_user_id=first_actor,
            reason="second",
        )
    async with bundle_session_maker() as session:
        revision_three = await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=revision_two.revision,
            approved_provider_ids={"google.generativeai"},
            blocked_component_keys={"ThirdComponent"},
            blocked_template_keys={"third-template"},
            actor_user_id=first_actor,
            reason="third",
        )
    async with bundle_session_maker() as session:
        rolled_back = await policy_store.rollback_policy_bundle_state(
            session,
            expected_revision=revision_three.revision,
            target_revision=1,
            actor_user_id=rollback_actor,
            reason="incident rollback",
        )

    assert rolled_back.revision == 4
    assert rolled_back.initialized is True
    assert rolled_back.source == "rollback"
    assert rolled_back.approved_provider_ids == _INITIAL_PROVIDERS
    assert rolled_back.blocked_component_keys == _INITIAL_COMPONENTS
    assert rolled_back.blocked_template_keys == _INITIAL_TEMPLATES
    assert rolled_back.rollback_of_revision == 1
    assert rolled_back.created_by == rollback_actor
    assert rolled_back.reason == "incident rollback"

    async with bundle_session_maker() as session:
        history = await policy_store.list_policy_bundle_history(session)

    assert [snapshot.revision for snapshot in history] == [4, 3, 2, 1]
    by_revision = {snapshot.revision: snapshot for snapshot in history}
    assert by_revision[1].reason == "initial"
    assert _bundle_value(by_revision[2]) == _bundle_value(revision_two)
    assert _bundle_value(by_revision[3]) == _bundle_value(revision_three)
    assert by_revision[1].content_hash == rolled_back.content_hash
    assert by_revision[2].rollback_of_revision is None
    assert by_revision[3].rollback_of_revision is None


async def test_stale_expected_revision_leaves_active_state_and_history_unchanged(bundle_session_maker):
    async with bundle_session_maker() as session:
        current = await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=1,
            approved_provider_ids={"anthropic"},
            blocked_component_keys={"CurrentComponent"},
            blocked_template_keys={"current-template"},
            actor_user_id=uuid4(),
        )

    async with bundle_session_maker() as session:
        with pytest.raises(policy_store.PolicyBundleRevisionConflictError) as exc_info:
            await policy_store.replace_policy_bundle_state(
                session,
                expected_revision=1,
                approved_provider_ids={"openai"},
                blocked_component_keys={"StaleComponent"},
                blocked_template_keys={"stale-template"},
                actor_user_id=uuid4(),
            )

    assert exc_info.value.expected_revision == 1
    assert exc_info.value.active_revision == 2
    assert _bundle_value(await _read_active(bundle_session_maker)) == _bundle_value(current)
    async with bundle_session_maker() as session:
        assert [item.revision for item in await policy_store.list_policy_bundle_history(session)] == [2, 1]


async def test_environment_bootstrap_initializes_a_pristine_bundle_exactly_once(bundle_session_maker):
    empty_hash = policy_store.policy_bundle_content_hash(
        approved_provider_ids=[],
        blocked_component_keys=[],
        blocked_template_keys=[],
    )
    async with bundle_session_maker() as session:
        active = await session.get(PolicyBundleActive, 1)
        initial = await session.get(PolicyBundleRevision, 1)
        legacy_provider = await session.get(ModelProviderPolicy, 1)
        assert active is not None
        assert initial is not None
        assert legacy_provider is not None
        active.initialized = False
        initial.initialized = False
        initial.approved_provider_ids = []
        initial.blocked_component_keys = []
        initial.blocked_template_keys = []
        initial.content_hash = empty_hash
        legacy_provider.approved_provider_ids = []
        legacy_provider.version = 0
        for rule in list((await session.exec(select(CatalogPolicyRule))).all()):
            await session.delete(rule)
        await session.commit()

    async with bundle_session_maker() as session:
        bootstrapped, created = await policy_store.bootstrap_policy_bundle_if_pristine(
            session,
            approved_provider_ids={"anthropic"},
            blocked_component_keys={"EnvironmentComponent"},
            blocked_template_keys={"environment-template"},
            reason="deployment bootstrap",
        )
    async with bundle_session_maker() as session:
        repeated, repeated_created = await policy_store.bootstrap_policy_bundle_if_pristine(
            session,
            approved_provider_ids={"openai"},
            blocked_component_keys={"MustNotReplace"},
            blocked_template_keys={"must-not-replace"},
        )

    assert created is True
    assert bootstrapped.revision == 2
    assert bootstrapped.initialized is True
    assert bootstrapped.source == "environment"
    assert bootstrapped.approved_provider_ids == frozenset({"anthropic"})
    assert repeated_created is False
    assert _bundle_value(repeated) == _bundle_value(bootstrapped)
    async with bundle_session_maker() as session:
        history = await policy_store.list_policy_bundle_history(session)
        pristine = await policy_store.get_policy_bundle_state(session, revision=1)
    assert [(item.revision, item.initialized) for item in history] == [(2, True), (1, False)]
    assert pristine.initialized is False


def test_runtime_publishes_one_immutable_snapshot_for_provider_and_catalog_facets(monkeypatch):
    bundle_service = PolicyBundleService()
    catalog_service = CatalogPolicyService(bundle_service)
    provider_service = ModelProviderPolicyService(bundle_service)
    old_snapshot = bundle_service.snapshot
    new_snapshot = PolicyBundleSnapshot(
        revision=9,
        initialized=True,
        source="api",
        approved_provider_ids={"anthropic"},
        blocked_component_keys={"OpenAIModel"},
        blocked_template_keys={"starter-template"},
        content_hash="9" * 64,
        reason="one atomic publication",
    )
    monkeypatch.setattr(langflow_service_deps, "get_policy_bundle_service", lambda: bundle_service)
    monkeypatch.setattr(langflow_service_deps, "get_catalog_policy_service", lambda: catalog_service)
    monkeypatch.setattr(lfx_service_deps, "get_policy_bundle_service", lambda: bundle_service)
    monkeypatch.setattr(lfx_service_deps, "get_catalog_policy_service", lambda: catalog_service)
    monkeypatch.setattr(lfx_service_deps, "get_model_provider_policy_service", lambda: provider_service)

    assert policy_store.apply_policy_bundle_state(new_snapshot) is True

    assert bundle_service.snapshot is new_snapshot
    assert catalog_service.policy_bundle_snapshot is new_snapshot
    assert provider_service.approved_provider_ids == new_snapshot.approved_provider_ids
    assert provider_service.policy_version == new_snapshot.revision
    assert catalog_service.snapshot.blocked_component_keys == new_snapshot.blocked_component_keys
    assert catalog_service.snapshot.blocked_template_keys == new_snapshot.blocked_template_keys
    assert old_snapshot == PolicyBundleSnapshot()


def test_runtime_applies_bundle_to_database_owned_catalog_plugin_with_independent_state(monkeypatch):
    class IndependentCatalogPolicy(BaseCatalogPolicyService):
        def __init__(self) -> None:
            super().__init__()
            self._snapshot = CatalogPolicySnapshot()
            self.applied: list[PolicyBundleSnapshot] = []
            self.set_ready()

        @property
        def snapshot(self) -> CatalogPolicySnapshot:
            return self._snapshot

        @property
        def supports_policy_bundle_updates(self) -> bool:
            return True

        def apply_policy_bundle(self, snapshot: PolicyBundleSnapshot) -> bool:
            self.applied.append(snapshot)
            self._snapshot = CatalogPolicySnapshot(
                blocked_component_keys=snapshot.blocked_component_keys,
                blocked_template_keys=snapshot.blocked_template_keys,
            )
            return True

    bundle_service = PolicyBundleService()
    catalog_service = IndependentCatalogPolicy()
    provider_service = ModelProviderPolicyService(bundle_service)
    snapshot = PolicyBundleSnapshot(
        revision=4,
        initialized=True,
        source="api",
        approved_provider_ids={"openai"},
        blocked_component_keys={"PythonREPL"},
        blocked_template_keys={"Starter"},
        content_hash="4" * 64,
    )
    monkeypatch.setattr(lfx_service_deps, "get_policy_bundle_service", lambda: bundle_service)
    monkeypatch.setattr(lfx_service_deps, "get_catalog_policy_service", lambda: catalog_service)
    monkeypatch.setattr(lfx_service_deps, "get_model_provider_policy_service", lambda: provider_service)

    assert policy_store.apply_policy_bundle_state(snapshot) is True
    assert catalog_service.applied == [snapshot]
    assert catalog_service.snapshot.blocked_component_keys == frozenset({"PythonREPL"})
    assert catalog_service.snapshot.blocked_template_keys == frozenset({"Starter"})

    stale = PolicyBundleSnapshot(
        revision=3,
        initialized=True,
        source="poll",
        approved_provider_ids={"anthropic"},
        blocked_component_keys={"OpenAIModel"},
        blocked_template_keys={"OldStarter"},
        content_hash="3" * 64,
    )
    assert policy_store.apply_policy_bundle_state(stale) is True
    assert bundle_service.snapshot is snapshot
    assert catalog_service.applied == [snapshot, snapshot]
    assert catalog_service.snapshot.blocked_component_keys == frozenset({"PythonREPL"})
    assert catalog_service.snapshot.blocked_template_keys == frozenset({"Starter"})
    assert provider_service.approved_provider_ids == frozenset({"openai"})
    assert provider_service.policy_version == 4


def test_runtime_rejects_database_owned_catalog_plugin_without_bundle_update_support(monkeypatch):
    class LegacyCatalogPolicy(BaseCatalogPolicyService):
        def __init__(self) -> None:
            super().__init__()
            self.set_ready()

        @property
        def snapshot(self) -> CatalogPolicySnapshot:
            return CatalogPolicySnapshot()

    bundle_service = PolicyBundleService()
    catalog_service = LegacyCatalogPolicy()
    provider_service = ModelProviderPolicyService(bundle_service)
    snapshot = PolicyBundleSnapshot(revision=2, initialized=True, content_hash="2" * 64)
    monkeypatch.setattr(lfx_service_deps, "get_policy_bundle_service", lambda: bundle_service)
    monkeypatch.setattr(lfx_service_deps, "get_catalog_policy_service", lambda: catalog_service)
    monkeypatch.setattr(lfx_service_deps, "get_model_provider_policy_service", lambda: provider_service)

    with pytest.raises(policy_store.PolicyBundleApplicationNotSupportedError, match="upgrade the plugin"):
        policy_store.apply_policy_bundle_state(snapshot)

    assert bundle_service.snapshot == PolicyBundleSnapshot()
    assert provider_service.policy_version == 0


async def test_second_worker_poll_refreshes_all_facets_from_one_committed_revision(
    monkeypatch,
    bundle_session_maker,
):
    async with bundle_session_maker() as session:
        committed = await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=1,
            approved_provider_ids={"anthropic"},
            blocked_component_keys={"OpenAIModel"},
            blocked_template_keys={"starter-template"},
            actor_user_id=uuid4(),
            reason="cross-worker",
        )

    second_bundle_service = PolicyBundleService()
    second_catalog_service = CatalogPolicyService(second_bundle_service)
    second_provider_service = ModelProviderPolicyService(second_bundle_service)

    @asynccontextmanager
    async def session_scope():
        async with bundle_session_maker() as session:
            yield session

    monkeypatch.setattr(refresh_module, "session_scope", session_scope)
    monkeypatch.setattr(
        refresh_module,
        "get_model_provider_policy_service",
        lambda: second_provider_service,
    )
    monkeypatch.setattr(
        refresh_module,
        "get_policy_bundle_service",
        lambda: second_bundle_service,
        raising=False,
    )
    monkeypatch.setattr(langflow_service_deps, "get_policy_bundle_service", lambda: second_bundle_service)
    monkeypatch.setattr(langflow_service_deps, "get_catalog_policy_service", lambda: second_catalog_service)
    monkeypatch.setattr(lfx_service_deps, "get_policy_bundle_service", lambda: second_bundle_service)
    monkeypatch.setattr(lfx_service_deps, "get_catalog_policy_service", lambda: second_catalog_service)
    monkeypatch.setattr(lfx_service_deps, "get_model_provider_policy_service", lambda: second_provider_service)

    changed = await refresh_module.ModelProviderPolicyRefreshWorker()._run_once()

    assert changed is True
    assert _bundle_value(second_bundle_service.snapshot) == _bundle_value(committed)
    assert second_catalog_service.policy_bundle_snapshot is second_bundle_service.snapshot
    assert second_provider_service.approved_provider_ids == committed.approved_provider_ids
    assert second_provider_service.policy_version == committed.revision
    assert second_catalog_service.snapshot.blocked_component_keys == committed.blocked_component_keys
    assert second_catalog_service.snapshot.blocked_template_keys == committed.blocked_template_keys


async def test_replace_persists_and_canonicalizes_blocked_model_keys(bundle_session_maker):
    actor_id = uuid4()
    async with bundle_session_maker() as session:
        committed = await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=1,
            approved_provider_ids=_INITIAL_PROVIDERS,
            blocked_component_keys=_INITIAL_COMPONENTS,
            blocked_template_keys=_INITIAL_TEMPLATES,
            blocked_model_keys={"OpenAI::gpt-blocked", "openai::gpt-blocked", "bare-blocked"},
            actor_user_id=actor_id,
            reason="block models",
        )

    assert committed.blocked_model_keys == frozenset({"openai::gpt-blocked", "bare-blocked"})
    assert committed.content_hash == policy_store.policy_bundle_content_hash(
        approved_provider_ids=_INITIAL_PROVIDERS,
        blocked_component_keys=_INITIAL_COMPONENTS,
        blocked_template_keys=_INITIAL_TEMPLATES,
        blocked_model_keys={"openai::gpt-blocked", "bare-blocked"},
    )
    durable = await _read_active(bundle_session_maker)
    assert durable.blocked_model_keys == committed.blocked_model_keys
    assert durable.content_hash == committed.content_hash


async def test_replace_without_model_keys_keeps_legacy_content_hash_shape(bundle_session_maker):
    async with bundle_session_maker() as session:
        committed = await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=1,
            approved_provider_ids=_INITIAL_PROVIDERS,
            blocked_component_keys=_INITIAL_COMPONENTS,
            blocked_template_keys=_INITIAL_TEMPLATES,
            actor_user_id=uuid4(),
        )

    assert committed.blocked_model_keys == frozenset()
    assert committed.content_hash == policy_store.policy_bundle_content_hash(
        approved_provider_ids=_INITIAL_PROVIDERS,
        blocked_component_keys=_INITIAL_COMPONENTS,
        blocked_template_keys=_INITIAL_TEMPLATES,
    )


async def test_malformed_blocked_model_key_rejected_before_any_write(bundle_session_maker):
    async with bundle_session_maker() as session:
        with pytest.raises(ValueError, match="Blocked-model key"):
            await policy_store.replace_policy_bundle_state(
                session,
                expected_revision=1,
                approved_provider_ids=_INITIAL_PROVIDERS,
                blocked_component_keys=_INITIAL_COMPONENTS,
                blocked_template_keys=_INITIAL_TEMPLATES,
                blocked_model_keys={"::claude-blocked"},
                actor_user_id=uuid4(),
            )

    active = await _read_active(bundle_session_maker)
    assert active.revision == 1
    assert active.blocked_model_keys == frozenset()


async def test_rollback_restores_blocked_model_keys(bundle_session_maker):
    async with bundle_session_maker() as session:
        revision_two = await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=1,
            approved_provider_ids=_INITIAL_PROVIDERS,
            blocked_component_keys=_INITIAL_COMPONENTS,
            blocked_template_keys=_INITIAL_TEMPLATES,
            blocked_model_keys={"openai::gpt-blocked"},
            actor_user_id=uuid4(),
            reason="block models",
        )
    async with bundle_session_maker() as session:
        revision_three = await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=revision_two.revision,
            approved_provider_ids=_INITIAL_PROVIDERS,
            blocked_component_keys=_INITIAL_COMPONENTS,
            blocked_template_keys=_INITIAL_TEMPLATES,
            actor_user_id=uuid4(),
            reason="unblock models",
        )
    assert revision_three.blocked_model_keys == frozenset()

    async with bundle_session_maker() as session:
        rolled_back = await policy_store.rollback_policy_bundle_state(
            session,
            expected_revision=revision_three.revision,
            target_revision=revision_two.revision,
            actor_user_id=uuid4(),
            reason="restore model blocks",
        )

    assert rolled_back.blocked_model_keys == frozenset({"openai::gpt-blocked"})
    assert rolled_back.rollback_of_revision == revision_two.revision
    assert rolled_back.content_hash == revision_two.content_hash


async def test_legacy_provider_ceiling_write_preserves_blocked_model_keys(bundle_session_maker):
    from langflow.services import model_provider_policy as legacy_provider_store

    async with bundle_session_maker() as session:
        await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=1,
            approved_provider_ids=_INITIAL_PROVIDERS,
            blocked_component_keys=_INITIAL_COMPONENTS,
            blocked_template_keys=_INITIAL_TEMPLATES,
            blocked_model_keys={"openai::gpt-blocked"},
            actor_user_id=uuid4(),
        )

    async with bundle_session_maker() as session:
        persisted = await legacy_provider_store.replace_model_provider_policy_state(
            session,
            {"openai", "anthropic"},
            actor_user_id=uuid4(),
        )

    assert persisted.bundle_snapshot is not None
    assert persisted.bundle_snapshot.blocked_model_keys == frozenset({"openai::gpt-blocked"})
    assert persisted.approved_provider_ids == frozenset({"openai", "anthropic"})
