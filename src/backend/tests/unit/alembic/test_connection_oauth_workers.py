"""Use separate OS processes to prove refresh coordination is database-backed."""

from __future__ import annotations

import asyncio
import json
import multiprocessing
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet
from langflow.services.database.models.connection import Connection, ConnectionSecret
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.database.models.user.model import User
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlmodel import Session

from .test_migration_execution import _engine_url, db_url  # noqa: F401


def _registration():
    return {
        "provider": "google",
        "client_type": "public",
        "context": "desktop",
        "client_id": "test-client",
        "redirect_uri": "http://localhost/api/v1/connections/oauth/google/callback",
        "scopes": ["read"],
    }


def _worker(database_url, key, owner_id, barrier, exchanges_path, results):
    """Every process owns its engine, resolver and OAuth transport."""
    from langflow.services.connection import service
    from langflow.services.connection.oauth import broker, providers
    from langflow.services.connection.oauth.config import OAuthSettings
    from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
    from lfx.services.authorization.base import ExecutionPrincipal
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel.ext.asyncio.session import AsyncSession

    async def run():
        async_url = (
            database_url
            if database_url.startswith("sqlite")
            else database_url.replace("postgresql://", "postgresql+psycopg://")
        )
        engine = create_async_engine(async_url)

        @asynccontextmanager
        async def sessions():
            async with AsyncSession(engine, expire_on_commit=False) as session:
                try:
                    yield session
                    await session.commit()
                except BaseException:
                    await session.rollback()
                    raise

        service.session_scope = sessions
        cipher = Fernet(key)
        service.auth_utils.encrypt_api_key = lambda value: cipher.encrypt(value.encode()).decode()
        service.auth_utils.decrypt_api_key = lambda value: cipher.decrypt(value.encode()).decode()
        broker.get_oauth_settings = lambda: OAuthSettings(
            context="desktop", registrations=SecretStr(json.dumps({"work": _registration()}))
        )

        async def exchange(_url, data, **_kwargs):
            assert data["refresh_token"] == "original-refresh"  # noqa: S105 - test fixture
            with Path(exchanges_path).open("a") as stream:  # noqa: ASYNC230 - subprocess test counter
                stream.write("exchange\n")
            await asyncio.sleep(0.3)
            return {
                "access_token": "worker-refreshed",
                "refresh_token": "rotated-refresh",
                "expires_in": 3600,
                "scope": "read",
            }

        providers._request = exchange
        await asyncio.to_thread(barrier.wait, 20)
        try:
            result = await service.DatabaseConnectionResolverService().resolve(
                ConnectionResolutionRequest(
                    ref=ConnectionRef(provider="google", name="work"),
                    principal=ExecutionPrincipal(kind="actor", user_id=owner_id, actor_id=owner_id, interactive=True),
                )
            )
            results.put(result.access_token.get_secret_value())
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
    except BaseException as exc:
        results.put(type(exc).__name__)
        raise


def test_two_workers_exchange_exactly_once(db_url, tmp_path):  # noqa: F811
    from langflow.services.connection.oauth.config import OAuthRegistration

    engine = create_engine(_engine_url(db_url))
    # These real tables exercise foreign keys and visibility across connections.
    for model in (User, Connection, ConnectionSecret, ConnectionOAuth):
        model.__table__.create(engine, checkfirst=True)
    owner, connection_id, generation = uuid4(), uuid4(), uuid4()
    key = Fernet.generate_key()
    now = datetime.now(timezone.utc)
    config_digest = OAuthRegistration.model_validate(_registration()).fingerprint()
    with Session(engine) as session:
        session.add(User(id=owner, username="worker-owner", password=str(uuid4()), is_active=True))
        session.commit()
        session.add(
            Connection(
                id=connection_id,
                owner_id=owner,
                provider_key="google",
                name="work",
                display_name="Work",
                status="ready",
                granted_scopes=["read"],
                executing_identity={"identity": "user_delegated"},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        envelope = {
            "version": 1,
            "access_token": "expired",
            "refresh_token": "original-refresh",
            "expires_at": (now - timedelta(seconds=1)).isoformat(),
            "oauth": {"registration_id": "work", "config_digest": config_digest, "generation": str(generation)},
        }
        session.add(
            ConnectionSecret(
                connection_id=connection_id,
                encrypted_payload=Fernet(key).encrypt(json.dumps(envelope).encode()).decode(),
            )
        )
        session.add(
            ConnectionOAuth(
                connection_id=connection_id,
                user_id=owner,
                registration_id="work",
                generation=generation,
                config_digest=config_digest,
                expires_at=now,
                scopes=["read"],
            )
        )
        session.commit()
    engine.dispose()
    ctx = multiprocessing.get_context("spawn")
    barrier, results = ctx.Barrier(2), ctx.Queue()
    exchanges = tmp_path / "exchanges.txt"
    workers = [
        ctx.Process(target=_worker, args=(db_url, key, str(owner), barrier, str(exchanges), results)) for _ in range(2)
    ]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=45)
            assert worker.exitcode == 0
        assert [results.get(timeout=5) for _ in workers] == ["worker-refreshed", "worker-refreshed"]
        assert exchanges.read_text().splitlines() == ["exchange"]
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=5)
        results.close()
