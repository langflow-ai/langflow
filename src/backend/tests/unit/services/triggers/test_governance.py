"""Trigger policy cannot be bypassed by an existing saved trigger or queued event."""

from unittest.mock import AsyncMock

import pytest
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, ledger
from langflow.services.triggers.service import TriggerService
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def policy(monkeypatch):
    bundle = PolicyBundleService()
    monkeypatch.setattr("lfx.services.deps.get_policy_bundle_service", lambda: bundle)
    return bundle


async def test_enable_refuses_an_existing_kind_outside_the_approved_set(make_trigger, policy):
    identifier = await make_trigger(config={"cron": "0 * * * *", "timezone": "UTC"})
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset({"google.calendar"})))
    async with session_scope() as session:
        row = await session.get(Trigger, identifier)
        with pytest.raises(ValueError, match="Blocked by trigger policy"):
            await TriggerService().enable(session, row=row)


async def test_queued_event_is_blocked_before_any_background_job(make_trigger, fake_background_service, policy):
    identifier = await make_trigger()
    async with session_scope() as session:
        event, _ = await ledger.append_event(session, trigger_id=identifier, dedupe_key="blocked")
        event_id = event.id
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset()))
    await dispatcher.run_once(owner="policy-test")
    assert fake_background_service.submits == []
    async with session_scope() as session:
        assert (await session.get(Trigger, identifier)).state == TriggerState.PAUSED.value
        assert (await session.get(TriggerEvent, event_id)).error == "policy_blocked"


async def test_source_hint_does_not_consume_a_run_quota(make_trigger, policy, monkeypatch):
    from langflow.services.triggers import source_runtime

    identifier = await make_trigger(kind="google.calendar", provider="google")
    async with session_scope() as session:
        await ledger.append_event(session, trigger_id=identifier, dedupe_key="hint", payload={"_source_hint": True})
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset({"google.calendar"})))
    hook = AsyncMock()
    monkeypatch.setattr(TriggerService, "authorize_trigger", hook)
    reconcile = AsyncMock()
    monkeypatch.setattr(source_runtime, "reconcile_source", reconcile)
    await dispatcher.run_once(owner="policy-test")
    reconcile.assert_awaited_once()
    hook.assert_not_awaited()


async def test_approved_enable_calls_the_enterprise_hook_without_widening_the_ceiling(
    make_trigger, policy, monkeypatch
):
    identifier = await make_trigger(config={"cron": "0 * * * *", "timezone": "UTC"})
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset({"schedule"})))
    service = TriggerService()
    hook = AsyncMock()
    monkeypatch.setattr(service, "authorize_trigger", hook, raising=False)
    async with session_scope() as session:
        row = await session.get(Trigger, identifier)
        await service.enable(session, row=row)
    hook.assert_awaited_once()
    assert hook.call_args.kwargs["context"].kind == "schedule"
    assert hook.call_args.kwargs["context"].purpose.value == "enable"


async def test_restricted_policy_fails_closed_when_refresh_is_unavailable(make_trigger, policy):
    identifier = await make_trigger(config={"cron": "0 * * * *", "timezone": "UTC"})
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset({"schedule"})))
    policy.mark_source_unavailable()
    async with session_scope() as session:
        row = await session.get(Trigger, identifier)
        with pytest.raises(ValueError, match="Blocked by trigger policy"):
            await TriggerService().enable(session, row=row)


async def test_provider_ceiling_blocks_an_explicitly_approved_trigger_kind(policy, trigger_owner):
    from langflow.services.triggers.policy import (
        TriggerPolicyContext,
        TriggerPolicyError,
        TriggerPolicyPurpose,
        require_trigger_allowed,
    )

    policy.publish(
        PolicyBundleSnapshot(
            revision=2,
            approved_trigger_kinds=frozenset({"google.gmail"}),
            approved_integration_provider_ids=frozenset({"microsoft"}),
        )
    )
    service = TriggerService()
    service.authorize_trigger = AsyncMock()
    with pytest.raises(TriggerPolicyError, match="outside the approved integration set") as raised:
        await require_trigger_allowed(
            TriggerPolicyContext(user_id=trigger_owner, kind="google.gmail", purpose=TriggerPolicyPurpose.ENABLE),
            service=service,
        )
    service.authorize_trigger.assert_not_awaited()
    from langflow.services.triggers.error_codes import last_error_code, refusal_detail

    assert refusal_detail(raised.value)["code"] == "governance_blocked"
    assert last_error_code(str(raised.value)) is None


