"""Unit tests for session_scope_autocommit.

Two layers:
- Unconditional (SQLite): keyword tokenization, guard predicate, gate degradation
  (SQLite never reports READ COMMITTED, cold engine, noop session) and read-result
  equivalence.
- Real-PostgreSQL mechanics (armed scope, write blocking, compound-statement
  rejection, flag lifecycle, nesting, wire-level transaction control and
  cancellation pool fate): these exercise the actual database driver and pool
  behavior. In CI they run in the LFX Tests job (.github/workflows/python_test.yml),
  which provides a postgres:16 service and sets LANGFLOW_TEST_DATABASE_URI, with
  psycopg installed from lfx's dev dependency group. Locally they use
  LANGFLOW_TEST_DATABASE_URI when set, fall back to the optional pgserver
  package, and skip when neither is available.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from lfx.services import deps
from lfx.services.deps import (
    AutocommitReadGuardError,
    _first_sql_keyword,
    _guard_blocked,
    session_scope_autocommit,
    session_scope_readonly,
)
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


class _FakeDbService:
    """Minimal stand-in routing _with_session to an engine-bound session."""

    def __init__(self, engine, shared_session=None):
        self._sessionmaker = _sm(engine)
        self._shared = shared_session

    @asynccontextmanager
    async def _with_session(self):
        if self._shared is not None:
            yield self._shared
        else:
            async with self._sessionmaker() as session:
                yield session


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def pg_uri(tmp_path_factory):
    """Real-PostgreSQL URL for the armed-mechanics tests.

    Resolution order follows the repo convention from the alembic migration
    tests: LANGFLOW_TEST_DATABASE_URI first (the LFX Tests job in
    python_test.yml sets it and provides the postgres:16 service), then the
    optional pgserver package for local runs without a server. Skips when
    neither is available.
    """
    import os

    url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if url:
        yield url.replace("postgresql://", "postgresql+psycopg://", 1).replace(
            "postgres://", "postgresql+psycopg://", 1
        )
        return
    pgserver = pytest.importorskip(
        "pgserver",
        reason="PG mechanics tests need LANGFLOW_TEST_DATABASE_URI or the optional pgserver package",
    )
    server = pgserver.get_server(str(tmp_path_factory.mktemp("pgdata")))
    yield server.get_uri().replace("postgresql://", "postgresql+psycopg://")
    server.cleanup()


@pytest.fixture
async def pg_engine(pg_uri):
    eng = create_async_engine(pg_uri, pool_size=2, max_overflow=0)
    async with eng.begin() as conn:
        await conn.execute(text("SELECT 1"))  # warm: initialize the dialect
    yield eng
    await eng.dispose()


class TestKeywordTokenization:
    def test_simple(self):
        assert _first_sql_keyword("SELECT 1") == "SELECT"

    def test_paren_and_comment_prefixes(self):
        assert _first_sql_keyword("(SELECT 1)") == "SELECT"
        assert _first_sql_keyword("-- hi\nSELECT 1") == "SELECT"
        assert _first_sql_keyword("/* x */ SELECT 1") == "SELECT"

    def test_no_whitespace_forms(self):
        assert _first_sql_keyword("VALUES(1)") == "VALUES"
        assert _first_sql_keyword("SELECT(1)") == "SELECT"
        assert _first_sql_keyword("SELECT/**/1") == "SELECT"

    def test_write_keywords(self):
        assert _first_sql_keyword("INSERT INTO t VALUES (1)") == "INSERT"
        assert _first_sql_keyword("with x as (select 1) select * from x") == "WITH"


class TestGuardBlocked:
    def test_reads_pass(self):
        for stmt in ["SELECT 1", "SHOW x", "VALUES (1)", "WITH a AS (SELECT 1) SELECT * FROM a"]:
            assert not _guard_blocked(stmt)

    def test_writes_blocked(self):
        for stmt in ["INSERT INTO t VALUES (1)", "UPDATE t SET x = 1", "DROP TABLE t", "CREATE TABLE t (id int)"]:
            assert _guard_blocked(stmt)

    def test_any_semicolon_blocks_fail_closed(self):
        assert _guard_blocked("SELECT 1; INSERT INTO t VALUES (1)")
        # documented conservative false positive: semicolon inside a string literal
        assert _guard_blocked("SELECT 'a;b'")


class TestGateAndDegrade:
    async def test_sqlite_gate_degrades_to_plain_session(self, engine, monkeypatch):
        """SQLite never reports READ COMMITTED, so the scope must stay plain."""
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(engine))
        async with session_scope_autocommit() as session:
            assert isinstance(session, AsyncSession)
            conn = await session.connection()
            fairy = conn.sync_connection.connection
            assert not getattr(engine.sync_engine, "_ac_guard_installed", False)
            assert not fairy.info.get("autocommit_read_guard")
            # writes are NOT blocked in a degraded scope
            await session.execute(text("CREATE TABLE t (id INTEGER)"))

    async def test_cold_engine_degrades(self, engine, monkeypatch):
        """A never-connected engine has no isolation attributes: degrade, don't raise."""
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(engine))
        async with session_scope_autocommit() as session:
            await session.execute(text("SELECT 1"))

    async def test_noop_session_passthrough(self, monkeypatch):
        from lfx.services.session import NoopSession

        class _NoopService:
            @asynccontextmanager
            async def _with_session(self):
                async with NoopSession() as s:
                    yield s

        monkeypatch.setattr(deps, "get_db_service", lambda: _NoopService())
        async with session_scope_autocommit() as session:
            assert isinstance(session, NoopSession)

    async def test_result_equivalence_sqlite(self, engine, monkeypatch):
        """Reads return identical results through the degraded scope and plain scope."""
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(engine))
        async with engine.begin() as c:
            await c.execute(text("CREATE TABLE t (id INTEGER)"))
            await c.execute(text("INSERT INTO t VALUES (1), (2), (3)"))
        async with session_scope_autocommit() as session:
            rows = (await session.execute(text("SELECT id FROM t ORDER BY id"))).scalars().all()
        assert rows == [1, 2, 3]


