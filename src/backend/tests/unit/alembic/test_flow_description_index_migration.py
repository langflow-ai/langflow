"""Tests for removing the flow description index (issue #16412)."""

import importlib.util
import os
import random
import string
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = (
    Path(__file__).parents[3] / "base/langflow/alembic/versions/8094acf12f99_remove_flow_description_index.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("remove_flow_description_index", _MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _flow_table(metadata: sa.MetaData) -> sa.Table:
    table = sa.Table(
        "flow",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    sa.Index("ix_flow_description", table.c.description, unique=False)
    return table


def _generate_poorly_compressible_text(min_length: int = 4000) -> str:
    """Generate deterministic, high-entropy text that resists TOAST/compression algorithms."""
    rng = random.Random(42)  # noqa: S311
    chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;':,./<>?~`"
    tokens = []
    current_len = 0
    while current_len < min_length:
        token = "".join(rng.choices(chars, k=32))
        tokens.append(token)
        current_len += len(token) + 1
    return "-".join(tokens)


def _get_test_engine():
    """Return a PostgreSQL engine if configured via environment, otherwise in-memory SQLite."""
    pg_url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if pg_url:
        if pg_url.startswith("postgresql://"):
            pg_url = pg_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return sa.create_engine(pg_url)
    return sa.create_engine("sqlite://")


def test_upgrade_drops_index_and_supports_deterministic_poorly_compressible_text():
    """Verify upgrade drops ix_flow_description and supports long, poorly compressible descriptions."""
    migration = _load_migration()
    engine = _get_test_engine()
    is_postgres = engine.dialect.name == "postgresql"

    with engine.begin() as connection:
        metadata = sa.MetaData()
        flow = _flow_table(metadata)
        flow.create(connection)

        indexes_before = {idx["name"] for idx in sa.inspect(connection).get_indexes("flow")}
        assert "ix_flow_description" in indexes_before

        large_description = _generate_poorly_compressible_text(min_length=4200)
        assert len(large_description) >= 4000

        # On PostgreSQL with the index present, the uncompressible text should fail the 1/3 page limit
        if is_postgres:
            with pytest.raises(sa.exc.DBAPIError) as exc_info, connection.begin_nested():
                connection.execute(
                    flow.insert().values(
                        id=str(uuid4()),
                        name="Pre-Migration Oversized Flow",
                        description=large_description,
                    )
                )
            assert "exceeds" in str(exc_info.value).lower() or "54000" in str(exc_info.value)

        # Run migration upgrade
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()

        # Idempotent - running upgrade again succeeds cleanly
        migration.upgrade()

        indexes_after = {idx["name"] for idx in sa.inspect(connection).get_indexes("flow")}
        assert "ix_flow_description" not in indexes_after

        # Now the large description insert must succeed
        flow_id = str(uuid4())
        connection.execute(
            flow.insert().values(
                id=flow_id,
                name="Large Description Flow",
                description=large_description,
            )
        )

        row = connection.execute(sa.select(flow).where(flow.c.id == flow_id)).one()
        assert row.description == large_description

        # Update with another deterministic large description
        updated_description = "updated-" + _generate_poorly_compressible_text(min_length=4500)
        assert len(updated_description) >= 4000
        connection.execute(flow.update().where(flow.c.id == flow_id).values(description=updated_description))

        updated_row = connection.execute(sa.select(flow).where(flow.c.id == flow_id)).one()
        assert updated_row.description == updated_description

        # On PostgreSQL, recreating the index when oversized rows exist must fail
        # without truncating or corrupting existing user data
        if is_postgres:
            with pytest.raises(sa.exc.DBAPIError), connection.begin_nested():
                migration.downgrade()
            preserved_row = connection.execute(sa.select(flow).where(flow.c.id == flow_id)).one()
            assert preserved_row.description == updated_description
    engine.dispose()


def test_upgrade_with_existing_flows_preserves_data():
    """Verify upgrade with existing flows retains all rows and descriptions unchanged."""
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        metadata = sa.MetaData()
        flow = _flow_table(metadata)
        flow.create(connection)

        id1 = str(uuid4())
        id2 = str(uuid4())
        id3 = str(uuid4())

        connection.execute(
            flow.insert(),
            [
                {"id": id1, "name": "Flow 1", "description": "Short description"},
                {"id": id2, "name": "Flow 2", "description": None},
                {"id": id3, "name": "Flow 3", "description": "Markdown with *styling* and `code`"},
            ],
        )

        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()

        rows = {row.id: (row.name, row.description) for row in connection.execute(sa.select(flow)).all()}
        assert rows[id1] == ("Flow 1", "Short description")
        assert rows[id2] == ("Flow 2", None)
        assert rows[id3] == ("Flow 3", "Markdown with *styling* and `code`")
    engine.dispose()


def test_downgrade_with_indexable_descriptions_restores_index():
    """Verify downgrade with standard indexable descriptions successfully restores ix_flow_description."""
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        metadata = sa.MetaData()
        flow = _flow_table(metadata)
        flow.create(connection)

        flow_id = str(uuid4())
        connection.execute(
            flow.insert().values(
                id=flow_id,
                name="Indexable Flow",
                description="Standard description well within index limits",
            )
        )

        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert "ix_flow_description" not in {idx["name"] for idx in sa.inspect(connection).get_indexes("flow")}

        migration.downgrade()
        assert "ix_flow_description" in {idx["name"] for idx in sa.inspect(connection).get_indexes("flow")}

        row = connection.execute(sa.select(flow).where(flow.c.id == flow_id)).one()
        assert row.description == "Standard description well within index limits"
    engine.dispose()


def test_flow_model_no_longer_indexes_description():
    """Verify FlowBase / Flow model metadata does not register an index on description."""
    from langflow.services.database.models.flow.model import Flow, FlowBase

    desc_field = FlowBase.model_fields["description"]
    assert desc_field is not None

    table_indexes = {idx.name for idx in Flow.__table__.indexes}
    assert "ix_flow_description" not in table_indexes

    desc_col = Flow.__table__.c.description
    assert not desc_col.index


def test_flow_model_large_description_roundtrip():
    """Verify Flow SQLModel instance accepts and preserves >4,000 char descriptions."""
    from langflow.services.database.models.flow.model import Flow

    large_description = _generate_poorly_compressible_text(min_length=4200)
    flow = Flow(
        id=uuid4(),
        name="SQLModel Large Description Test",
        description=large_description,
    )
    assert flow.description == large_description
    assert len(flow.description) >= 4000