async def test_provider_policy_refusal_preserves_the_provider_explanation(policy, trigger_owner, monkeypatch):
    from langflow.services.triggers.policy import (
        TriggerPolicyContext,
        TriggerPolicyError,
        TriggerPolicyPurpose,
        require_trigger_policy,
    )
    from lfx.services.integration_policy import IntegrationPolicyError, IntegrationPolicyPurpose

    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset({"google.calendar"})))
    refusal = IntegrationPolicyError("google", IntegrationPolicyPurpose.USE)
    monkeypatch.setattr("langflow.services.triggers.policy.aresolve_integration_policy", AsyncMock(side_effect=refusal))
    with pytest.raises(TriggerPolicyError, match="outside the approved integration set") as raised:
        await require_trigger_policy(
            TriggerPolicyContext(user_id=trigger_owner, kind="google.calendar", purpose=TriggerPolicyPurpose.ENABLE)
        )
    assert str(raised.value) == str(refusal)
    assert raised.value.code == "governance_blocked"


async def test_discovery_hides_unapproved_kinds_without_mutating_the_cached_palette(policy, trigger_owner):
    from langflow.services.integration_policy_discovery import filter_component_palette_by_integration_policy

    palette = {
        "triggers": {
            "Schedule": {"metadata": {"trigger_kind": "schedule"}},
            "Action": {"metadata": {}},
        }
    }
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset()))
    visible = await filter_component_palette_by_integration_policy(palette, user_id=trigger_owner)
    assert set(visible["triggers"]) == {"Action"}
    assert "Schedule" in palette["triggers"]


async def test_building_a_hidden_trigger_is_refused(policy, trigger_owner):
    from langflow.services.integration_policy_discovery import aenforce_integration_policy_for_component
    from lfx.services.integration_policy import IntegrationPolicyError

    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset()))
    with pytest.raises(IntegrationPolicyError):
        await aenforce_integration_policy_for_component(
            {"metadata": {"trigger_kind": "schedule"}}, user_id=trigger_owner
        )


async def test_templates_hide_blocked_core_triggers_without_an_integration_requirement(policy, trigger_owner):
    from langflow.services.integration_policy_discovery import ablocked_template_positions, template_integration_filter

    nodes = [{"data": {"node": {"metadata": {"trigger_kind": "schedule"}}}}]
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset()))
    assert template_integration_filter([("schedule", nodes), ("empty", [])]) == {0}
    assert await ablocked_template_positions([nodes, []], user_id=trigger_owner) == {0}


async def test_enterprise_hook_can_narrow_but_cannot_bypass_the_shared_ceiling(make_trigger, policy, monkeypatch):
    from langflow.services.triggers.policy import TriggerPolicyError

    identifier = await make_trigger(config={"cron": "0 * * * *", "timezone": "UTC"})
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset({"schedule"})))
    service = TriggerService()
    hook = AsyncMock(side_effect=TriggerPolicyError("Trigger quota requires operator approval."))
    monkeypatch.setattr(service, "authorize_trigger", hook)
    async with session_scope() as session:
        with pytest.raises(TriggerPolicyError, match="quota"):
            await service.enable(session, row=await session.get(Trigger, identifier))
    hook.assert_awaited_once()
    hook.reset_mock()
    policy.publish(PolicyBundleSnapshot(revision=3, approved_trigger_kinds=frozenset()))
    async with session_scope() as session:
        with pytest.raises(TriggerPolicyError, match="Blocked by trigger policy"):
            await service.enable(session, row=await session.get(Trigger, identifier))
    hook.assert_not_awaited()


async def test_policy_refresh_pauses_blocked_rows_and_keeps_approved_rows(make_trigger, policy):
    from langflow.services.triggers.policy import pause_disallowed_triggers

    allowed_id = await make_trigger(kind="schedule")
    denied_id = await make_trigger(kind="google.gmail", provider="google")
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset({"schedule"})))
    async with session_scope() as session:
        assert await pause_disallowed_triggers(session) == 1
    async with session_scope() as session:
        assert (await session.get(Trigger, allowed_id)).state == "active"
        denied = await session.get(Trigger, denied_id)
        assert denied.state == "paused"
        assert "Blocked by trigger policy" in denied.last_error
        assert await pause_disallowed_triggers(session) == 0


async def test_operator_resume_records_the_policy_denial(make_trigger, policy, trigger_owner):
    from langflow.services.database.models.auth.authz import AuthzAuditLog
    from langflow.services.database.models.trigger.schemas import TriggerBulkRequest
    from langflow.services.triggers import operator
    from sqlmodel import select

    identifier = await make_trigger(config={"cron": "0 * * * *", "timezone": "UTC"})
    async with session_scope() as session:
        await operator.bulk_pause(
            session, TriggerService(), request=TriggerBulkRequest(trigger_ids=[identifier]), actor_id=trigger_owner
        )
    policy.publish(PolicyBundleSnapshot(revision=2, approved_trigger_kinds=frozenset()))
    async with session_scope() as session:
        result = await operator.bulk_resume(
            session, TriggerService(), request=TriggerBulkRequest(trigger_ids=[identifier]), actor_id=trigger_owner
        )
    assert len(result.failed) == 1
    async with session_scope() as session:
        denial = (
            await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.action == "trigger:policy_denied"))
        ).one()
        assert denial.user_id == trigger_owner
        assert denial.result == "deny"
