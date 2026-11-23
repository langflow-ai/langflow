"""Tests for idle-gated pool pre-ping on DatabaseService engines."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import sqlalchemy as sa
from langflow.services.database.service import _configure_idle_pre_ping
from sqlalchemy.ext.asyncio import create_async_engine


class _FakeClock:
    def __init__(self, initial: float = 100.0) -> None:
        self.now = initial

    def __call__(self) -> float:
        return self.now


@pytest.mark.asyncio
async def test_idle_pre_ping_skips_fresh_and_recent_checkouts_and_probes_after_idle(tmp_path):
    db_file = tmp_path / "idle_probe.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", pool_pre_ping=False)
    clock = _FakeClock()
    ping_results = [True]

    try:
        with (
            patch("langflow.services.database.service.time.monotonic", side_effect=clock),
            patch.object(
                engine.sync_engine.dialect,
                "do_ping",
                side_effect=lambda _conn: ping_results.pop(0),
            ) as mock_ping,
        ):
            _configure_idle_pre_ping(engine, idle_seconds=10.0)

            # 1. First checkout (fresh connection): no ping
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            assert mock_ping.call_count == 0

            # 2. Immediate re-checkout (idle 2s < 10s): no ping
            clock.now += 2.0
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            assert mock_ping.call_count == 0

            # 3. Re-checkout after >= 10s idle: probes via do_ping
            clock.now += 10.0
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            assert mock_ping.call_count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_idle_pre_ping_invalidates_stale_connection_on_failed_probe(tmp_path):
    db_file = tmp_path / "idle_stale.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", pool_pre_ping=False)
    clock = _FakeClock()
    # First probe fails (stale connection); SQLAlchemy invalidates & reconnects transparently
    ping_calls: list[bool] = []

    def _fake_ping(_conn) -> bool:
        result = len(ping_calls) > 0
        ping_calls.append(result)
        return result

    try:
        with (
            patch("langflow.services.database.service.time.monotonic", side_effect=clock),
            patch.object(engine.sync_engine.dialect, "do_ping", side_effect=_fake_ping),
        ):
            _configure_idle_pre_ping(engine, idle_seconds=5.0)

            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            assert ping_calls == []

            clock.now += 6.0
            async with engine.connect() as conn:
                res = await conn.execute(sa.text("SELECT 1"))
                assert res.scalar_one() == 1
            assert ping_calls == [False]
    finally:
        await engine.dispose()
