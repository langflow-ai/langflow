"""Installed owner discovery and actual ingress ledger, dispatch and cleanup."""

import hashlib
import hmac
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import lfx_whatsapp
import pytest
from langflow.services.connection.service import DatabaseConnectionResolverService
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerEvent
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.triggers import dispatcher, source_runtime
from langflow.services.triggers.providers import registry
from langflow.services.triggers.providers.whatsapp.provider import PROVIDER
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_cleanup import run_cleanup_pass
from lfx.extension import bundle_registry, load_extension
from lfx.extension.bundle_registry import BundleRecord
from lfx.integrations.errors import ConnectionNotAuthorizedError, IntegrationPolicyBlockedError
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service
from sqlmodel import select

from .support import DEBUG, PHONES, operator
from .test_events import CONFIG, SECRET, STATUS, payload

__all__ = ["operator"]
pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def installed(monkeypatch, client):  # noqa: ARG001
    loaded = load_extension(Path(lfx_whatsapp.__file__).parent, distribution="lfx-whatsapp")
    assert loaded.ok, loaded.errors
    owner = loaded.integrations[0]
    record = BundleRecord(
        bundle="whatsapp",
        extension_id="lfx-whatsapp",
        extension_version=owner.extension_version,
        slot="official",
        integrations=(owner,),
        components=tuple(
            SimpleNamespace(class_name=cap.component_ref) for cap in owner.capability_manifest.capabilities
        ),
    )
    monkeypatch.setattr(
        bundle_registry,
        "get_default_registry",
        lambda: SimpleNamespace(snapshot=lambda: {"whatsapp": record}, list_integrations=lambda: [owner]),
    )
    original = registry.metadata.entry_points
    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda **kwargs: [
            SimpleNamespace(
                name="whatsapp", dist=SimpleNamespace(metadata={"Name": "lfx-whatsapp"}), load=lambda: PROVIDER
            )
        ]
        if kwargs.get("group") == registry.ENTRY_POINT_GROUP
        else original(**kwargs),
    )
    monkeypatch.setattr(registry, "_cache_key", None)
    monkeypatch.setattr(registry, "_cache_records", ())
    monkeypatch.setattr(registry, "_providers", {})
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_origin", "https://langflow.example")
    state = {"callback": None, "requests": []}

    def graph(request):
        state["requests"].append(request)
        if request.url.path.endswith("debug_token"):
            return httpx.Response(200, json=DEBUG)
        if request.url.path.endswith("phone_numbers"):
            return httpx.Response(200, json=PHONES)
        if request.url.path.endswith("subscribed_apps"):
            if request.method == "POST":
                state["callback"] = json.loads(request.content).get("override_callback_uri")
                return httpx.Response(200, json={"success": True})
            return httpx.Response(
                200,
                json={
                    "data": [{"whatsapp_business_api_data": {"id": "111"}, "override_callback_uri": state["callback"]}]
                },
            )
        pytest.fail("Unexpected provider request")

    monkeypatch.setattr("lfx_whatsapp._client.httpx.AsyncHTTPTransport", lambda **_kwargs: httpx.MockTransport(graph))
    return state


async def connection(owner_id, *, allow=True):
    async with session_scope() as session:
        owner = await session.get(User, owner_id)
        return await DatabaseConnectionResolverService().create(
            session,
            user=owner,
            payload=ConnectionCreate(
                provider_key="whatsapp",
                name="business",
                display_name="Business",
                executing_identity={"identity": "service"},
                allow_non_interactive=allow,
                credentials={"access_token": "synthetic-system-user-token"},
            ),
        )


async def reconcile(flow_id, owner_id):
    fields = {**CONFIG, "delivery_mode": "push"}
    data = {
        "nodes": [
            {
                "id": "whatsapp-source",
                "data": {
                    "type": "ext:whatsapp:WhatsAppOnEventTriggerComponent@official",
                    "node": {"template": {name: {"value": value} for name, value in fields.items()}},
                },
            }
        ],
        "edges": [],
    }
    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=owner_id, flow_data=data)
    async with session_scope() as session:
        return (await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).one()


