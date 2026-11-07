"""Durable policy semantics while N-1 and current workers share a database."""

from __future__ import annotations

# ruff: noqa: F811
import hashlib
import json
from uuid import uuid4

import pytest
from langflow.services import model_provider_policy as provider_store
from langflow.services import policy_bundle as policy_store
from langflow.services.database.models.model_provider_policy import ModelProviderPolicy
from langflow.services.database.models.policy_bundle import PolicyBundleActive, PolicyBundleRevision
from lfx.integrations.policy_constants import INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID
from lfx.services.integration_policy import IntegrationPolicyContext, IntegrationPolicyPurpose, IntegrationPolicyService
from lfx.services.policy_bundle import PolicyBundleService

from .test_policy_bundle_store import bundle_session_maker  # noqa: F401

_CANDIDATES = frozenset({"google", "slack"})


def _legacy_content_hash(row: PolicyBundleRevision) -> str:
    """Hash the stored lists using the N-1 canonical payload contract."""
    payload = {
        "approved_provider_ids": sorted(set(row.approved_provider_ids)),
        "blocked_component_keys": sorted(set(row.blocked_component_keys)),
        "blocked_template_keys": sorted(set(row.blocked_template_keys)),
    }
    for field in (
        "blocked_model_keys",
        "approved_integration_provider_ids",
        "blocked_integration_action_keys",
    ):
        values = getattr(row, field)
        if values:
            payload[field] = sorted(set(values))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def _replace(session_maker, *, expected_revision: int, integration_providers):
    async with session_maker() as session:
        return await policy_store.replace_policy_bundle_state(
            session,
            expected_revision=expected_revision,
            approved_provider_ids={"openai"},
            blocked_component_keys={"OldComponent"},
            blocked_template_keys={"old-template"},
            approved_integration_provider_ids=integration_providers,
            actor_user_id=uuid4(),
        )


async def _legacy_model_provider_edit(session_maker):
    """Carry the ceiling through an N-1 read/write, without the new codec.

    N-1 ``_snapshot_from_row`` uses ``frozenset(raw or [])`` and its writer
    serializes ``sorted(snapshot.approved_integration_provider_ids)``. Keep
    those boundaries explicit: using the current store here would miss the
    rolling-upgrade regression this test protects against.
    """
    async with session_maker() as session:
        active = await session.get(PolicyBundleActive, 1)
        row = await session.get(PolicyBundleRevision, active.revision)
        legacy_ceiling = frozenset(row.approved_integration_provider_ids or [])
        next_row = PolicyBundleRevision(
            **{
                **row.model_dump(),
                "revision": active.revision + 1,
                "approved_provider_ids": ["anthropic", "openai"],
                "approved_integration_provider_ids": sorted(legacy_ceiling),
                "source": "api",
            }
        )
        next_row.content_hash = _legacy_content_hash(next_row)
        active.revision = next_row.revision
        provider = await session.get(ModelProviderPolicy, 1)
        provider.approved_provider_ids = next_row.approved_provider_ids
        provider.version = next_row.revision
        session.add(next_row)
        await session.commit()
        return legacy_ceiling, next_row.revision


def _allowed_by_current_worker(snapshot) -> frozenset[str]:
    bundle = PolicyBundleService()
    bundle.publish(snapshot)
    return (
        IntegrationPolicyService(policy_bundle_service=bundle)
        .resolve(
            context=IntegrationPolicyContext(),
            candidate_provider_ids=_CANDIDATES,
            purpose=IntegrationPolicyPurpose.USE,
        )
        .allowed_provider_ids
    )


@pytest.mark.parametrize("legacy_value", [None, []], ids=["null", "empty-list"])
async def test_legacy_empty_writes_remain_unrestricted_after_a_new_worker_save(
    bundle_session_maker,
    legacy_value,
):
    async with bundle_session_maker() as session:
        row = await session.get(PolicyBundleRevision, 1)
        row.approved_integration_provider_ids = legacy_value
        await session.commit()
        initial = await policy_store.get_policy_bundle_state(session)
    assert initial.approved_integration_provider_ids is None

    await _replace(bundle_session_maker, expected_revision=1, integration_providers=None)
    legacy_ceiling, revision = await _legacy_model_provider_edit(bundle_session_maker)

    # An old replica rewrites even NULL as [] after an unrelated model edit.
    assert legacy_ceiling == frozenset()
    async with bundle_session_maker() as session:
        row = await session.get(PolicyBundleRevision, revision)
        assert row.approved_integration_provider_ids == []
        current = await policy_store.get_policy_bundle_state(session)
    assert current.approved_integration_provider_ids is None
    assert _allowed_by_current_worker(current) == _CANDIDATES
    assert current.approved_provider_ids == frozenset({"anthropic", "openai"})


