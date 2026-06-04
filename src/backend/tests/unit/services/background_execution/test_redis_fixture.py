"""The real-redis fixture must connect to LANGFLOW_TEST_REDIS_URL or skip cleanly."""

from __future__ import annotations

import os

import pytest


@pytest.mark.asyncio
async def test_real_redis_fixture_roundtrips(real_redis):
    # If LANGFLOW_TEST_REDIS_URL is unset, the fixture skips before reaching here.
    prefix = real_redis._bgtest_prefix
    await real_redis.set(f"{prefix}probe", "1", ex=5)
    assert await real_redis.get(f"{prefix}probe") == b"1"


def test_real_redis_skips_without_env(real_redis_url):
    # real_redis_url returns None when env is unset; documents the skip contract.
    if real_redis_url is None:
        pytest.skip("LANGFLOW_TEST_REDIS_URL not set")
    assert real_redis_url.startswith("redis://") or os.environ.get("LANGFLOW_TEST_REDIS_URL")