class TestArmedScopePostgres:
    """Armed-scope mechanics on a real PostgreSQL driver (skipped without a PG URL)."""

    async def test_armed_read_passes_and_write_blocked(self, pg_engine, monkeypatch):
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(pg_engine))
        async with session_scope_autocommit() as session:
            await session.execute(text("SELECT 1"))
            with pytest.raises(AutocommitReadGuardError):
                await session.execute(text("CREATE TABLE blocked (id int)"))
            # session still usable for reads after a blocked statement
            await session.execute(text("SELECT 2"))
            # driver connection really is in autocommit inside the armed scope;
            # psycopg exposes the flag on the raw driver connection, asyncpg on
            # SQLAlchemy's adapted connection
            conn = await session.connection()
            fairy = conn.sync_connection.connection
            if pg_engine.dialect.driver == "asyncpg":
                assert fairy.dbapi_connection.autocommit is True
            else:
                assert fairy.driver_connection.autocommit is True
        assert getattr(pg_engine.sync_engine, "_ac_guard_installed", False) is True

    async def test_finally_clears_flag_on_same_connection(self, pg_uri, monkeypatch):
        """Scope-exit finally must clear the flag on the very connection it armed.

        pool_size=1 pins the physical connection; no new checkout happens between
        scope exit and the assertion, so only the finally (not the checkout
        listener) can have cleared it. The old pool_size=2 form could not see a
        stale flag if the pool handed out the other connection.
        """
        eng = create_async_engine(pg_uri, pool_size=1, max_overflow=0)
        try:
            async with eng.connect():  # warm up: a cold engine degrades by design
                pass
            monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(eng))
            async with session_scope_autocommit() as session:
                conn = await session.connection()
                # capture the record's info dict while checked out, so the
                # post-exit assert reads the same dict the finally wrote to
                info_dict = conn.sync_connection.connection.info
                assert info_dict.get("autocommit_read_guard") is True
            assert not info_dict.get("autocommit_read_guard")
        finally:
            await eng.dispose()

    async def test_checkout_listener_clears_orphaned_flag(self, pg_uri):
        """An orphaned flag (finally bypassed) must be cleared by the pool checkout.

        The checkout listener bounds the flag's lifetime so it can never poison a
        later borrower of the same connection. The guardless control engine proves
        the listener is the clearing agent.
        """
        eng = create_async_engine(pg_uri, pool_size=1, max_overflow=0)
        try:
            deps.ensure_autocommit_guard(eng.sync_engine)
            async with eng.connect() as c:
                info_dict = c.sync_connection.connection.info
                info_dict["autocommit_read_guard"] = True  # orphan it by hand
            async with eng.connect() as c2:
                # pool_size=1: the checkout reused the same record (same info dict)
                assert c2.sync_connection.connection.info is info_dict
                assert not info_dict.get("autocommit_read_guard")
        finally:
            await eng.dispose()
        control = create_async_engine(pg_uri, pool_size=1, max_overflow=0)
        try:
            async with control.connect() as c:
                control_info = c.sync_connection.connection.info
                control_info["autocommit_read_guard"] = True
            async with control.connect() as c2:
                assert c2.sync_connection.connection.info is control_info
                # no listener installed: the orphaned flag survives a checkout
                assert control_info.get("autocommit_read_guard") is True
        finally:
            await control.dispose()

    async def test_compound_statement_blocked(self, pg_engine, monkeypatch):
        """psycopg3 sends parameterless multi-statements over the simple protocol.

        Without the semicolon reject the write would land (executed in review).
        """
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(pg_engine))
        async with session_scope_autocommit() as session:
            with pytest.raises(AutocommitReadGuardError):
                await session.execute(text("SELECT 1; CREATE TABLE t (id int)"))

    async def test_guard_installed_once_per_engine(self, pg_engine, monkeypatch):
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(pg_engine))
        calls = []
        real_listen = event.listen

        def spy(*args, **kwargs):
            calls.append(args)
            return real_listen(*args, **kwargs)

        monkeypatch.setattr(deps.event, "listen", spy)
        async with session_scope_autocommit():
            pass
        async with session_scope_autocommit():
            pass
        assert len(calls) == 2  # one pair, installed once, reused on the second scope

    async def test_nested_armed_scope_rejected_outer_survives(self, pg_engine, monkeypatch):
        # a service whose _with_session yields the SAME session twice models an
        # (unsupported) nested/reused-session entry into the helper
        async with _sm(pg_engine)() as shared:
            monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(pg_engine, shared_session=shared))
            async with session_scope_autocommit() as outer:
                assert outer is shared
                with pytest.raises(AutocommitReadGuardError):
                    async with session_scope_autocommit():
                        pass
                # outer flag survived the rejected inner entry
                conn = await outer.connection()
                fairy_info = conn.sync_connection.connection.info
                assert fairy_info.get("autocommit_read_guard") is True
                # outer scope still blocks writes
                with pytest.raises(AutocommitReadGuardError):
                    await outer.execute(text("CREATE TABLE blocked (id int)"))
            # outer exit cleaned up (asserting on the dict captured while
            # checked out above)
            assert not fairy_info.get("autocommit_read_guard")

    async def test_with_led_top_level_dml_passes_disclosed(self, pg_engine, monkeypatch):
        """DISCLOSED LIMITATION, pinned.

        WITH-led statements can write via data-modifying CTEs or top-level DML
        after the WITH clause (no semicolon needed). The per-caller audit, not
        the guard, is the safety mechanism.
        """
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(pg_engine))
        async with pg_engine.begin() as c:
            await c.execute(text("DROP TABLE IF EXISTS t_with"))
            await c.execute(text("CREATE TABLE t_with (id int)"))
        async with session_scope_autocommit() as session:
            result = await session.execute(text("WITH a AS (SELECT 1) INSERT INTO t_with SELECT 1 RETURNING 1"))
            assert result.scalar() == 1  # passes the guard and lands: disclosed


