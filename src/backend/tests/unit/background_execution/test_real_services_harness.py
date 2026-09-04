"""Phase 0 harness tests: the real_services marker + real-instance fixtures.

These prove the harness itself works before any background-execution code exists:
the marker is registered, the DB fixture backs a real engine on sqlite and
postgres, and the redis fixture pings a real server.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.no_blockbuster
def test_real_services_marker_is_registered(request: pytest.FixtureRequest) -> None:
    """The real_services marker must be registered so --strict-markers accepts it."""
    ini_markers = request.config.getini("markers")
    names = {line.split(":", 1)[0].strip() for line in ini_markers}
    assert "real_services" in names, f"real_services not registered; have: {sorted(names)}"


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_real_services_db_url_yields_real_engine(real_services_db_url: str) -> None:
    """real_services_db_url must produce a URL backing a real, queryable engine."""
    if "postgresql" in real_services_db_url:
        assert os.environ.get("LANGFLOW_TEST_DATABASE_URI"), "postgres param ran without URI set"
    engine = create_async_engine(real_services_db_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
    finally:
        await engine.dispose()


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_real_services_redis_url_pings_real_server(real_services_redis_url: str) -> None:
    """real_services_redis_url must back a reachable, real Redis server."""
    from redis.asyncio import StrictRedis

    assert os.environ.get("LANGFLOW_TEST_REDIS_URL"), "redis fixture ran without URL set"
    client = StrictRedis.from_url(real_services_redis_url)
    try:
        assert await client.ping() is True
        await client.set("real_services:probe", "1")
        assert await client.get("real_services:probe") == b"1"
    finally:
        await client.aclose()
