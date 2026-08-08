"""Shared fixtures for background-execution scaled-backend tests.

Lease/watchdog/Streams/pub-sub timing depends on Redis blocking-pop and
pub/sub delivery, which fakeredis does not faithfully reproduce. These tests
use a REAL Redis pointed at by LANGFLOW_TEST_REDIS_URL (mirroring the existing
LANGFLOW_TEST_DATABASE_URI convention). When the env var is unset the tests
skip rather than fail, so CI without a Redis service stays green.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio


@pytest.fixture
def real_redis_url() -> str | None:
    """Return LANGFLOW_TEST_REDIS_URL or None when unset."""
    return os.environ.get("LANGFLOW_TEST_REDIS_URL")


@pytest_asyncio.fixture
async def real_redis(real_redis_url):
    """A real StrictRedis client on a unique key-prefix namespace.

    Skips the test when LANGFLOW_TEST_REDIS_URL is unset. Flushes only the
    keys created under the per-test prefix on teardown to avoid clobbering a
    shared Redis used for other suites.
    """
    if real_redis_url is None:
        pytest.skip("LANGFLOW_TEST_REDIS_URL not set; skipping real-redis test")

    from redis.asyncio import StrictRedis

    client = StrictRedis.from_url(real_redis_url)
    try:
        await client.ping()
    except Exception as exc:
        pytest.skip(f"LANGFLOW_TEST_REDIS_URL unreachable: {exc}")

    prefix = f"bgtest:{uuid.uuid4().hex}:"
    client._bgtest_prefix = prefix  # type: ignore[attr-defined]
    try:
        yield client
    finally:
        # Delete only keys this test created under its prefix.
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor, match=f"{prefix}*", count=500)
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break
        await client.aclose()
