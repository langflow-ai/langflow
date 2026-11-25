"""The flow description is free text and must not carry a B-tree index.

PostgreSQL rejects a B-tree entry above roughly a third of a page, so an index
on ``flow.description`` turned a valid long description into an HTTP 500.
Runs on SQLite and, when ``LANGFLOW_TEST_DATABASE_URI`` is set, PostgreSQL.
"""

from __future__ import annotations

import base64
import random
from uuid import uuid4

import pytest
from alembic import command
from langflow.services.database.models.flow.model import Flow
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PREVIOUS_REVISION = "a09a699afb52"  # pragma: allowlist secret
_REVISION = "5cddf0859de4"  # pragma: allowlist secret


def _poorly_compressible_description() -> str:
    """Seeded random bytes as base64: about 6,000 ASCII characters that do not compress."""
    return base64.b64encode(random.Random(16412).randbytes(4500)).decode("ascii")  # noqa: S311


def _multibyte_description() -> str:
    """Seeded CJK and emoji text: 1,500 characters, over 4,500 UTF-8 bytes."""
    rng = random.Random(412)  # noqa: S311
    return "".join(chr(rng.choice((rng.randint(0x4E00, 0x9FFF), rng.randint(0x1F300, 0x1F5FF)))) for _ in range(1500))


def _description_indexes(connection) -> list[str]:
    return [
        index["name"] for index in inspect(connection).get_indexes("flow") if index["column_names"] == ["description"]
    ]


def _insert_flow(connection, description: str) -> str:
    user_id = str(uuid4())
    flow_id = str(uuid4())
    connection.execute(
        text(
            'INSERT INTO "user" (id, username, password, is_active, is_superuser, create_at, updated_at) '
            "VALUES (:id, :username, 'x', true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"id": user_id, "username": f"description-owner-{user_id}"},
    )
    connection.execute(
        text("INSERT INTO flow (id, name, user_id, description) VALUES (:id, :name, :user_id, :description)"),
        {"id": flow_id, "name": f"flow-{flow_id}", "user_id": user_id, "description": description},
    )
    return flow_id


def _read_description(connection, flow_id: str) -> str | None:
    return connection.execute(text("SELECT description FROM flow WHERE id = :id"), {"id": flow_id}).scalar_one()


def test_flow_model_does_not_index_description():
    assert not Flow.__table__.c.description.index
    assert all(list(index.columns.keys()) != ["description"] for index in Flow.__table__.indexes)


def test_upgrade_drops_description_index(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PREVIOUS_REVISION)
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            assert _description_indexes(connection) == ["ix_flow_description"]

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert _description_indexes(connection) == []
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "description_factory",
    [_poorly_compressible_description, _multibyte_description],
    ids=["poorly-compressible", "multibyte"],
)
def test_long_descriptions_create_update_and_read_at_head(db_url, description_factory):  # noqa: F811
    description = description_factory()
    updated = description[::-1]
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, "head")
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            flow_id = _insert_flow(connection, description)
        with engine.begin() as connection:
            assert _read_description(connection, flow_id) == description
            connection.execute(
                text("UPDATE flow SET description = :description WHERE id = :id"),
                {"id": flow_id, "description": updated},
            )
        with engine.connect() as connection:
            assert _read_description(connection, flow_id) == updated
    finally:
        engine.dispose()


def test_upgrade_keeps_existing_descriptions_and_downgrade_restores_index(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PREVIOUS_REVISION)
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            flow_id = _insert_flow(connection, "A short description that fits the index")

        command.upgrade(config, _REVISION)
        command.downgrade(config, _PREVIOUS_REVISION)

        with engine.connect() as connection:
            assert _description_indexes(connection) == ["ix_flow_description"]
            assert _read_description(connection, flow_id) == "A short description that fits the index"
    finally:
        engine.dispose()


def test_postgres_downgrade_with_oversized_description_fails_without_data_loss(db_url):  # noqa: F811
    if not db_url.startswith("postgresql"):
        pytest.skip("Only PostgreSQL limits the size of a B-tree index entry")
    description = _poorly_compressible_description()
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _REVISION)
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            flow_id = _insert_flow(connection, description)

        with pytest.raises(DBAPIError, match="index row size"):
            command.downgrade(config, _PREVIOUS_REVISION)

        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == _REVISION
            assert _description_indexes(connection) == []
            assert _read_description(connection, flow_id) == description
    finally:
        engine.dispose()
