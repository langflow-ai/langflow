"""Real database reservation and HTTP provisioning and cleanup contracts."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.connection.schemas import ConnectionCreate
from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
from langflow.services.triggers.providers.whatsapp import lifecycle
from langflow.services.triggers.providers.whatsapp.credentials import validate_manual_credential
from langflow.services.triggers.source_errors import SourceConfigurationError
from lfx.integrations.errors import ConnectionNotAuthorizedError
from lfx.integrations.models import ConnectionAccount, ResolvedCredential
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .support import DEBUG, PHONES, GraphTransport, lease, operator
from .test_events import CONFIG

__all__ = ["operator"]
pytestmark = pytest.mark.no_blockbuster
APPS = {"data": [{"whatsapp_business_api_data": {"id": "111"}}]}


@pytest.fixture
async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: SQLModel.metadata.create_all(
                sync,
                tables=[
                    Connection.__table__,
                    Trigger.__table__,
                    TriggerSubscription.__table__,
                    TriggerCleanup.__table__,
                ],
            )
        )
    yield engine
    await engine.dispose()


async def saved_trigger(session):
    owner = uuid4()
    connection = Connection(
        owner_id=owner,
        ownership_mode="user",
        provider_key="whatsapp",
        name="business",
        display_name="Business",
        status="ready",
        executing_identity={"identity": "service", "account": {"id": "333", "tenant_id": "111:222"}},
    )
    session.add(connection)
    await session.flush()
    trigger = Trigger(
        flow_id=uuid4(),
        user_id=owner,
        name="WhatsApp",
        kind="whatsapp.event",
        provider="whatsapp",
        config={**CONFIG, "mechanism_id": "whatsapp.webhook"},
        connection_id=connection.id,
        public_id=uuid4().hex,
        signing_secret_encrypted="synthetic-envelope",  # noqa: S106  # pragma: allowlist secret
        state="active",
    )
    session.add(trigger)
    await session.flush()
    return trigger


@pytest.fixture
def callbacks(monkeypatch):
    async def address(_session, trigger):
        return f"https://receiver.example/api/v1/triggers/ingress/whatsapp/{trigger.public_id}"

    async def source_lease(*_args, **_kwargs):
        return lease()

    monkeypatch.setattr(lifecycle, "source_ingress_url", address)
    monkeypatch.setattr(lifecycle, "source_lease", source_lease)
    monkeypatch.setattr(lifecycle, "decrypt_api_key", lambda _value: "synthetic-challenge-token")


@pytest.mark.usefixtures("callbacks")
async def test_prepare_is_db_only_and_claim_is_unique_across_connections(database, monkeypatch):
    transport = GraphTransport([]).install(monkeypatch)
    async with AsyncSession(database, expire_on_commit=False) as session:
        first = await saved_trigger(session)
        second = await saved_trigger(session)
        await lifecycle.prepare(session, first)
        await session.commit()
        await lifecycle.prepare(session, first)
        with pytest.raises(SourceConfigurationError, match="already has a receiver"):
            await lifecycle.prepare(session, second)
        assert len((await session.exec(select(TriggerSubscription))).all()) == 1
    assert not transport.requests


@pytest.mark.usefixtures("callbacks")
async def test_pending_cleanup_blocks_same_trigger_reenable_and_replacement(database):
    async with AsyncSession(database, expire_on_commit=False) as session:
        trigger = await saved_trigger(session)
        await lifecycle.prepare(session, trigger)
        row = await lifecycle.subscription(session, trigger)
        row.state = "expired"
        session.add(row)
        task = TriggerCleanup(
            id=uuid4(),
            trigger_id=trigger.id,
            user_id=trigger.user_id,
            provider="whatsapp",
            kind="whatsapp.event",
            provider_subscription_id=row.provider_subscription_id,
            provider_state=dict(row.provider_state),
        )
        session.add(task)
        await session.flush()
        with pytest.raises(SourceConfigurationError, match="cleanup is pending"):
            await lifecycle.prepare(session, trigger)
        other = await saved_trigger(session)
        with pytest.raises(SourceConfigurationError, match="cleanup is pending"):
            await lifecycle.prepare(session, other)
        await session.delete(task)
        await session.flush()
        await lifecycle.prepare(session, trigger)
        assert (await lifecycle.subscription(session, trigger)).state == "pending"


@pytest.mark.usefixtures("callbacks")
@pytest.mark.parametrize("existing", [None, "self", "foreign"])
async def test_provision_retries_own_uncertain_create_without_overwriting_another_callback(
    database, monkeypatch, existing
):
    async with AsyncSession(database, expire_on_commit=False) as session:
        trigger = await saved_trigger(session)
        await lifecycle.prepare(session, trigger)
        row = await lifecycle.subscription(session, trigger)
        apps = {
            "data": [
                {
                    "whatsapp_business_api_data": {"id": "111"},
                    "override_callback_uri": row.provider_state["callback_url"]
                    if existing == "self"
                    else "https://other.example/hook"
                    if existing == "foreign"
                    else None,
                }
            ]
        }
        transport = GraphTransport([DEBUG, PHONES, apps, {"success": True}]).install(monkeypatch)
        if existing == "foreign":
            with pytest.raises(SourceConfigurationError, match="left unchanged"):
                await lifecycle.provision(session, trigger)
            assert len(transport.requests) == 3
        else:
            result = await lifecycle.provision(session, trigger)
            assert result.state == "active"
            assert result.expires_at is None
            assert result.renew_after is None
            import json

            assert json.loads(transport.requests[-1].content) == {
                "override_callback_uri": row.provider_state["callback_url"],
                "verify_token": "synthetic-challenge-token",
            }
            proof = await lifecycle.ingress_secrets(session, trigger)
            assert proof.resource_id == "222"
            assert proof.channel_id == "333"
            assert proof.target_config == trigger.config


@pytest.mark.usefixtures("callbacks")
@pytest.mark.parametrize("current", ["self", "foreign", None])
async def test_cleanup_removes_only_exact_owned_override_without_unsubscribing(database, monkeypatch, current):
    async with AsyncSession(database, expire_on_commit=False) as session:
        trigger = await saved_trigger(session)
        await lifecycle.prepare(session, trigger)
        row = await lifecycle.subscription(session, trigger)
        task = TriggerCleanup(
            id=uuid4(),
            trigger_id=trigger.id,
            user_id=trigger.user_id,
            provider="whatsapp",
            kind="whatsapp.event",
            provider_subscription_id=row.provider_subscription_id,
            provider_state=row.provider_state,
        )
        apps = {
            "data": [
                {
                    "whatsapp_business_api_data": {"id": "111"},
                    "override_callback_uri": row.provider_state["callback_url"]
                    if current == "self"
                    else "https://other.example"
                    if current == "foreign"
                    else None,
                }
            ]
        }
        transport = GraphTransport([DEBUG, PHONES, apps, {"success": True}]).install(monkeypatch)
        await lifecycle.revoke(task, lease())
        assert not any(request.method == "DELETE" for request in transport.requests)
        assert len(transport.requests) == (4 if current == "self" else 3)
        if current == "self":
            assert transport.requests[-1].content == b"{}"


def connection_payload(**overrides):
    values = {
        "provider_key": "whatsapp",
        "name": "business",
        "display_name": "Business",
        "executing_identity": {"identity": "service", "account": {"id": "forged"}},
        "granted_scopes": ["forged"],
        "credentials": {"access_token": "synthetic-system-user-token"},
        **overrides,
    }
    return ConnectionCreate.model_validate(values)


async def test_manual_validation_replaces_untrusted_account_scopes_and_expiry(monkeypatch):
    GraphTransport([DEBUG, PHONES]).install(monkeypatch)
    result = await validate_manual_credential(connection_payload(), context="self_managed")
    assert result.executing_identity.account.id == "333"
    assert result.executing_identity.account.tenant_id == "111:222"
    assert result.granted_scopes == ["whatsapp_business_management", "whatsapp_business_messaging"]
    assert result.credentials.expires_at is None


@pytest.mark.parametrize("context", ["desktop", "headless"])
async def test_manual_validation_rejects_unsupported_context(context):
    with pytest.raises(ValueError, match="system-user"):
        await validate_manual_credential(connection_payload(), context=context)


async def test_retained_adapter_delegates_each_read_without_caching_or_extending_authority():
    deadline = datetime.now(timezone.utc) + timedelta(minutes=20)

    class OriginalLease:
        calls = 0

        async def get_credential(self):
            self.calls += 1
            return ResolvedCredential(
                access_token=SecretStr(f"synthetic-{self.calls}"),
                provider="whatsapp",
                expires_at=deadline,
                connection_id="original-deleted-connection",
                owner_kind="user",
            )

    original = OriginalLease()
    account = ConnectionAccount(id="333", tenant_id="111:222")
    wrapped = lifecycle._RetainedCleanupLease(original, account)
    for expected in range(1, 5):
        credential = await wrapped.get_credential()
        assert original.calls == expected
        assert credential.access_token.get_secret_value() == f"synthetic-{expected}"
        assert credential.expires_at == deadline
        assert credential.connection_id == "original-deleted-connection"
        assert credential.owner_kind == "user"
        assert credential.identity == "service"
        assert credential.account == account


async def test_retained_adapter_rejects_a_foreign_provider_credential():
    class OriginalLease:
        async def get_credential(self):
            return ResolvedCredential(access_token=SecretStr("synthetic"), provider="github")

    wrapped = lifecycle._RetainedCleanupLease(OriginalLease(), ConnectionAccount(id="333", tenant_id="111:222"))
    with pytest.raises(ConnectionNotAuthorizedError):
        await wrapped.get_credential()