def _traced_engine(pg_uri, trace_path, enable):
    """Engine whose NEW raw connections get a libpq wire trace once enabled."""
    import psycopg

    eng = create_async_engine(pg_uri, pool_size=1, max_overflow=0)
    trace_file = Path(trace_path).open("wb")  # noqa: SIM115 - closed by the caller after engine disposal

    def on_connect(dbapi_connection, _connection_record):
        if not enable["on"]:
            return
        real = getattr(dbapi_connection, "driver_connection", None) or dbapi_connection
        pgconn = real.pgconn
        pgconn.set_trace_flags(psycopg.pq.Trace.SUPPRESS_TIMESTAMPS | psycopg.pq.Trace.REGRESS_MODE)
        pgconn.trace(trace_file.fileno())

    event.listen(eng.sync_engine, "connect", on_connect)
    return eng, trace_file


def _trace_counts(path):
    data = Path(path).read_bytes().decode("utf-8", "replace")
    return {
        "BEGIN": len(re.findall(r'Query\s+"(?:BEGIN|START TRANSACTION)"', data)),
        "COMMIT": len(re.findall(r'Query\s+"COMMIT"', data)),
        "ROLLBACK": len(re.findall(r'Query\s+"ROLLBACK"', data)),
        # extended-protocol parses of transaction control (psycopg style)
        "BEGIN_parse": len(re.findall(r'Parse\s+\S*\s*"(?:BEGIN|START TRANSACTION)', data)),
        "COMMIT_parse": len(re.findall(r'Parse\s+\S*\s*"COMMIT', data)),
        "ROLLBACK_parse": len(re.findall(r'Parse\s+\S*\s*"ROLLBACK', data)),
        "SELECT_seen": "SELECT 1" in data,
    }