async def test_new_deny_all_survives_an_old_worker_read_and_unrelated_write(bundle_session_maker):
    await _replace(bundle_session_maker, expected_revision=1, integration_providers=[])
    async with bundle_session_maker() as session:
        row = await session.get(PolicyBundleRevision, 2)
        assert row.approved_integration_provider_ids == [INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID]
        assert row.content_hash == _legacy_content_hash(row)

    legacy_ceiling, revision = await _legacy_model_provider_edit(bundle_session_maker)
    # N-1 enforces every nonempty ceiling by intersecting it with candidates.
    assert legacy_ceiling
    assert not (_CANDIDATES & legacy_ceiling)
    async with bundle_session_maker() as session:
        current = await policy_store.get_policy_bundle_state(session)
        row = await session.get(PolicyBundleRevision, revision)
        assert row.content_hash == _legacy_content_hash(row)
    assert current.approved_integration_provider_ids == frozenset()
    assert not _allowed_by_current_worker(current)
    assert current.approved_provider_ids == frozenset({"anthropic", "openai"})


async def test_model_provider_facet_edit_preserves_deny_all(bundle_session_maker):
    await _replace(bundle_session_maker, expected_revision=1, integration_providers=[])
    async with bundle_session_maker() as session:
        await provider_store.replace_model_provider_policy_state(
            session, {"anthropic", "openai"}, actor_user_id=uuid4()
        )
    async with bundle_session_maker() as session:
        current = await policy_store.get_policy_bundle_state(session)
    assert current.approved_integration_provider_ids == frozenset()
    assert not _allowed_by_current_worker(current)


async def test_rollback_and_history_keep_unrestricted_distinct_from_deny_all(bundle_session_maker):
    denied = await _replace(bundle_session_maker, expected_revision=1, integration_providers=[])
    unrestricted = await _replace(bundle_session_maker, expected_revision=2, integration_providers=None)
    async with bundle_session_maker() as session:
        rollback = await policy_store.rollback_policy_bundle_state(
            session, expected_revision=3, target_revision=2, actor_user_id=uuid4()
        )
    assert rollback.approved_integration_provider_ids == frozenset()
    assert rollback.content_hash == denied.content_hash
    assert not _allowed_by_current_worker(rollback)

    async with bundle_session_maker() as session:
        restored = await policy_store.rollback_policy_bundle_state(
            session, expected_revision=4, target_revision=3, actor_user_id=uuid4()
        )
        history = await policy_store.list_policy_bundle_history(session)
    assert restored.approved_integration_provider_ids is None
    assert restored.content_hash == unrestricted.content_hash
    assert _allowed_by_current_worker(restored) == _CANDIDATES
    assert [item.approved_integration_provider_ids for item in history] == [
        None,
        frozenset(),
        None,
        frozenset(),
        None,
    ]


@pytest.mark.parametrize("integration_providers", [None, [], ["google"]], ids=["unrestricted", "deny-all", "allowlist"])
async def test_new_hash_matches_n_minus_one_hash_of_stored_policy(
    bundle_session_maker,
    integration_providers,
):
    snapshot = await _replace(bundle_session_maker, expected_revision=1, integration_providers=integration_providers)
    async with bundle_session_maker() as session:
        row = await session.get(PolicyBundleRevision, snapshot.revision)
        assert snapshot.content_hash == _legacy_content_hash(row)


@pytest.mark.parametrize(
    "integration_providers",
    [
        [INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID],
        ["google", INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID],
        [f"  {INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID.upper()}  "],
    ],
    ids=["marker", "mixed-marker", "normalized-marker"],
)
async def test_reserved_identity_is_rejected_before_cas(bundle_session_maker, integration_providers):
    with pytest.raises(ValueError, match="reserved"):
        await _replace(bundle_session_maker, expected_revision=1, integration_providers=integration_providers)

    async with bundle_session_maker() as session:
        current = await policy_store.get_policy_bundle_state(session)
    assert current.revision == 1
    assert current.approved_integration_provider_ids is None
    assert _allowed_by_current_worker(current) == _CANDIDATES