async def test_real_owner_discovery_enable_batch_intake_dedupe_dispatch_and_cleanup(
    installed, trigger_owner, owned_flow, client, fake_background_service
):
    from langflow.services.auth.utils import decrypt_api_key

    assert registry.get_provider("whatsapp") is PROVIDER
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        public_id = row.public_id
        proof = decrypt_api_key(row.signing_secret_encrypted)
    assert installed["callback"].endswith(public_id)
    assert await source_runtime.sync_source(trigger.id) == 0
    assert await dispatcher.reconcile_push_sources() == 0
    url = f"/api/v1/triggers/ingress/whatsapp/{public_id}"
    handshake = await client.get(
        url, params={"hub.mode": "subscribe", "hub.verify_token": proof, "hub.challenge": "1234"}
    )
    assert handshake.status_code == 200
    assert handshake.text == "1234"
    body = json.dumps(payload(statuses=[STATUS])).encode()
    headers = {"X-Hub-Signature-256": "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()}
    for _ in range(2):
        response = await client.post(url, content=body, headers=headers)
        assert response.status_code == 200, response.text
    assert (await client.post(url, content=body, headers={"X-Hub-Signature-256": "forged"})).status_code == 404
    # Another signed envelope containing the same item must dedupe across batches.
    second = json.dumps(payload(messages=[], statuses=[STATUS])).encode()
    signed = "sha256=" + hmac.new(SECRET.encode(), second, hashlib.sha256).hexdigest()
    assert (await client.post(url, content=second, headers={"X-Hub-Signature-256": signed})).status_code == 200
    async with session_scope() as session:
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).all()
        assert len(events) == 2
    assert await dispatcher.run_once(owner="whatsapp-contract") == 1
    assert len(fake_background_service.submits) == 1
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
        assert (await session.exec(select(TriggerCleanup).where(TriggerCleanup.trigger_id == trigger.id))).one()
    assert await run_cleanup_pass() == 1
    assert installed["callback"] is None
    assert not any(request.method == "DELETE" for request in installed["requests"])
    assert (await client.post(url, content=body, headers=headers)).status_code == 404


async def test_noninteractive_consent_is_required_before_callback_creation(installed, trigger_owner, owned_flow):
    await connection(trigger_owner, allow=False)
    trigger = await reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises((ValueError, ConnectionNotAuthorizedError), match=r".+"):
            await TriggerService().enable_and_activate(session, row=row)
    assert installed["callback"] is None


@pytest.mark.parametrize("failure", ["foreign-owner", "policy"])
async def test_owner_and_policy_denials_precede_callback_writes(installed, trigger_owner, owned_flow, failure):
    owner_id = trigger_owner
    if failure == "foreign-owner":
        async with session_scope() as session:
            other = User(username=f"whatsapp-other-{uuid4().hex}", password="not-a-login", is_active=True)  # noqa: S106
            session.add(other)
            await session.flush()
            owner_id = other.id
    await connection(owner_id)
    trigger = await reconcile(owned_flow, trigger_owner)
    bundle = get_policy_bundle_service()
    original = bundle.snapshot
    if failure == "policy":
        bundle.publish(
            replace(
                original,
                revision=original.revision + 1,
                initialized=True,
                blocked_integration_action_keys=frozenset({"integrations.whatsapp.trigger.event.webhook"}),
            )
        )
        get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            with pytest.raises((ValueError, IntegrationPolicyBlockedError), match=r".+"):
                await TriggerService().enable_and_activate(session, row=row)
        assert installed["callback"] is None
    finally:
        bundle.publish(replace(original, revision=bundle.snapshot.revision + 1))
        get_integration_policy_service().invalidate()
