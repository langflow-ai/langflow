"""Phase 0 harness tests: the hard_proof marker + real-instance fixtures.

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
def test_hard_proof_marker_is_registered(request: pytest.FixtureRequest) -> None:
    """The hard_proof marker must be registered so --strict-markers accepts it."""
    ini_markers = request.config.getini("markers")
    names = {line.split(":", 1)[0].strip() for line in ini_markers}
    assert "hard_proof" in names, f"hard_proof not registered; have: {sorted(names)}"


@pytest.mark.hard_proof
@pytest.mark.no_blockbuster
async def test_hard_proof_db_url_yields_real_engine(hard_proof_db_url: str) -> None:
    """hard_proof_db_url must produce a URL backing a real, queryable engine."""
    if "postgresql" in hard_proof_db_url:
        assert os.environ.get("LANGFLOW_TEST_DATABASE_URI"), "postgres param ran without URI set"
    engine = create_async_engine(hard_proof_db_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
    finally:
        await engine.dispose()


@pytest.mark.hard_proof
@pytest.mark.no_blockbuster
async def test_hard_proof_redis_url_pings_real_server(hard_proof_redis_url: str) -> None:
    """hard_proof_redis_url must back a reachable, real Redis server."""
    from redis.asyncio import StrictRedis

    assert os.environ.get("LANGFLOW_TEST_REDIS_URL"), "redis fixture ran without URL set"
    client = StrictRedis.from_url(hard_proof_redis_url)
    try:
        assert await client.ping() is True
        await client.set("hard_proof:probe", "1")
        assert await client.get("hard_proof:probe") == b"1"
    finally:
        await client.aclose()
