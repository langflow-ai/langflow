# src/backend/tests/perf/check_key_benchmark.py
import asyncio
import hashlib
import logging
import os
import statistics
import time
import uuid

import pytest
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.api_key import crud as api_key_crud
from langflow.services.deps import get_settings_service

logger = logging.getLogger(__name__)


class DummyResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class MockSession:
    def __init__(self, rows: list[tuple]):
        self._rows = rows

    async def exec(self, _query):
        await asyncio.sleep(0)  # yield control
        return DummyResult(self._rows)

    async def get(self, _user, id_):
        class DummyUser:
            id = id_
            is_active = True

        return DummyUser()


async def benchmark_once(n_keys: int, iterations: int = 100, *, use_real_crypto: bool = True):
    settings_service = None
    try:
        settings_service = get_settings_service()
    except Exception:
        settings_service = None

    stored_rows = []
    # generate N keys, keep one matching candidate_key to test hit
    candidate_raw = f"sk-test-{uuid.uuid4()}"

    for i in range(n_keys):
        raw = f"sk-test-{uuid.uuid4()}"
        if i == n_keys - 1:
            raw = candidate_raw
        if use_real_crypto:
            try:
                stored = auth_utils.encrypt_api_key(raw, settings_service=settings_service)
            except Exception:
                stored = f"enc-{raw}"
        else:
            salt = os.urandom(16)
            stored = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt, 10000).hex()
        stored_rows.append((str(i), stored, str(uuid.uuid4())))

    session = MockSession(stored_rows)

    await api_key_crud._check_key_from_db(session, candidate_raw, settings_service)

    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        await api_key_crud._check_key_from_db(session, candidate_raw, settings_service)
        t1 = time.perf_counter()
        timings.append((t1 - t0) * 1000.0)  # ms

    mean = statistics.mean(timings)
    p50 = statistics.median(timings)
    total_ms = sum(timings)
    return {
        "n_keys": n_keys,
        "iterations": iterations,
        "mean_ms": mean,
        "p50_ms": p50,
        "total_ms": total_ms,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("n_keys", [1, 5, 10, 20, 50, 100, 1000])
async def test_benchmark_check_key_from_db_smoke(n_keys):
    """Run a quick smoke benchmark using simulated stored values (no real crypto).

    This test doesn't assert strict performance thresholds — it ensures the
    benchmark runner works under pytest and returns sensible metrics.
    """
    # keep iterations small for CI-friendly run time - use simulated stored values
    r = await benchmark_once(n_keys=n_keys, iterations=5, use_real_crypto=True)

    # basic sanity checks
    assert r["n_keys"] == n_keys
    assert r["mean_ms"] >= 0.0
    assert r["p50_ms"] >= 0.0

    # log results so they are captured by pytest's logging capture
    logger.info(
        "perf n=%s mean=%.2fms p50=%.2fms total=%.2fms",
        n_keys,
        r["mean_ms"],
        r["p50_ms"],
        r["total_ms"],
    )
