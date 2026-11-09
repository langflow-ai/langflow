"""A policy-blocked saved trigger returns an actionable refusal without starting work."""

from dataclasses import replace

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import session_scope
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service
from sqlmodel import select

from tests.unit.services.triggers import test_confluence_lifecycle, test_jira_lifecycle
from tests.unit.services.triggers.test_confluence_lifecycle import confluence  # noqa: F401
from tests.unit.services.triggers.test_jira_lifecycle import jira  # noqa: F401

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("provider", ["confluence", "jira"])
async def test_policy_blocked_resume_returns_safe_403_and_stays_paused(
    client, active_user, logged_in_headers, request, provider, fake_background_service
):
    """Exercise each installed provider's real arming policy through the owner API."""
    listener = request.getfixturevalue(provider)
    lifecycle = test_confluence_lifecycle if provider == "confluence" else test_jira_lifecycle
    await lifecycle.connection(active_user.id)
    async with session_scope() as session:
        flow = Flow(name=f"{provider} policy refusal", user_id=active_user.id)
        session.add(flow)
        await session.flush()
        flow_id = flow.id
    trigger = await lifecycle.reconcile(flow_id, active_user.id)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        row.state = "paused"
        session.add(row)
        flow = await session.get(Flow, flow_id)
        flow.data = {"nodes": [{"id": row.node_id}], "edges": []}
        session.add(flow)

    bundle = get_policy_bundle_service()
    original = bundle.snapshot
    action = f"integrations.{provider}.trigger.updated"
    bundle.publish(
        replace(
            original,
            revision=original.revision + 1,
            initialized=True,
            blocked_integration_action_keys=frozenset({action}),
        )
    )
    get_integration_policy_service().invalidate()
    try:
        response = await client.post(f"api/v1/triggers/{trigger.id}/enable", headers=logged_in_headers)

        assert response.status_code == 403, response.text
        assert response.json()["detail"] == {
            "error_code": "policy-blocked",
            "message": "This integration action is not available under the current integration policy.",
            "hint": "Ask an administrator to approve the integration or unblock the action.",
            "provider": provider,
        }
        assert "synthetic-" not in response.text
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            assert row.state == "paused"
            assert not (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == row.id))).all()
        assert not listener.calls
        assert not fake_background_service.submits
    finally:
        bundle.publish(replace(original, revision=bundle.snapshot.revision + 1))
        get_integration_policy_service().invalidate()

    resumed = await client.post(f"api/v1/triggers/{trigger.id}/enable", headers=logged_in_headers)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["state"] == "active"
    assert not fake_background_service.submits