@pytest.fixture
def pg_psycopg_uri(pg_uri):
    """Libpq wire tracing is psycopg-specific; skip on other drivers."""
    if "+asyncpg" in pg_uri:
        pytest.skip("wire-trace tests use psycopg's PQtrace and need a psycopg URI")
    return pg_uri


class TestWireTrace:
    """Wire-level proof of the round-trip savings, relative not absolute.

    The armed scope must emit no transaction control for a single read; the
    readonly scope must pay teardown. The assertion is structural (no BEGIN /
    COMMIT / ROLLBACK on the wire), not a universal fixed wire-command count:
    exact counts are driver- and protocol-dependent.
    """

    async def test_armed_scope_wire_has_no_txn_control(self, pg_psycopg_uri, monkeypatch, tmp_path):
        enable = {"on": False}
        eng, tf = _traced_engine(pg_psycopg_uri, str(tmp_path / "ac.trace"), enable)
        async with eng.begin() as c:
            await c.execute(text("SELECT 1"))  # warm dialect (untraced)
        enable["on"] = True
        await eng.dispose()  # force a fresh, traced raw connection
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(eng))
        async with session_scope_autocommit() as session:
            await session.execute(text("SELECT 1"))
        await eng.dispose()
        tf.close()
        counts = _trace_counts(str(tmp_path / "ac.trace"))
        assert counts["SELECT_seen"], counts
        txn = (
            counts["BEGIN"]
            + counts["COMMIT"]
            + counts["ROLLBACK"]
            + counts["BEGIN_parse"]
            + counts["COMMIT_parse"]
            + counts["ROLLBACK_parse"]
        )
        assert txn == 0, f"transaction control on the wire in autocommit scope: {counts}"

    async def test_readonly_scope_wire_pays_txn_teardown(self, pg_psycopg_uri, monkeypatch, tmp_path):
        enable = {"on": False}
        eng, tf = _traced_engine(pg_psycopg_uri, str(tmp_path / "ro.trace"), enable)
        async with eng.begin() as c:
            await c.execute(text("SELECT 1"))
        enable["on"] = True
        await eng.dispose()
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(eng))
        async with session_scope_readonly() as session:
            await session.execute(text("SELECT 1"))
        await eng.dispose()
        tf.close()
        counts = _trace_counts(str(tmp_path / "ro.trace"))
        assert counts["SELECT_seen"], counts
        teardown = counts["COMMIT"] + counts["ROLLBACK"] + counts["COMMIT_parse"] + counts["ROLLBACK_parse"]
        assert teardown >= 1, f"readonly scope paid no teardown round trip? {counts}"


class TestCancellationPoolFate:
    """A cancelled scope must not poison the pool for the next borrower."""

    async def _cancel_probe(self, pg_uri, monkeypatch, scope_factory):
        eng = create_async_engine(pg_uri, pool_size=1, max_overflow=0)
        async with eng.begin() as c:
            await c.execute(text("SELECT 1"))  # warm dialect
        monkeypatch.setattr(deps, "get_db_service", lambda: _FakeDbService(eng))
        started = asyncio.Event()

        def spy(_conn, _cursor, statement, _parameters, _context, _executemany):
            if "pg_sleep" in statement:
                started.set()

        event.listen(eng.sync_engine, "before_cursor_execute", spy)
        outcome = {}

        async def victim():
            try:
                async with scope_factory() as session:
                    await session.execute(text("SELECT pg_backend_pid()"))
                    await session.execute(text("SELECT pg_sleep(30)"))
                outcome["result"] = "completed"
            except BaseException as e:
                outcome["result"] = type(e).__name__
                raise

        task = asyncio.create_task(victim())
        await asyncio.wait_for(started.wait(), timeout=10)
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=15)
        assert outcome["result"] == "CancelledError", outcome

        # same single-connection pool: the next scope must get a usable connection
        async def fresh_read():
            async with scope_factory() as session:
                return (await session.execute(text("SELECT 1"))).scalar()

        val = await asyncio.wait_for(fresh_read(), timeout=15)
        await eng.dispose()
        return val

    async def test_cancel_armed_scope_pool_size_1(self, pg_uri, monkeypatch):
        val = await self._cancel_probe(pg_uri, monkeypatch, session_scope_autocommit)
        assert val == 1

    async def test_cancel_readonly_scope_pool_size_1(self, pg_uri, monkeypatch):
        val = await self._cancel_probe(pg_uri, monkeypatch, session_scope_readonly)
        assert val == 1
