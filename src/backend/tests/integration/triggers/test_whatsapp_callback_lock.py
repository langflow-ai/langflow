"""Meta callback verification must finish while provisioning holds its claim."""

import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.database.models.trigger.model import TriggerSubscription
from langflow.services.triggers.ingress.verifiers import state_digest
from langflow.services.triggers.providers.whatsapp import lifecycle
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateTable
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.no_blockbuster


async def test_callback_reads_committed_reservation_during_provisioning(monkeypatch):
    url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not url or not url.startswith("postgresql+psycopg://"):
        pytest.skip("LANGFLOW_TEST_DATABASE_URI must point to a PostgreSQL test cluster")
    schema = "whatsapp_callback_" + uuid4().hex
    base = create_async_engine(url)
    engine = base.execution_options(schema_translate_map={None: schema})
    monkeypatch.setattr(
        lifecycle,
        "settings",
        lambda: SimpleNamespace(
            tenant="111:222",
            phone_id="333",
            waba_id="222",
            app_secret="synthetic-app-value",  # noqa: S106  # pragma: allowlist secret
        ),
    )
    monkeypatch.setattr(lifecycle, "decrypt_api_key", lambda _value: "synthetic-verification-value")
    trigger = SimpleNamespace(
        id=uuid4(),
        signing_secret_encrypted="synthetic-envelope",  # noqa: S106  # pragma: allowlist secret
        kind="whatsapp.event",
        config={},
    )
    try:
        async with base.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
        async with engine.begin() as connection:
            # Only the receiver table is needed to prove its actual lock behavior.
            await connection.run_sync(
                lambda sync: sync.execute(
                    CreateTable(TriggerSubscription.__table__, include_foreign_key_constraints=[]),
                )
            )
        async with AsyncSession(engine) as session:
            session.add(
                TriggerSubscription(
                    trigger_id=trigger.id,
                    connection_id=uuid4(),
                    provider="whatsapp",
                    provider_subscription_id="waba:111:222",
                    state="pending",
                    provider_state={"phone_id": "333"},
                )
            )
            await session.commit()
        async with AsyncSession(engine) as provisioning, AsyncSession(engine) as callback:
            assert await lifecycle.subscription(provisioning, trigger) is not None
            # A blocking callback deadlocks a synchronous verification POST.
            secrets = await asyncio.wait_for(lifecycle.ingress_secrets(callback, trigger), timeout=2)
            assert secrets.resource_id == "222"
            assert secrets.channel_id == "333"
            assert secrets.verification_token_digest == state_digest("synthetic-verification-value")
            assert provisioning.in_transaction()
    finally:
        async with base.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await base.dispose()
