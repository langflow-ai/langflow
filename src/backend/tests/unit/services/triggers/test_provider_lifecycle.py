"""A synthetic installed provider exercises shared ownership and delivery."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langflow.services.connection.service import DatabaseConnectionResolverService
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerEvent, TriggerSubscription
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, source_runtime
from langflow.services.triggers.ingress.verifiers import IngressRejected, Verified
from langflow.services.triggers.providers import registry
from langflow.services.triggers.reconciliation import reconcile_flow_triggers
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_cleanup import run_cleanup_pass
from langflow.services.triggers.source_clients import SourceHTTP
from langflow.services.triggers.subscriptions import upsert_subscription
from lfx.extension.bundle_registry import BundleRecord
from lfx.extension.loader._types import LoadedIntegration
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.integrations.errors import IntegrationPolicyBlockedError
from lfx.integrations.models import ConnectionRef
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def pilot(monkeypatch, client):  # noqa: ARG001
    from lfx.extension import bundle_registry

    manifest = IntegrationCapabilityManifest.model_validate(
        {
            "schema_version": 1,
            "provider_id": "pilot",
            "display_name": "Pilot",
            "auth_profiles": [
                {
                    "id": "pilot-token",
                    "kind": "api_key",
                    "identity": "service",
                    "client_type_by_context": {"self_managed": "external"},
                }
            ],
            "capabilities": [
                {
                    "id": "pilot.trigger.item",
                    "display_name": "Pilot On Item",
                    "auth_profile_id": "pilot-token",
                    "identity": "service",
                    "policy_keys": ["integrations.pilot.trigger.item"],
                    "substrate": "rest",
                    "maturity": "preview",
                    "deployment_contexts": ["self_managed"],
                    "risk": "read",
                    "component_ref": "PilotOnItemTriggerComponent",
                }
            ],
        }
    )
    owner = LoadedIntegration(
        extension_id="lfx-pilot",
        extension_version="0.1.0",
        bundle="pilot",
        provider_id="pilot",
        manifest_path=Path("pilot.json"),
        capability_manifest=manifest,
        distribution="lfx-pilot",
    )
    record = BundleRecord(
        bundle="pilot",
        extension_id="lfx-pilot",
        extension_version="0.1.0",
        slot="official",
        integrations=(owner,),
        components=(SimpleNamespace(class_name="PilotOnItemTriggerComponent"),),
    )
    monkeypatch.setattr(
        bundle_registry,
        "get_default_registry",
        lambda: SimpleNamespace(snapshot=lambda: {"pilot": record}, list_integrations=lambda: [owner]),
    )
    monkeypatch.setattr(registry, "_cache_key", None)
    monkeypatch.setattr(registry, "_providers", {})
    deleted = []
    provisions = []
    prepared = []

    def normalize(_kind, raw):
        if raw.get("repository") != "acme/widgets":
            msg = "Choose a supported repository."
            raise ValueError(msg)
        return {field: value for field, value in raw.items() if value is not None}

    async def validate(payload, *, context):  # noqa: ARG001
        return payload

    def verify(request, secrets, *, tolerance_s):  # noqa: ARG001
        signature = hmac.new(secrets.signing_secret.encode(), request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, request.header("x-pilot-signature") or ""):
            msg = "bad_signature"
            raise IngressRejected(msg)
        body = json.loads(request.body)
        if body.get("repository") != secrets.target_config["repository"]:
            msg = "bad_signature"
            raise IngressRejected(msg)
        return Verified(payload={"item_id": body["id"]}, dedupe_suffix=hashlib.sha256(request.body).hexdigest())

    def verify_get(request, secrets, *, tolerance_s):  # noqa: ARG001
        if not hmac.compare_digest(request.query.get("proof", ""), secrets.signing_secret):
            msg = "bad_signature"
            raise IngressRejected(msg)
        return Verified(handshake=request.query.get("challenge", ""))

    async def provision(session, trigger):
        provisions.append(trigger.id)
        return await upsert_subscription(
            session,
            trigger_id=trigger.id,
            connection_id=trigger.connection_id,
            provider="pilot",
            provider_subscription_id=f"pilot:{trigger.id}",
            client_state_digest=None,
            expires_at=None,
            provider_state={"repository": trigger.config["repository"]},
        )

    async def prepare(session, trigger):
        prepared.append(trigger.id)
        await upsert_subscription(
            session,
            trigger_id=trigger.id,
            connection_id=trigger.connection_id,
            provider="pilot",
            provider_subscription_id=f"pilot:{trigger.id}",
            client_state_digest=None,
            expires_at=None,
            provider_state={"repository": trigger.config["repository"]},
        )

    async def revoke(task, lease):
        assert lease.ref.provider == "pilot"
        deleted.append(task.provider_subscription_id)

    provider = registry.TriggerProvider(
        provider_id="pilot",
        bundle="pilot",
        normalize_config=normalize,
        kinds=(
            registry.TriggerKind(
                kind="pilot.item",
                component="PilotOnItemTriggerComponent",
                display_name="Pilot On Item",
                config_fields=("connection", "repository", "delivery_mode"),
                push_mechanism="pilot.webhook",
                identity="service",
            ),
        ),
        verify=verify,
        verify_get=verify_get,
        provision=provision,
        revoke=revoke,
        validate_manual_credential=validate,
        api_origins=("https://api.pilot.example",),
        prepare=prepare,
    )
    original_entry_points = registry.metadata.entry_points
    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda **kwargs: [
            SimpleNamespace(name="pilot", dist=SimpleNamespace(metadata={"Name": "lfx-pilot"}), load=lambda: provider)
        ]
        if kwargs.get("group") == registry.ENTRY_POINT_GROUP
        else original_entry_points(**kwargs),
    )
    monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_CONTEXT", "self_managed")
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "trigger_ingress_origin", "https://langflow.example")
    return SimpleNamespace(provider=provider, deleted=deleted, provisions=provisions, prepared=prepared)


async def _connection(owner_id, *, name="work", allow=True, identity="service"):
    async with session_scope() as session:
        owner = await session.get(User, owner_id)
        return await DatabaseConnectionResolverService().create(
            session,
            user=owner,
            payload=ConnectionCreate(
                provider_key="pilot",
                name=name,
                display_name="Pilot work",
                executing_identity={"identity": identity},
                allow_non_interactive=allow,
                credentials={"access_token": "synthetic-pilot-credential"},
            ),
        )


async def _reconcile(flow_id, owner_id):
    data = {
        "nodes": [
            {
                "id": "pilot-source",
                "data": {
                    "type": "ext:pilot:PilotOnItemTriggerComponent@official",
                    "node": {
                        "template": {
                            name: {"value": value}
                            for name, value in {
                                "connection": "pilot/work",
                                "repository": "acme/widgets",
                                "delivery_mode": "push",
                            }.items()
                        }
                    },
                },
            }
        ],
        "edges": [],
    }
    async with session_scope() as session:
        await reconcile_flow_triggers(session, flow_id=flow_id, owner_id=owner_id, flow_data=data)
    async with session_scope() as session:
        return (await session.exec(select(Trigger).where(Trigger.flow_id == flow_id))).one()


async def test_save_enable_signed_delivery_dispatch_and_cleanup(
    pilot,
    trigger_owner,
    owned_flow,
    client,
    fake_background_service,
):
    from langflow.services.auth.utils import decrypt_api_key

    await _connection(trigger_owner)
    trigger = await _reconcile(owned_flow, trigger_owner)
    assert trigger.state == "pending"
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        assert row.signing_secret_encrypted
        secret = decrypt_api_key(row.signing_secret_encrypted)
        public_id = row.public_id
    assert pilot.provisions == [trigger.id]
    assert pilot.prepared == [trigger.id]
    assert await source_runtime.sync_source(trigger.id) == 0
    assert await dispatcher.reconcile_push_sources() == 0
    assert pilot.provisions == [trigger.id]

    body = json.dumps({"repository": "acme/widgets", "id": "item-7"}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    url = f"/api/v1/triggers/ingress/pilot/{public_id}"
    for _ in range(2):
        response = await client.post(url, content=body, headers={"x-pilot-signature": signature})
        assert response.status_code == 202, response.text
    assert (await client.post(url, content=body, headers={"x-pilot-signature": "wrong"})).status_code == 404
    async with session_scope() as session:
        events = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger.id))).all()
        assert len(events) == 1
        assert events[0].payload == {"provider": "pilot", "delivery": {"item_id": "item-7"}}
    assert await dispatcher.run_once(owner="pilot-dispatch-test") == 1
    assert len(fake_background_service.submits) == 1

    challenge = await client.get(url, params={"proof": secret, "challenge": "verified-challenge"})
    assert challenge.status_code == 200
    assert challenge.text == "verified-challenge"
    assert (await client.get(url, params={"proof": "wrong", "challenge": "bad"})).status_code == 404
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().disable(session, row=row)
        subscription = (
            await session.exec(select(TriggerSubscription).where(TriggerSubscription.trigger_id == trigger.id))
        ).one()
        assert subscription.state == "expired"
        assert subscription.expires_at is None
        assert subscription.renew_after is None
        assert len((await session.exec(select(TriggerCleanup))).all()) == 1
    assert await run_cleanup_pass() == 1
    assert pilot.deleted == [f"pilot:{trigger.id}"]
    assert (await client.post(url, content=body, headers={"x-pilot-signature": signature})).status_code == 404


async def test_direct_webhook_with_poll_fallback_never_collects_on_push(
    pilot,
    trigger_owner,
    owned_flow,
    monkeypatch,
):
    from langflow.services.triggers.source_poll import collect_source

    async def collect(_trigger, _lease):
        pytest.fail("A direct webhook called the polling API")

    provider = replace(
        pilot.provider, collect=collect, kinds=(replace(pilot.provider.kinds[0], poll_mechanism="pilot.poll"),)
    )
    monkeypatch.setattr(registry, "all_providers", lambda: (provider,))
    await _connection(trigger_owner)
    trigger = await _reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
    assert await source_runtime.sync_source(trigger.id) == 0
    assert await dispatcher.reconcile_push_sources() == 0
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        with pytest.raises(ValueError, match="cannot enter source polling"):
            await collect_source(row, None)


async def test_polling_prepare_claim_is_cleaned_up_on_pause(pilot, trigger_owner, owned_flow, monkeypatch):
    async def collect(_trigger, _lease):
        pytest.fail("Enabling a polling source should not collect inside its write transaction")

    provider = replace(
        pilot.provider, collect=collect, kinds=(replace(pilot.provider.kinds[0], poll_mechanism="pilot.poll"),)
    )
    monkeypatch.setattr(registry, "all_providers", lambda: (provider,))
    await _connection(trigger_owner)
    trigger = await _reconcile(owned_flow, trigger_owner)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        row.config = {**row.config, "delivery_mode": "poll"}
        session.add(row)
        await session.flush()
        await TriggerService().enable_and_activate(session, row=row)
        assert row.state == "active"
        assert row.config["mechanism_id"] == "pilot.poll"
        await TriggerService().disable(session, row=row)
    assert pilot.prepared == [trigger.id]
    assert pilot.provisions == []
    assert await run_cleanup_pass() == 1
    assert pilot.deleted == [f"pilot:{trigger.id}"]


@pytest.mark.parametrize("failure", ["foreign-owner", "consent", "identity", "policy"])
async def test_activation_enforces_owner_consent_identity_and_policy(pilot, trigger_owner, owned_flow, failure):
    owner_id = trigger_owner
    if failure == "foreign-owner":
        async with session_scope() as session:
            other = User(username=f"pilot-other-{uuid4().hex}", password="not-a-login", is_active=True)  # noqa: S106
            session.add(other)
            await session.flush()
            owner_id = other.id
    await _connection(owner_id, allow=failure != "consent", identity="bot" if failure == "identity" else "service")
    trigger = await _reconcile(owned_flow, trigger_owner)
    bundle = get_policy_bundle_service()
    original = bundle.snapshot
    if failure == "policy":
        bundle.publish(
            replace(
                original,
                revision=original.revision + 1,
                initialized=True,
                blocked_integration_action_keys=frozenset({"integrations.pilot.trigger.item"}),
            )
        )
        get_integration_policy_service().invalidate()
    try:
        async with session_scope() as session:
            row = await session.get(Trigger, trigger.id)
            with pytest.raises((ValueError, IntegrationPolicyBlockedError)):
                await TriggerService().enable_and_activate(session, row=row)
        assert pilot.provisions == []
    finally:
        bundle.publish(replace(original, revision=bundle.snapshot.revision + 1))
        get_integration_policy_service().invalidate()


@pytest.mark.usefixtures("pilot")
async def test_source_http_rejects_foreign_origin_before_credential_resolution():
    class Lease:
        ref = ConnectionRef(provider="pilot", name="work")

        async def get_token(self):
            pytest.fail("A forbidden destination resolved credentials")

    with pytest.raises(ValueError, match="not allowed"):
        SourceHTTP(Lease(), origin="https://attacker.example")
    async with SourceHTTP(
        Lease(),
        origin="https://api.pilot.example",
        transport=httpx.MockTransport(lambda _request: pytest.fail("A forbidden continuation reached HTTP")),
    ) as source:
        with pytest.raises(ValueError, match="left its API origin"):
            await source.request("GET", "https://attacker.example/private")
