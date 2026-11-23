from alembic import command
from sqlalchemy import create_engine, inspect

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "e5a7c9b1d3f2"  # pragma: allowlist secret -- migration revision identifier
_REVISION = "f1b3d5a7c9e2"  # pragma: allowlist secret -- migration revision identifier


def test_session_memory_state_table_added_and_removed(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PRIOR_REVISION)
    engine = create_engine(_engine_url(db_url))
    try:
        assert "session_memory_state" not in inspect(engine).get_table_names()

        command.upgrade(config, _REVISION)
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert "session_memory_state" in inspector.get_table_names()
            uniques = {u["name"]: u["column_names"] for u in inspector.get_unique_constraints("session_memory_state")}
            assert uniques["uq_session_memory_state_scope"] == ["flow_id", "user_id", "session_id", "context_id"]
            indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("session_memory_state")}
            assert indexes["ix_session_memory_state_flow_session"] == ["flow_id", "session_id"]

        command.downgrade(config, _PRIOR_REVISION)
        with engine.connect() as connection:
            assert "session_memory_state" not in inspect(connection).get_table_names()
    finally:
        engine.dispose()
