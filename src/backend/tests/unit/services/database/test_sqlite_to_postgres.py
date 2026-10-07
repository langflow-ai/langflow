"""Tests for converting a Langflow SQLite database to Postgres.

The coercion, ordering and source checks need no Postgres. The end-to-end tests
build a real SQLite instance with alembic, convert it into a fresh Postgres
database and read the result back. They run when ``LANGFLOW_TEST_DATABASE_URI``
points at a Postgres server the tests can create databases on, as in the
migration validation workflow.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
import tracemalloc
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from langflow.services.database.sqlite_to_postgres import (
    coerce_value,
    convert_sqlite_to_postgres,
    copy_order,
    upgrade_to_head,
)
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from pathlib import Path


class TestCoerceValue:
    def test_sqlite_integers_become_booleans(self):
        assert coerce_value(1, sa.Boolean()) is True
        assert coerce_value(0, sa.Boolean()) is False

    @pytest.mark.parametrize("dashed", [True, False])
    def test_both_uuid_spellings_become_uuids(self, dashed):
        expected = uuid.uuid4()
        raw = str(expected) if dashed else expected.hex
        assert coerce_value(raw, postgresql.UUID()) == expected

    def test_json_text_is_parsed(self):
        assert coerce_value('{"a": [1, 2]}', postgresql.JSONB()) == {"a": [1, 2]}
        assert coerce_value('["x"]', sa.JSON()) == ["x"]

    def test_already_parsed_json_is_left_alone(self):
        assert coerce_value({"a": 1}, sa.JSON()) == {"a": 1}

    def test_sqlite_datetime_text_is_parsed(self):
        assert coerce_value("2026-09-10 14:37:14.607610", sa.DateTime()) == datetime(2026, 9, 10, 14, 37, 14, 607610)  # noqa: DTZ001 - naive column

    def test_naive_datetime_for_a_timezone_column_is_read_as_utc(self):
        got = coerce_value("2026-09-10 14:37:14", sa.DateTime(timezone=True))
        assert got == datetime(2026, 9, 10, 14, 37, 14, tzinfo=timezone.utc)

    def test_offset_on_a_naive_column_is_stored_as_utc_wall_time(self):
        # Rows written through raw SQL can keep an offset. Bound as-is, Postgres converts
        # it to the session time zone, which is not UTC on every server.
        got = coerce_value("2026-09-10 16:37:14+02:00", sa.DateTime())
        assert got == datetime(2026, 9, 10, 14, 37, 14)  # noqa: DTZ001 - naive column
        assert got.tzinfo is None

    def test_none_and_untyped_values_pass_through(self):
        assert coerce_value(None, sa.Boolean()) is None
        assert coerce_value("text", sa.String()) == "text"


def test_copy_order_puts_parents_first_and_sso_config_before_sso_settings():
    import langflow.services.database.models  # noqa: F401 - importing registers every table on the metadata
    from sqlmodel import SQLModel

    order = [table.name for table in copy_order(SQLModel.metadata)]

    assert order.index("user") < order.index("flow") < order.index("flow_version")
    assert order.index("authz_role") < order.index("authz_role_assignment")
    # A compatibility trigger syncs enforce_sso between these two, so the
    # singleton has to be written after the config rows it mirrors.
    assert order.index("sso_config") < order.index("sso_settings")


@pytest.fixture
def run_cli(caplog):
    """Run the command in this process and return what it wrote and how it exited.

    Alembic logs every migration at INFO. The real process sends that to stderr, but
    a pytest plugin's log handler prints it on stdout, so INFO is switched off here.
    """
    from langflow.__main__ import app
    from typer.testing import CliRunner

    def run(*args: str, env: dict[str, str] | None = None):
        with caplog.at_level(logging.WARNING):
            return CliRunner().invoke(app, ["convert-sqlite-to-postgres", *args], env=env)

    return run


def _events(result) -> list[dict]:
    # Every line has to parse: a program reading --json cannot skip stray text.
    return [json.loads(line) for line in result.stdout.splitlines()]


# What a --json run says before the first table, so a slow start does not look like a hang.
CHECKING = {"event": "progress", "phase": "checking", "done": 0, "total": None, "unit": "rows"}
PREPARING_TARGET = {"event": "progress", "phase": "preparing_target", "done": 0, "total": None, "unit": "rows"}


class TestSourceChecks:
    # The target is never reached, so these need no Postgres server.
    UNREACHABLE_TARGET = "postgresql://nobody@127.0.0.1:1/none"

    def test_missing_source_file_is_refused_and_not_created(self, tmp_path):
        missing = tmp_path / "typo.db"

        report = convert_sqlite_to_postgres(f"sqlite:///{missing}", self.UNREACHABLE_TARGET)

        assert not report.ok
        assert any("does not exist" in p for p in report.problems)
        assert [p.code for p in report.problems] == ["source_missing"]
        assert not missing.exists()

    def test_source_without_langflow_schema_points_at_how_the_copy_was_made(self, tmp_path):
        empty = tmp_path / "copied.db"
        sqlite3.connect(empty).close()

        report = convert_sqlite_to_postgres(f"sqlite:///{empty}", self.UNREACHABLE_TARGET)

        assert not report.ok
        assert any("no Langflow schema" in p and "VACUUM INTO" in p for p in report.problems)
        assert [p.code for p in report.problems] == ["source_not_langflow"]

    def test_source_at_another_revision_is_refused(self, sqlite_source):
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE alembic_version SET version_num = 'older'"))
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, self.UNREACHABLE_TARGET)

        assert any("is at revision older" in p for p in report.problems)
        assert [p.code for p in report.problems] == ["source_not_at_head"]

    def test_source_url_that_does_not_parse_is_reported(self, run_cli):
        result = run_cli("--json", "--source", "not a url", "--target", self.UNREACHABLE_TARGET)

        assert result.exit_code == 1
        # A traceback instead would leave a program reading --json without its report line.
        assert isinstance(result.exception, SystemExit)
        checking, error, report = _events(result)
        assert checking == CHECKING
        assert (error["event"], error["code"]) == ("error", "source_unreadable")
        assert error["message"].startswith("could not read the source database: ")
        assert report["problems"] == [{"code": "source_unreadable", "message": error["message"]}]

    def test_source_url_with_a_port_that_is_not_a_number_is_reported(self, run_cli):
        # SQLAlchemy raises a bare ValueError for this one, not its own ArgumentError.
        source = "sqlite://user@localhost:not-a-port/db"

        result = run_cli("--json", "--source", source, "--target", self.UNREACHABLE_TARGET)

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        checking, error, report = _events(result)
        assert checking == CHECKING
        assert (error["event"], error["code"]) == ("error", "source_unreadable")
        assert error["message"].startswith("could not read the source database: the URL could not be read")
        assert (report["event"], report["ok"]) == ("report", False)
        assert report["problems"] == [{"code": "source_unreadable", "message": error["message"]}]

    @pytest.mark.parametrize(
        "source",
        [
            "sqlite:///{path}?timeout=soon",  # a ValueError, from an option instead of the port
            "sqlite+nope:///{path}",  # no such driver
            "sqlite+pysqlcipher:///{path}",  # a driver that is not installed
        ],
    )
    def test_source_url_refused_once_the_file_is_found_is_reported(self, tmp_path, monkeypatch, source):
        # The file exists, so these get past the missing-file check and fail building the engine.
        (tmp_path / "langflow.db").touch()
        monkeypatch.setitem(sys.modules, "pysqlcipher3", None)
        monkeypatch.setitem(sys.modules, "sqlcipher3", None)

        report = convert_sqlite_to_postgres(source.format(path=tmp_path / "langflow.db"), self.UNREACHABLE_TARGET)

        assert [p.code for p in report.problems] == ["source_unreadable"]

    def test_source_file_that_is_not_a_database_is_reported(self, tmp_path, run_cli):
        notes = tmp_path / "notes.db"
        notes.write_text("Not a SQLite file, only text that is longer than the header SQLite reads first. " * 4)

        result = run_cli("--json", "--source", f"sqlite:///{notes}", "--target", self.UNREACHABLE_TARGET)

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        checking, error, report = _events(result)
        assert checking == CHECKING
        assert (error["event"], error["code"]) == ("error", "source_unreadable")
        assert error["message"].startswith("could not read the source database: ")
        assert "file is not a database" in error["message"]
        assert report["problems"] == [{"code": "source_unreadable", "message": error["message"]}]

    def test_unreachable_target_is_reported_without_the_password(self, sqlite_source):
        from langflow.__main__ import app
        from typer.testing import CliRunner

        secret = "SuperSecretPw123"  # noqa: S105  # pragma: allowlist secret
        target = f"postgresql://postgres:{secret}@127.0.0.1:1/none"

        result = CliRunner().invoke(app, ["convert-sqlite-to-postgres", "--source", sqlite_source, "--target", target])

        assert result.exit_code == 1
        # An exception escaping the command is printed by Typer with its locals, URL included.
        assert result.exception is None or isinstance(result.exception, SystemExit)
        assert "Problem:" in result.output
        assert secret not in result.output

    def test_a_missing_postgres_driver_is_reported(self, sqlite_source, monkeypatch):
        # CI's unit environment has no Postgres driver. An unhandled ImportError
        # would reach the same traceback that prints the password.
        monkeypatch.setitem(sys.modules, "psycopg", None)

        report = convert_sqlite_to_postgres(sqlite_source, "postgresql+psycopg://user:pw@127.0.0.1:1/none")

        assert not report.ok
        assert any("langflow[postgresql]" in problem for problem in report.problems)
        assert [p.code for p in report.problems] == ["target_unreachable"]

    def test_json_reports_an_unreachable_target_and_ends_with_the_report(self, sqlite_source, run_cli):
        result = run_cli("--json", "--source", sqlite_source, "--target", self.UNREACHABLE_TARGET)

        assert result.exit_code == 1
        checking, error, report = _events(result)
        assert checking == CHECKING
        assert (error["event"], error["code"]) == ("error", "target_unreachable")
        assert report == {
            "event": "report",
            "ok": False,
            "revision": report["revision"],
            "tables_copied": 0,
            "rows_copied": 0,
            "orphans": [],
            "problems": [{"code": "target_unreachable", "message": error["message"]}],
        }

    def test_target_url_with_a_port_that_is_not_a_number_is_reported(self, sqlite_source, run_cli):
        target = "postgresql://user@localhost:not-a-port/db"

        result = run_cli("--json", "--source", sqlite_source, "--target", target)

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        checking, error, report = _events(result)
        assert checking == CHECKING
        assert (error["event"], error["code"]) == ("error", "target_unreachable")
        assert error["message"].startswith("could not use the target database: the URL could not be read")
        assert (report["event"], report["ok"]) == ("report", False)
        assert report["problems"] == [{"code": "target_unreachable", "message": error["message"]}]

    def test_target_host_the_driver_cannot_encode_is_reported(self, sqlite_source, run_cli):
        # An empty label fails before any lookup, with a UnicodeError the driver lets through.
        target = "postgresql://user@db..example.com:5432/langflow"

        result = run_cli("--json", "--source", sqlite_source, "--target", target)

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        checking, error, report = _events(result)
        assert checking == CHECKING
        assert (error["event"], error["code"]) == ("error", "target_unreachable")
        assert report["problems"] == [{"code": "target_unreachable", "message": error["message"]}]

    def test_a_password_the_parser_took_for_the_port_is_not_printed(self, sqlite_source, run_cli):
        # With the host left out, what follows the user's colon is read as the port, and
        # the parser's error quotes it.
        secret = "SuperSecretPw123"  # noqa: S105  # pragma: allowlist secret

        result = run_cli("--source", sqlite_source, "--target", f"postgresql://postgres:{secret}/langflow")

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert "Problem: could not use the target database: the URL could not be read" in result.output
        assert secret not in result.output

    def test_json_stdout_of_a_child_process_holds_only_events(self, sqlite_source):
        # Run the way an admin UI runs it, with the logger at its noisiest and in the JSON
        # format containers use, whose lines would pass for events if they reached stdout.
        result = subprocess.run(  # noqa: S603 - the interpreter running the tests, fixed arguments
            [
                sys.executable,
                "-m",
                "langflow",
                "convert-sqlite-to-postgres",
                "--json",
                "--log-level",
                "debug",
                "--source",
                sqlite_source,
                "--target",
                self.UNREACHABLE_TARGET,
            ],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "LANGFLOW_LOG_ENV": "container"},
        )

        assert result.returncode == 1, result.stderr
        assert [json.loads(line)["event"] for line in result.stdout.splitlines()] == ["progress", "error", "report"]
        assert "Logger set up with log level" in result.stderr

    def test_urls_are_read_from_the_environment(self, sqlite_source, run_cli):
        # How a parent process passes them, so the target's password is never in argv.
        env = {"LANGFLOW_MIGRATION_SOURCE_URL": sqlite_source, "LANGFLOW_MIGRATION_TARGET_URL": self.UNREACHABLE_TARGET}

        result = run_cli("--json", env=env)

        assert result.exit_code == 1, result.output
        assert [problem["code"] for problem in _events(result)[-1]["problems"]] == ["target_unreachable"]

    def test_flags_win_over_the_environment(self, sqlite_source, tmp_path, run_cli):
        missing = f"sqlite:///{tmp_path / 'typo.db'}"
        env = {"LANGFLOW_MIGRATION_SOURCE_URL": sqlite_source, "LANGFLOW_MIGRATION_TARGET_URL": "postgresql://unused"}

        result = run_cli("--json", "--source", missing, "--target", self.UNREACHABLE_TARGET, env=env)

        assert [problem["code"] for problem in _events(result)[-1]["problems"]] == ["source_missing"]

    def test_help_names_the_environment_variables_and_never_shows_their_values(self, run_cli):
        secret = "SuperSecretPw123"  # noqa: S105  # pragma: allowlist secret
        env = {
            "LANGFLOW_MIGRATION_SOURCE_URL": "sqlite:////data/private-name.db",
            "LANGFLOW_MIGRATION_TARGET_URL": f"postgresql://postgres:{secret}@db/langflow",
        }

        result = run_cli("--help", env=env)

        assert result.exit_code == 0
        assert "LANGFLOW_MIGRATION_SOURCE_URL" in result.output
        assert "LANGFLOW_MIGRATION_TARGET_URL" in result.output
        assert secret not in result.output
        assert "private-name" not in result.output


# --------------------------------------------------------------------------
# End to end against a real Postgres server
# --------------------------------------------------------------------------


@pytest.fixture
def postgres_database():
    base_url = os.getenv("LANGFLOW_TEST_DATABASE_URI")
    if not base_url:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
    admin_url = sa.engine.make_url(base_url).set(drivername="postgresql+psycopg")
    name = f"lf_convert_{uuid.uuid4().hex[:10]}"
    admin = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    url = admin_url.set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def sqlite_source(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'langflow.db'}"
    upgrade_to_head(url)
    return url


SUPERUSER = uuid.UUID("11111111-1111-4111-8111-111111111111")
ALICE = uuid.UUID("22222222-2222-4222-8222-222222222222")
FLOW = uuid.UUID("33333333-3333-4333-8333-333333333333")
CUSTOM_ROLE = uuid.UUID("44444444-4444-4444-8444-444444444444")


def _seed(url: str) -> None:
    """Write through the ORM, the way a running Langflow would."""
    from langflow.services.database.models import Flow, User
    from langflow.services.database.models.auth.authz import AuthzRole, AuthzRoleAssignment
    from sqlmodel import Session, select

    engine = sa.create_engine(url)
    with Session(engine) as session:
        session.add(User(id=SUPERUSER, username="langflow", password="x", is_superuser=True, is_active=True))  # noqa: S106
        session.add(User(id=ALICE, username="alice", password="x", is_active=True))  # noqa: S106
        session.add(Flow(id=FLOW, name="main", data={"nodes": [1, 2]}, user_id=SUPERUSER, is_component=True))
        admin = session.exec(select(AuthzRole).where(AuthzRole.name == "admin")).one()
        session.add(AuthzRole(id=CUSTOM_ROLE, name="team-lead", is_system=False, parent_role_id=admin.id))
        session.add(AuthzRoleAssignment(user_id=ALICE, role_id=admin.id, domain_type="global"))
        session.add(AuthzRoleAssignment(user_id=ALICE, role_id=CUSTOM_ROLE, domain_type="global"))
        session.commit()
        session.exec(sa.text("UPDATE model_provider_policy SET approved_provider_ids='[\"openai\"]', version=7"))
        session.exec(sa.text("UPDATE sso_settings SET enforce_sso = 1"))
        session.commit()
    engine.dispose()


BOB = uuid.UUID("55555555-5555-4555-8555-555555555555")


def _leave_orphans(url: str) -> None:
    """Clear a flow's traces and delete a user the way Langflow did before 1.13.

    Langflow never turns on SQLite's foreign keys, so neither delete cascades:
    the spans and bob's role assignment stay behind. Deleting a user through the
    ORM removes their role assignments since 1.13 (#15124), but databases where a
    user was deleted earlier still hold them, so bob is deleted with plain SQL.
    """
    from langflow.services.database.models import User
    from langflow.services.database.models.auth.authz import (
        AuthzRole,
        AuthzRoleAssignment,
        AuthzRoleAssignmentGrant,
    )
    from langflow.services.database.models.traces.model import SpanTable, TraceTable
    from sqlmodel import Session, select

    engine = sa.create_engine(url)
    with Session(engine) as session:
        trace = TraceTable(name="run", flow_id=FLOW)
        root = SpanTable(name="root", trace_id=trace.id)
        session.add_all([trace, root, SpanTable(name="child", trace_id=trace.id, parent_span_id=root.id)])
        session.add(User(id=BOB, username="bob", password="x", is_active=True))  # noqa: S106
        viewer = session.exec(select(AuthzRole).where(AuthzRole.name == "viewer")).one()
        assignment = AuthzRoleAssignment(user_id=BOB, role_id=viewer.id, domain_type="global")
        session.add(assignment)
        session.add(AuthzRoleAssignmentGrant(assignment_id=assignment.id, source_kind="manual"))
        # bob granted alice her roles, so her assignments point at him too.
        for alices in session.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.user_id == ALICE)):
            alices.assigned_by = BOB
        session.commit()
        # The flow's "Clear all" traces button, and DELETE /users/{id} before 1.13.
        session.execute(sa.delete(TraceTable).where(TraceTable.flow_id == FLOW))
        session.execute(sa.delete(User).where(User.id == BOB))
        session.commit()
    engine.dispose()


def _counts(url: str, tables: list[str]) -> dict[str, int]:
    engine = sa.create_engine(url)
    with engine.connect() as conn:
        counts = {t: conn.execute(sa.text(f'SELECT count(*) FROM "{t}"')).scalar_one() for t in tables}  # noqa: S608
    engine.dispose()
    return counts


class TestConversionEndToEnd:
    def test_converts_and_the_orm_reads_the_result(self, sqlite_source, postgres_database):
        _seed(sqlite_source)

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert report.ok, report.problems
        tables = ["user", "flow", "authz_role", "authz_role_assignment", "model_provider_policy"]
        assert _counts(postgres_database, tables) == _counts(sqlite_source, tables)

        from langflow.services.database.models import Flow, User
        from langflow.services.database.models.auth.authz import AuthzRole, AuthzRoleAssignment
        from sqlmodel import Session, select

        engine = sa.create_engine(postgres_database)
        with Session(engine) as session:
            # A typed lookup by id is exactly what fails if ids land in the wrong form.
            assert session.get(User, SUPERUSER).username == "langflow"
            flow = session.get(Flow, FLOW)
            assert flow.is_component is True
            assert flow.data == {"nodes": [1, 2]}
            # System role ids were realigned, so assignments and the custom role's
            # parent all resolve to the right role by name.
            admin = session.exec(select(AuthzRole).where(AuthzRole.name == "admin")).one()
            assert session.get(AuthzRole, CUSTOM_ROLE).parent_role_id == admin.id
            role_names = {
                session.get(AuthzRole, a.role_id).name
                for a in session.exec(select(AuthzRoleAssignment).where(AuthzRoleAssignment.user_id == ALICE))
            }
            assert role_names == {"admin", "team-lead"}
            # Rows both sides seed carry the source's configuration, not the target's defaults.
            policy = session.exec(sa.text("SELECT approved_provider_ids, version FROM model_provider_policy")).one()
            assert (list(policy[0]), policy[1]) == (["openai"], 7)
            assert session.exec(sa.text("SELECT enforce_sso FROM sso_settings")).scalar_one() is True
        engine.dispose()

    def test_rerunning_is_idempotent(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        assert convert_sqlite_to_postgres(sqlite_source, postgres_database).ok

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert report.ok, report.problems
        assert _counts(postgres_database, ["user", "authz_role"]) == _counts(sqlite_source, ["user", "authz_role"])

    def test_a_self_referencing_table_is_copied_without_holding_it_in_memory(self, sqlite_source, postgres_database):
        # 40 MB of spans, each pointing at the span written after it. Ordering them
        # parents first in memory held the whole table, so the peak grew past its size.
        _seed(sqlite_source)
        trace_id = uuid.uuid4()
        spans = [uuid.uuid4() for _ in range(40)]
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO trace (id, name, status, start_time, total_latency_ms, total_tokens, flow_id) "
                    "VALUES (:id, 'run', 'ok', '2025-01-01 00:00:00', 0, 0, :flow_id)"
                ),
                {"id": trace_id.hex, "flow_id": FLOW.hex},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO span (id, trace_id, parent_span_id, name, span_type, status, start_time, latency_ms, "
                    "inputs, span_kind) VALUES (:id, :trace_id, :parent, 'llm', 'llm', 'ok', '2025-01-01 00:00:00', 0, "
                    ":inputs, 'INTERNAL')"
                ),
                [
                    {
                        "id": span.hex,
                        "trace_id": trace_id.hex,
                        "parent": parent.hex if parent else None,
                        "inputs": json.dumps({"text": "x" * 1_000_000}),
                    }
                    for span, parent in zip(spans, [*spans[1:], None], strict=True)
                ],
            )
        engine.dispose()
        # Migrating allocates on its own, so the target is migrated before measuring.
        upgrade_to_head(postgres_database)

        tracemalloc.start()
        try:
            report = convert_sqlite_to_postgres(sqlite_source, postgres_database, batch_size=1)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        assert report.ok, report.problems
        assert peak < 20_000_000
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            parents = dict(conn.execute(sa.text("SELECT id, parent_span_id FROM span")).all())
        engine.dispose()
        assert parents == dict(zip(spans, [*spans[1:], None], strict=True))

    def test_invalid_enum_value_is_refused_before_anything_is_written(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE flow SET flow_type = 'FLOW'"))
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert not report.ok
        # The problem names the row, so the operator can go straight to it.
        assert any("flow.flow_type" in p and "FLOW" in p and FLOW.hex in p for p in report.problems)
        assert [p.code for p in report.problems] == ["value_rejected"]
        # A refused run leaves the target exactly as it was: not even migrated.
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assert sa.inspect(conn).get_table_names() == []
        engine.dispose()

    def test_value_that_cannot_be_converted_is_reported_with_its_column(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE flow SET data = '{bad'"))
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert not report.ok
        assert any("flow.data" in p for p in report.problems), report.problems
        assert [p.code for p in report.problems] == ["value_rejected"]
        assert _counts(postgres_database, ["flow"]) == {"flow": 0}

    def test_a_value_postgres_rejects_during_the_copy_rolls_it_back(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            # Postgres text cannot hold a NUL byte; SQLite text can.
            conn.execute(sa.text("UPDATE flow SET name = 'a' || char(0) || 'b'"))
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert [p.code for p in report.problems] == ["copy_failed"]
        assert report.problems[0].startswith("copy failed and was rolled back: ")
        assert _counts(postgres_database, ["user", "flow"]) == {"user": 0, "flow": 0}

    def test_rows_the_source_no_longer_has_fail_the_count_and_roll_back(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        assert convert_sqlite_to_postgres(sqlite_source, postgres_database).ok
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM flow"))
            conn.execute(sa.text("UPDATE \"user\" SET username = 'renamed' WHERE username = 'alice'"))
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert list(report.problems) == ["flow: source has 0 rows, target has 1 after copy"]
        assert [p.code for p in report.problems] == ["count_mismatch"]
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT count(*) FROM \"user\" WHERE username = 'renamed'")).scalar_one() == 0
        engine.dispose()

    def test_an_error_reading_the_source_during_the_checks_names_the_source(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            # Still at the right revision, but a table the orphan check reads is gone.
            conn.execute(sa.text('DROP TABLE "user"'))
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert [p.code for p in report.problems] == ["source_unreadable"]
        assert report.problems[0].startswith("could not read the source database: ")
        assert "no such table: user" in report.problems[0]
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assert sa.inspect(conn).get_table_names() == []
        engine.dispose()

    def test_sql_null_in_json_columns_stays_sql_null(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE flow SET tags = NULL"))
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert report.ok, report.problems
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT count(*) FROM flow WHERE tags IS NULL")).scalar_one() == 1
        engine.dispose()

    def test_legacy_uppercase_trace_enums_are_carried_as_langflow_reads_them(self, sqlite_source, postgres_database):
        # Before 1.9.2 trace and span enums were stored by name, and the SQLite
        # rows were never rewritten. Langflow still reads them case-insensitively.
        _seed(sqlite_source)
        trace_id = uuid.uuid4()
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO trace (id, name, status, start_time, total_latency_ms, total_tokens, flow_id) "
                    "VALUES (:id, 'run', 'OK', '2025-01-01 00:00:00', 0, 0, :flow_id)"
                ),
                {"id": trace_id.hex, "flow_id": FLOW.hex},
            )
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert report.ok, report.problems
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            status = conn.execute(
                sa.text("SELECT status::text FROM trace WHERE id = :id"), {"id": trace_id}
            ).scalar_one()
        engine.dispose()
        assert status == "ok"

    def test_policy_history_that_does_not_start_at_revision_one_is_carried_verbatim(
        self, sqlite_source, postgres_database
    ):
        # The shared policy bundle migration seeds its first revision from
        # model_provider_policy.version, so an instance that changed its provider
        # policy before upgrading starts its history above 1. A fresh target seeds 1.
        _seed(sqlite_source)
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE policy_bundle_revision SET revision = 7"))
            conn.execute(sa.text("UPDATE policy_bundle_active SET revision = 7"))
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert report.ok, report.problems
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT revision FROM policy_bundle_revision")).scalars().all() == [7]
            assert conn.execute(sa.text("SELECT revision FROM policy_bundle_active")).scalar_one() == 7
        engine.dispose()

    def test_orphan_rows_are_refused_before_anything_is_written(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        _leave_orphans(sqlite_source)

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert not report.ok
        # Each key is named with its count. The grant's assignment still exists in
        # SQLite, but it goes with bob's assignment, so the grant is gone too.
        for named in [
            "span.trace_id: 2 row(s)",
            "authz_role_assignment.user_id: 1 row(s)",
            "authz_role_assignment_grant.assignment_id: 1 row(s)",
            "authz_role_assignment.assigned_by: 2 row(s)",
        ]:
            assert any(p.startswith(named) and "--drop-orphans" in p for p in report.problems), report.problems
        assert {p.code for p in report.problems} == {"orphans_droppable"}
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assert sa.inspect(conn).get_table_names() == []
        engine.dispose()

    def test_drop_orphans_copies_what_on_delete_would_have_left(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        _leave_orphans(sqlite_source)
        # A key written as a dashed string through raw SQL still points at its row.
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO trace (id, name, status, start_time, total_latency_ms, total_tokens, flow_id) "
                    "VALUES (:id, 'kept', 'ok', '2025-01-01 00:00:00', 0, 0, :flow_id)"
                ),
                {"id": uuid.uuid4().hex, "flow_id": str(FLOW)},
            )
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database, drop_orphans=True)

        assert report.ok, report.problems
        assert {(o.table, o.column, o.ondelete, o.rows) for o in report.orphans} == {
            ("span", "trace_id", "CASCADE", 2),
            ("authz_role_assignment", "user_id", "CASCADE", 1),
            ("authz_role_assignment_grant", "assignment_id", "CASCADE", 1),
            ("authz_role_assignment", "assigned_by", "SET NULL", 2),
        }
        source = _counts(sqlite_source, ["user", "flow", "trace", "span", "authz_role_assignment"])
        assert _counts(postgres_database, list(source)) == {
            **source,
            "span": 0,
            "authz_role_assignment": source["authz_role_assignment"] - 1,
        }
        assert _counts(postgres_database, ["authz_role_assignment_grant"]) == {"authz_role_assignment_grant": 0}
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assigned_by = conn.execute(sa.text("SELECT assigned_by FROM authz_role_assignment")).scalars().all()
        engine.dispose()
        assert assigned_by == [None, None]

    def test_target_holding_another_instances_users_is_refused(self, sqlite_source, postgres_database, tmp_path):
        _seed(sqlite_source)
        other = f"sqlite:///{tmp_path / 'other.db'}"
        upgrade_to_head(other)
        engine = sa.create_engine(other)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    'INSERT INTO "user" (id, username, password, is_active, is_superuser, create_at, updated_at) '
                    "VALUES ('99999999999949998999999999999999', 'mallory', 'x', 1, 0, '2026-01-01', '2026-01-01')"
                )
            )
        engine.dispose()
        assert convert_sqlite_to_postgres(other, postgres_database).ok

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert not report.ok
        assert any("another instance" in p for p in report.problems)
        assert [p.code for p in report.problems] == ["target_not_empty"]


ORPHANS = {
    ("span", "trace_id", "trace", "CASCADE", 2),
    ("authz_role_assignment", "user_id", "user", "CASCADE", 1),
    ("authz_role_assignment_grant", "assignment_id", "authz_role_assignment", "CASCADE", 1),
    ("authz_role_assignment", "assigned_by", "user", "SET NULL", 2),
}


def _orphan_tuples(orphans: list[dict]) -> set[tuple]:
    return {(o["table"], o["column"], o["parent"], o["ondelete"], o["rows"]) for o in orphans}


class TestCommandOutput:
    def test_text_output_is_one_line_per_table_then_the_summary(self, sqlite_source, postgres_database, run_cli):
        _seed(sqlite_source)

        result = run_cli("--source", sqlite_source, "--target", postgres_database)

        assert result.exit_code == 0, result.output
        engine = sa.create_engine(postgres_database)
        metadata = sa.MetaData()
        metadata.reflect(bind=engine)
        with engine.connect() as conn:
            revision = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        engine.dispose()
        names = [table.name for table in copy_order(metadata)]
        counts = _counts(postgres_database, names)
        assert counts["user"] == 2
        assert result.stdout == (
            "".join(f"{name}: {counts[name]} row(s)\n" for name in names)
            + f"Converted {len(names)} table(s) at revision {revision}.\n"
        )

    def test_json_streams_progress_and_each_table_then_the_report(self, sqlite_source, postgres_database, run_cli):
        _seed(sqlite_source)

        result = run_cli("--json", "--source", sqlite_source, "--target", postgres_database, "--batch-size", "1")

        assert result.exit_code == 0, result.output
        *events, report = _events(result)
        assert {event["event"] for event in events} == {"progress", "item"}
        items = [event["item"] for event in events if event["event"] == "item"]
        progress = [event for event in events if event["event"] == "progress"]

        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            copied = sorted(set(sa.inspect(conn).get_table_names()) - {"alembic_version"})
            revision = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        engine.dispose()
        # One item per table, holding the counts the target ends up with.
        assert sorted(item["table"] for item in items) == copied
        assert {item["table"]: item["target_rows"] for item in items} == _counts(postgres_database, copied)
        assert all(item["source_rows"] == item["target_rows"] for item in items)

        # The source checks and the target's migrations are announced before the first table.
        assert events[:2] == [CHECKING, PREPARING_TARGET]
        copying = progress[2:]
        rows = sum(item["source_rows"] for item in items)
        done = [event["done"] for event in copying]
        assert done == sorted(done)
        assert done[-1] == rows
        assert all(
            event["phase"] == "copying" and event["total"] == rows and event["unit"] == "rows" for event in copying
        )
        # Every table reports, empty ones included, and a table larger than a batch reports per batch.
        assert {event["subject"] for event in copying} == set(copied)
        user = [event["done"] for event in copying if event["subject"] == "user"]
        assert [count - user[0] for count in user] == [0, 1, 2]

        assert report == {
            "event": "report",
            "ok": True,
            "revision": revision,
            "tables_copied": len(copied),
            "rows_copied": rows,
            "orphans": [],
            "problems": [],
        }

    def test_json_asks_for_a_decision_when_only_droppable_orphans_are_refused(
        self, sqlite_source, postgres_database, run_cli
    ):
        _seed(sqlite_source)
        _leave_orphans(sqlite_source)

        result = run_cli("--json", "--source", sqlite_source, "--target", postgres_database)

        assert result.exit_code == 1
        checking, decision, report = _events(result)
        assert checking == CHECKING
        assert (decision["event"], decision["code"], decision["flag"]) == (
            "decision_needed",
            "orphans_droppable",
            "--drop-orphans",
        )
        assert decision["message"]
        assert _orphan_tuples(decision["details"]["orphans"]) == ORPHANS
        assert report["ok"] is False
        assert [problem["code"] for problem in report["problems"]] == ["orphans_droppable"] * len(ORPHANS)
        assert (report["tables_copied"], report["rows_copied"], report["orphans"]) == (0, 0, [])
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assert sa.inspect(conn).get_table_names() == []
        engine.dispose()

    def test_target_at_a_revision_this_langflow_does_not_know_is_refused(
        self, sqlite_source, postgres_database, run_cli
    ):
        _seed(sqlite_source)
        engine = sa.create_engine(postgres_database)
        with engine.begin() as conn:
            # What a newer Langflow leaves behind: a revision this one has no migration for.
            conn.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            conn.execute(sa.text("INSERT INTO alembic_version VALUES ('ffffffffffff')"))
        engine.dispose()

        result = run_cli("--json", "--source", sqlite_source, "--target", postgres_database)

        assert result.exit_code == 1
        # Alembic's own error escaping would leave a program reading --json without its report line.
        assert isinstance(result.exception, SystemExit)
        events = _events(result)
        error, report = events[-2:]
        assert events[:-2] == [CHECKING, PREPARING_TARGET]
        assert error["code"] == "target_not_empty"
        assert error["message"].startswith("target database is at revision ffffffffffff")
        assert "another Langflow version" in error["message"]
        assert "convert into an empty database" in error["message"]
        assert report["problems"] == [{"code": "target_not_empty", "message": error["message"]}]

        text = run_cli("--source", sqlite_source, "--target", postgres_database)

        assert text.exit_code == 1
        assert isinstance(text.exception, SystemExit)
        assert text.stdout == ""
        assert text.stderr == f"Problem: {error['message']}\n"
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assert sa.inspect(conn).get_table_names() == ["alembic_version"]
        engine.dispose()

    def test_json_report_records_the_orphans_that_were_dropped(self, sqlite_source, postgres_database, run_cli):
        _seed(sqlite_source)
        _leave_orphans(sqlite_source)

        result = run_cli("--json", "--drop-orphans", "--source", sqlite_source, "--target", postgres_database)

        assert result.exit_code == 0, result.output
        *events, report = _events(result)
        assert report["ok"] is True
        assert _orphan_tuples(report["orphans"]) == ORPHANS
        # The total leaves out the rows that were dropped, so the copy still reaches it.
        last = [event for event in events if event["event"] == "progress"][-1]
        assert last["done"] == last["total"] == report["rows_copied"]

    def test_json_reports_orphans_no_rule_covers_as_errors(self, sqlite_source, postgres_database, run_cli):
        _seed(sqlite_source)
        _leave_orphans(sqlite_source)
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            # flow.user_id has no ON DELETE rule, so --drop-orphans cannot settle it.
            conn.execute(sa.text("UPDATE flow SET user_id = :gone"), {"gone": uuid.uuid4().hex})
        engine.dispose()

        result = run_cli("--json", "--source", sqlite_source, "--target", postgres_database)

        assert result.exit_code == 1
        _, *errors, report = _events(result)
        # Rerunning with --drop-orphans would not be enough, so no decision is offered.
        assert {event["event"] for event in errors} == {"error"}
        codes = [event["code"] for event in errors]
        assert sorted(codes) == ["orphans_droppable"] * len(ORPHANS) + ["orphans_no_rule"]
        no_rule = errors[codes.index("orphans_no_rule")]
        assert no_rule["message"].startswith("flow.user_id: 1 row(s) point at user rows that are gone")
        assert report["problems"] == [{"code": event["code"], "message": event["message"]} for event in errors]
        engine = sa.create_engine(postgres_database)
        with engine.connect() as conn:
            assert sa.inspect(conn).get_table_names() == []
        engine.dispose()
