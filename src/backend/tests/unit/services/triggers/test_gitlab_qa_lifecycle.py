"""GitLab filter saves, expected refusals, and owner-visible cleanup failures."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from langflow.api.v1.triggers import enable_trigger
from langflow.api.v1.triggers_helpers import present_one
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_cleanup import run_cleanup_pass
from langflow.services.triggers.source_runtime import source_failure_detail
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service
from sqlmodel import select

from tests.unit.services.triggers.test_gitlab_lifecycle import connection, gitlab, reconcile  # noqa: F401

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize(
    ("field", "value"),
    [("actions", ["close"]), ("include_self_events", True), ("include_bot_events", True)],
)
async def test_filter_save_keeps_active_subscription(gitlab, trigger_owner, owned_flow, field, value):  # noqa: F811
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        public_id = row.public_id
        subscription = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == row.id))
        ).one()
        subscription_id = subscription.id
        provider_state = dict(row.provider_state)
    async with session_scope() as session:
        flow = await session.get(Flow, owned_flow)
        data = {**flow.data, "nodes": [dict(flow.data["nodes"][0])]}
        node = data["nodes"][0]
        node["data"] = {**node["data"], "node": {**node["data"]["node"]}}
        node["data"]["node"]["template"] = {**node["data"]["node"]["template"], field: {"value": value}}
        flow.data = data
        session.add(flow)
        await reconcile_flow_triggers(session, flow_id=owned_flow, owner_id=trigger_owner, flow_data=data)
        row = await session.get(Trigger, trigger.id)
        assert row.state == "active"
        assert row.config[field] == value
        assert row.public_id == public_id
        assert row.provider_state == provider_state
        assert await session.get(TriggerSubscription, subscription_id) is not None
        assert not (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == row.id))).all()
    assert await run_cleanup_pass() == 0
    assert gitlab.created == 1
    assert gitlab.deleted == []


async def test_policy_denial_is_a_client_refusal(gitlab, trigger_owner, owned_flow):  # noqa: F811
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    policy = get_policy_bundle_service()
    before = policy.snapshot
    policy.publish(
        replace(
            before,
            revision=before.revision + 1,
            initialized=True,
            blocked_integration_action_keys=frozenset({"integrations.gitlab.trigger.issue"}),
        )
    )
    get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            user = await session.get(User, trigger_owner)
            with pytest.raises(HTTPException) as refusal:
                await enable_trigger(trigger.id, session, user, TriggerService())
            assert refusal.value.status_code == 403
            assert refusal.value.detail["code"] == "policy-blocked"
            assert "integration policy" in refusal.value.detail["message"]
        assert gitlab.created == 0
    finally:
        policy.publish(replace(before, revision=policy.snapshot.revision + 1))
        get_integration_policy_service().invalidate()


async def test_cleanup_and_activation_show_safe_ownership_guidance(gitlab, trigger_owner, owned_flow):  # noqa: F811
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        callback = gitlab.hooks[1]["url"]
        manual_hook = {**gitlab.hooks[1], "description": "foreign-marker"}
        gitlab.hooks[1]["url"] = "https://other.example/callback"
        await TriggerService().disable(session, row=row)
    assert await run_cleanup_pass() == 0
    async with session_scope() as session:
        cleanup = (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).one()
        expected = "The GitLab callback ownership changed and requires administrator cleanup"
        assert cleanup.last_error == expected
        user = await session.get(User, trigger_owner)
        row = await session.get(Trigger, trigger.id)
        shown = await present_one(session, user, row)
        assert expected in shown.last_error
        assert "https://other.example" not in shown.last_error
        cleanup.available_at = datetime.now(timezone.utc)
        session.add(cleanup)
    gitlab.hooks[1]["url"] = callback
    assert await run_cleanup_pass() == 1
    async with session_scope() as session:
        user = await session.get(User, trigger_owner)
        row = await session.get(Trigger, trigger.id)
        assert (await present_one(session, user, row)).last_error is None
    gitlab.hooks[1] = manual_hook
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="ownership proof"):
            await TriggerService().enable_and_activate(session, row=row)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        assert "ownership proof" in row.last_error
        assert "ValueError" not in row.last_error
    assert gitlab.deleted == [1]


def test_untrusted_errors_do_not_expose_provider_details():
    assert source_failure_detail(ValueError("provider response with a secret")) == "ValueError"
