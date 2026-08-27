
"""Adaptive pre-ping must skip fresh connections AND still protect stale ones.

The optimization is only defensible if both halves hold. Skipping the ping is
what makes it fast; still pinging an idle connection -- and transparently
replacing it when that ping fails -- is what keeps it safe. A version that only
did the first half would be `pool_pre_ping=False` with extra steps, and would
look identical on a benchmark.
"""

import time
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from langflow.services.database.service import DatabaseService
from sqlalchemy.exc import DisconnectionError


class _Cursor:
    def __init__(self, record, fail):
        self._record, self._fail = record, fail

    def execute(self, sql):
        self._record.append(sql)
        if self._fail:
            msg = "server closed the connection unexpectedly"
            raise OSError(msg)

    def close(self):
        pass


class _Conn:
    """Minimal DBAPI stand-in that records whether it was pinged."""

    def __init__(self, *, fail=False):
        self.executed: list[str] = []
        self._fail = fail

    def cursor(self):
        return _Cursor(self.executed, self._fail)


def _install(threshold, kwargs=None):
    """Attach the adaptive ping to a throwaway engine, exactly as production does."""
    # Created WITH pre-ping so the "did we leave SQLAlchemy in charge?"
    # assertions below are testing the code rather than the fixture.
    engine = sa.create_engine("sqlite://", pool_pre_ping=True)
    svc = SimpleNamespace(
        settings_service=SimpleNamespace(
            settings=SimpleNamespace(pool_pre_ping_idle_threshold_s=threshold)
        )
    )

    class _FakeAsyncEngine:
        """Stands in for AsyncEngine: the code needs .sync_engine and .pool."""

        def __init__(self, sync_engine):
            self.sync_engine = sync_engine
            self.pool = sync_engine.pool

    fake = _FakeAsyncEngine(engine)
    DatabaseService._install_adaptive_pre_ping(svc, fake, kwargs or {"pool_pre_ping": True})
    return {"engine": engine, "fake": fake}


def _fire_checkout(engine, dbapi_conn, record):
    """Invoke checkout listeners the way the pool does. `checkout` is a POOL event."""
    engine.pool.dispatch.checkout(dbapi_conn, record, None)


def _fire_checkin(engine, dbapi_conn, record):
    engine.pool.dispatch.checkin(dbapi_conn, record)


def test_fresh_connection_is_not_pinged():
    """The whole point: a connection returned moments ago costs no round trip."""
    c = _install(threshold=20.0)
    conn, rec = _Conn(), SimpleNamespace(info={})
    _fire_checkin(c["engine"], conn, rec)
    _fire_checkout(c["engine"], conn, rec)

    assert conn.executed == [], "a just-returned connection must not be validated"


def test_idle_connection_is_pinged():
    """The safety half: past the threshold the connection IS validated."""
    c = _install(threshold=20.0)
    conn, rec = _Conn(), SimpleNamespace(info={"lf_last_checkin": time.monotonic() - 60})
    _fire_checkout(c["engine"], conn, rec)

    assert conn.executed == ["SELECT 1"], "a long-idle connection must be validated"


def test_never_checked_in_connection_is_pinged():
    """No recorded checkin means unknown age, which must be treated as stale."""
    c = _install(threshold=20.0)
    conn, rec = _Conn(), SimpleNamespace(info={})
    _fire_checkout(c["engine"], conn, rec)

    assert conn.executed == ["SELECT 1"]


def test_dead_idle_connection_raises_disconnection_error():
    """A failed ping must ask the pool to replace the connection, not surface an error.

    DisconnectionError is the documented signal for "discard and retry"; any other
    exception would reach the caller as a request failure.
    """
    c = _install(threshold=20.0)
    conn = _Conn(fail=True)
    rec = SimpleNamespace(info={"lf_last_checkin": time.monotonic() - 60})

    with pytest.raises(DisconnectionError):
        _fire_checkout(c["engine"], conn, rec)


def test_threshold_zero_restores_stock_behaviour():
    """0 must mean 'validate every checkout', not 'never validate'."""
    c = _install(threshold=0)
    conn, rec = _Conn(), SimpleNamespace(info={})
    _fire_checkin(c["engine"], conn, rec)
    _fire_checkout(c["engine"], conn, rec)

    # With the adaptive path disabled, SQLAlchemy's own pre-ping stays in charge.
    assert c["fake"].pool._pre_ping is True
    assert conn.executed == []


def test_no_op_when_pre_ping_disabled():
    """If the operator turned pre-ping off, this must not turn it back on."""
    c = _install(threshold=20.0, kwargs={"pool_pre_ping": False})
    conn, rec = _Conn(), SimpleNamespace(info={})
    _fire_checkout(c["engine"], conn, rec)

    assert conn.executed == []
