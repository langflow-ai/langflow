# src/backend/tests/perf/check_key_benchmark.py
import logging
import statistics
import time
import uuid

import pytest
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.api_key import crud as api_key_crud
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


def _get_test_password() -> str:
    """Generate a unique test password for benchmark runs."""
    return str(uuid.uuid4())


class DummyResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


async def benchmark_once(
    n_keys: int,
    iterations: int = 100,
    async_db_session: AsyncSession | None = None,
):
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
        try:
            stored = auth_utils.encrypt_api_key(raw, settings_service=settings_service)
        except Exception:
            stored = f"enc-{raw}"
        stored_rows.append((str(i), stored, str(uuid.uuid4())))

    if async_db_session is not None:
        # use provided async session fixture to mimic DB
        db_session = async_db_session
        # create a user
        user = User(username=f"u-{uuid.uuid4()}", password=_get_test_password())
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        for i, (_, stored, _uid) in enumerate(stored_rows):
            api = ApiKey(api_key=stored, name=f"k-{i}", user_id=user.id)
            db_session.add(api)
        await db_session.commit()

        timings = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            await api_key_crud._check_key_from_db(db_session, candidate_raw, settings_service)
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


@pytest.mark.parametrize("n_keys", [1, 10, 50, 100, 1000])
async def test_benchmark_check_key_from_db_smoke(async_session: AsyncSession, n_keys):
    """Run a quick smoke benchmark using simulated stored values (no real crypto).

    This test doesn't assert strict performance thresholds — it ensures the
    benchmark runner works under pytest and returns sensible metrics.
    """
    # keep iterations small for CI-friendly run time - use async session fixture
    r = await benchmark_once(n_keys=n_keys, iterations=5, async_db_session=async_session)

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
