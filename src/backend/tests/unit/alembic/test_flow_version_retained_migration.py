import uuid

from alembic import command
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "d4f1a6c8e2b7"  # pragma: allowlist secret -- migration revision identifier
_REVISION = "e5a7c9b1d3f2"  # pragma: allowlist secret -- migration revision identifier


def test_retained_columns_added_and_removed(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PRIOR_REVISION)
    engine = create_engine(_engine_url(db_url))
    sqlite = engine.dialect.name == "sqlite"
    try:
        if sqlite:
            # A version that predates the column. SQLite doesn't enforce the flow
            # foreign key here, so no user or flow is needed to hold the row.
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO flow_version (id, flow_id, version_number, created_at) "
                        "VALUES (:id, :flow_id, 1, CURRENT_TIMESTAMP)"
                    ),
                    {"id": uuid.uuid4().hex, "flow_id": uuid.uuid4().hex},
                )
        command.upgrade(config, _REVISION)
        with engine.connect() as connection:
            columns = {c["name"]: c for c in inspect(connection).get_columns("flow_version")}
            assert columns["retained"]["nullable"] is False
            assert columns["retained_reason"]["nullable"] is True
            if sqlite:
                # The existing row reads as not retained, which the prune filter relies on.
                rows = connection.execute(text("SELECT retained, retained_reason FROM flow_version")).all()
                assert [(bool(retained), reason) for retained, reason in rows] == [(False, None)]

        command.downgrade(config, _PRIOR_REVISION)
        with engine.connect() as connection:
            names = {c["name"] for c in inspect(connection).get_columns("flow_version")}
            assert not names & {"retained", "retained_reason"}
    finally:
        engine.dispose()
