"""The startup warning for a pool ceiling that exceeds the server's limit.

Why this matters: the pool ceiling is per WORKER PROCESS, so a deployment can
demand ``workers * (pool_size + max_overflow)`` connections. The shipped
defaults (20 + 30) with 4 workers reach 200 against a stock Postgres limit of
100 -- no single setting looks wrong, and the failure surfaces as "too many
clients already" inside an unrelated request. These tests pin the arithmetic and,
just as importantly, pin that a failed probe can never block startup.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from langflow.services.database.service import DatabaseService


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _Conn:
    """Answers the two SHOW probes; raises if asked anything unexpected."""

    def __init__(self, max_connections: int, reserved: int, *, fail: bool = False):
        self._answers = {
            "SHOW max_connections": max_connections,
            "SHOW superuser_reserved_connections": reserved,
        }
        self._fail = fail

    async def exec_driver_sql(self, sql: str):
        if self._fail:
            msg = "connection lost"
            raise RuntimeError(msg)
        return _Result(self._answers[sql])


def _service(*, pool_size, max_overflow, workers, max_connections=100, reserved=3, fail=False,
             telemetry_writer=False, database_url="postgresql://x/y"):
    conn = _Conn(max_connections, reserved, fail=fail)

    @asynccontextmanager
    async def _connect():
        yield conn

    kwargs = {}
    if pool_size is not None:
        kwargs["pool_size"] = pool_size
    if max_overflow is not None:
        kwargs["max_overflow"] = max_overflow

    return SimpleNamespace(
        database_url=database_url,
        settings_service=SimpleNamespace(
            settings=SimpleNamespace(workers=workers, telemetry_writer_enabled=telemetry_writer)
        ),
        _build_connection_kwargs=lambda: kwargs,
        engine=SimpleNamespace(connect=_connect),
    )


@pytest.fixture
def captured(monkeypatch):
    """Capture what the service logged, without asserting on message wording."""
    out = {"warning": [], "debug": []}
    import langflow.services.database.service as mod

    monkeypatch.setattr(mod.logger, "warning", lambda m, *_a, **_k: out["warning"].append(str(m)))
    monkeypatch.setattr(mod.logger, "debug", lambda m, *_a, **_k: out["debug"].append(str(m)))
    return out


async def test_warns_when_ceiling_exceeds_available(captured):
    """The shipped defaults on 4 workers: 4 * (20 + 30) = 200 > 100 - 3."""
    svc = _service(pool_size=20, max_overflow=30, workers=4)
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)

    assert len(captured["warning"]) == 1
    msg = captured["warning"][0]
    assert "200" in msg, "must state the ceiling it computed"
    assert "97" in msg, "must state what the server actually allows (100 - 3)"


async def test_silent_when_budget_fits(captured):
    """A single worker with the same pool fits comfortably and must not warn."""
    svc = _service(pool_size=20, max_overflow=30, workers=1)
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)

    assert captured["warning"] == []
    assert any("budget OK" in m for m in captured["debug"])


async def test_exactly_at_the_limit_does_not_warn(captured):
    """The boundary is inclusive: a ceiling equal to what is available is fine."""
    # 1 worker x (90 + 7) == 97 == 100 - 3
    svc = _service(pool_size=90, max_overflow=7, workers=1)
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)

    assert captured["warning"] == []


async def test_one_over_the_limit_warns(captured):
    svc = _service(pool_size=90, max_overflow=8, workers=1)
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)

    assert len(captured["warning"]) == 1


async def test_workers_multiply_the_ceiling(captured):
    """Each worker owns an independent pool -- the ceiling scales with workers."""
    svc = _service(pool_size=10, max_overflow=10, workers=8)  # 8 * 20 = 160 > 97
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)

    assert len(captured["warning"]) == 1
    assert "160" in captured["warning"][0]


async def test_absent_keys_fall_back_to_sqlalchemy_defaults(captured):
    """An empty db_connection_settings means SQLAlchemy's own 5 + 10, not zero.

    Assuming 0 here would make the check silently unable to ever fire.
    """
    svc = _service(pool_size=None, max_overflow=None, workers=20)  # 20 * (5 + 10) = 300
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)

    assert len(captured["warning"]) == 1
    assert "300" in captured["warning"][0]


async def test_probe_failure_never_blocks_startup(captured):
    """If the server cannot be probed, log and move on -- never raise."""
    svc = _service(pool_size=20, max_overflow=30, workers=4, fail=True)
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)

    assert captured["warning"] == []
    assert any("Could not read server connection limits" in m for m in captured["debug"])


async def test_workers_none_is_treated_as_one(captured):
    """A missing/zero worker count must not zero out the ceiling."""
    svc = _service(pool_size=20, max_overflow=30, workers=None)
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)

    # 1 * 50 = 50 <= 97 -> no warning, and crucially no crash on None
    assert captured["warning"] == []


async def test_telemetry_writer_pool_is_counted(captured):
    """The writer builds its OWN engine; omitting it under-reports the real ceiling.

    A check that says "you fit" when the deployment actually does not is worse
    than no check, so its connections must be in the arithmetic.
    """
    # 4 x (10 + 12) = 88 fits in 97; adding 4 x 2 writer connections makes 96, still fits.
    svc = _service(pool_size=10, max_overflow=12, workers=4, telemetry_writer=True)
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)
    assert captured["warning"] == []

    # 4 x (10 + 14) = 96 fits, but + 4 x 2 writer = 104 does NOT.
    out = captured["debug"], captured["warning"]
    svc2 = _service(pool_size=10, max_overflow=14, workers=4, telemetry_writer=True)
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc2)
    assert len(captured["warning"]) == 1, "writer connections must push this over the limit"
    assert "104" in captured["warning"][0]
    assert "telemetry-writer" in captured["warning"][0], "the message must show where the extra came from"
    assert out is not None


async def test_sqlite_writer_counts_one_not_two(captured):
    """_create_dedicated_engine uses pool_size=1 on sqlite; the check must match."""
    svc = _service(pool_size=10, max_overflow=14, workers=4, telemetry_writer=True,
                   database_url="sqlite:///x.db")
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)
    # 96 + 4 x 1 = 100 > 97
    assert len(captured["warning"]) == 1
    assert "100" in captured["warning"][0]


async def test_writer_disabled_is_not_counted(captured):
    svc = _service(pool_size=10, max_overflow=14, workers=4, telemetry_writer=False)
    await DatabaseService.warn_if_connection_budget_exceeds_server_limit(svc)
    assert captured["warning"] == [], "96 fits in 97 when the writer is off"
