"""Tests for converting a Langflow SQLite database to Postgres.

The coercion and ordering tests need no database. The end-to-end tests build a
real SQLite instance with alembic, convert it into a fresh Postgres database and
read the result back. They are opt-in: set
``LANGFLOW_RUN_POSTGRES_CONVERSION_TESTS=1`` and ``LANGFLOW_TEST_POSTGRES_ADMIN_URL``
to a server URL the tests can create databases on.
"""

from __future__ import annotations

import os
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


# --------------------------------------------------------------------------
# End to end against a real Postgres server
# --------------------------------------------------------------------------


@pytest.fixture
def postgres_database():
    admin_url = os.getenv("LANGFLOW_TEST_POSTGRES_ADMIN_URL")
    if os.getenv("LANGFLOW_RUN_POSTGRES_CONVERSION_TESTS") != "1" or not admin_url:
        pytest.skip("Set LANGFLOW_RUN_POSTGRES_CONVERSION_TESTS=1 and LANGFLOW_TEST_POSTGRES_ADMIN_URL")
    name = f"lf_convert_{uuid.uuid4().hex[:10]}"
    admin = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    url = sa.engine.make_url(admin_url).set(database=name).render_as_string(hide_password=False)
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


def _counts(url: str, tables: list[str]) -> dict[str, int]:
    engine = sa.create_engine(url)
    with engine.connect() as conn:
        counts = {t: conn.execute(sa.text(f'SELECT count(*) FROM "{t}"')).scalar_one() for t in tables}  # noqa: S608
    engine.dispose()
    return counts


@pytest.mark.api_key_required
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

    def test_invalid_enum_value_is_refused_before_anything_is_written(self, sqlite_source, postgres_database):
        _seed(sqlite_source)
        engine = sa.create_engine(sqlite_source)
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE flow SET flow_type = 'FLOW'"))
        engine.dispose()

        report = convert_sqlite_to_postgres(sqlite_source, postgres_database)

        assert not report.ok
        assert any("flow.flow_type" in p and "FLOW" in p for p in report.problems)
        assert _counts(postgres_database, ["user"]) == {"user": 0}

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
