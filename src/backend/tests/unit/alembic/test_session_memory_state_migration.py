from alembic import command
from sqlalchemy import create_engine, inspect

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "a09a699afb52"  # pragma: allowlist secret -- migration revision identifier
_REVISION = "9b9248669aad"  # pragma: allowlist secret -- migration revision identifier


def test_session_memory_state_upgrade_downgrade_upgrade(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PRIOR_REVISION)
    engine = create_engine(_engine_url(db_url))
    try:
        assert "session_memory_state" not in inspect(engine).get_table_names()

        command.upgrade(config, _REVISION)
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert "session_memory_state" in inspector.get_table_names()
            columns = {c["name"] for c in inspector.get_columns("session_memory_state")}
            assert {"summary", "cursor_message_id", "cursor_timestamp", "version"} <= columns
            uniques = {u["name"]: u["column_names"] for u in inspector.get_unique_constraints("session_memory_state")}
            assert uniques["uq_session_memory_state_scope"] == ["flow_id", "user_id", "session_id", "context_id"]
            indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("session_memory_state")}
            assert indexes["ix_session_memory_state_flow_session"] == ["flow_id", "session_id"]

        command.downgrade(config, _PRIOR_REVISION)
        with engine.connect() as connection:
            assert "session_memory_state" not in inspect(connection).get_table_names()

        command.upgrade(config, _REVISION)
        with engine.connect() as connection:
            assert "session_memory_state" in inspect(connection).get_table_names()
    finally:
        engine.dispose()
