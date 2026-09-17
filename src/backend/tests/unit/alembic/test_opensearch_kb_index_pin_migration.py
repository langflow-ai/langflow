"""Tests for pinning existing OpenSearch knowledge bases before owner-scoped indexes."""

from __future__ import annotations

import importlib
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from lfx.base.knowledge_bases.backends import opensearch as opensearch_backend

_MIGRATION = importlib.import_module("langflow.alembic.versions.386662af02e9_pin_legacy_opensearch_kb_indexes")

_METADATA = sa.MetaData()
_KNOWLEDGE_BASE = sa.Table(
    "knowledge_base",
    _METADATA,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), nullable=False),
    sa.Column("name", sa.String(), nullable=False),
    sa.Column("backend_type", sa.String(), nullable=False),
    sa.Column("backend_config", sa.JSON(), nullable=False),
)


@pytest.fixture
def connection(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    _METADATA.create_all(engine)
    with engine.begin() as conn:
        monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(conn)))
        yield conn


def _add(conn: sa.Connection, owner: UUID, name: str, config: dict, backend_type: str = "opensearch") -> UUID:
    row_id = uuid4()
    conn.execute(
        _KNOWLEDGE_BASE.insert().values(
            id=row_id, user_id=owner, name=name, backend_type=backend_type, backend_config=config
        )
    )
    return row_id


def _configs(conn: sa.Connection) -> dict[UUID, dict]:
    rows = conn.execute(sa.select(_KNOWLEDGE_BASE.c.id, _KNOWLEDGE_BASE.c.backend_config)).mappings()
    return {row["id"]: row["backend_config"] for row in rows}


@pytest.mark.parametrize(
    ("kb_name", "expected"),
    [
        ("chat_memory_a1b2c3d4", "chat_memory_a1b2c3d4"),
        ("My-KB!", "my-kb_"),
        ("  Docs 2024  ", "docs_2024"),
        ("_leading", "leading"),
        ("", "kb"),
        ("..", "kb"),
    ],
)
def test_legacy_index_name_matches_pre_scoping_backend(kb_name: str, expected: str) -> None:
    # The table the backend's ``derive_index_name(kb_name)`` was pinned to
    # before owner scoping; existing indexes on clusters carry these names.
    assert _MIGRATION.legacy_index_name(kb_name) == expected


def test_frozen_naming_matches_the_backend() -> None:
    owner = uuid4()
    assert _MIGRATION.owner_scoped_index_name(owner, "Team Docs") == opensearch_backend.derive_index_name(
        "Team Docs", owner
    )
    assert _MIGRATION.INDEX_NAME_ORIGIN_KEY == opensearch_backend.INDEX_NAME_ORIGIN_KEY
    assert _MIGRATION.LEGACY_KB_NAME_ORIGIN == opensearch_backend.LEGACY_KB_NAME_ORIGIN
    assert _MIGRATION.LEGACY_SHARED_INDEX_KEY == opensearch_backend.LEGACY_SHARED_INDEX_KEY


def test_single_owner_legacy_index_is_pinned(connection) -> None:
    owner = uuid4()
    row = _add(connection, owner, "My KB", {"url_variable": "OPENSEARCH_URL", "index_name": ""})

    _MIGRATION.upgrade()

    assert _configs(connection)[row] == {
        "url_variable": "OPENSEARCH_URL",
        "index_name": "my_kb",
        "index_name_origin": "legacy_kb_name",
    }


def test_legacy_index_shared_by_two_owners_is_not_pinned(connection, caplog) -> None:
    alice = _add(connection, uuid4(), "docs", {"url_variable": "OPENSEARCH_URL"})
    bob = _add(connection, uuid4(), "docs", {})
    # Names that sanitized to the same index collide as well.
    carol = _add(connection, uuid4(), "Reports", {})
    dave = _add(connection, uuid4(), "reports", {})

    _MIGRATION.upgrade()

    configs = _configs(connection)
    assert configs[alice] == {"url_variable": "OPENSEARCH_URL", "legacy_shared_index": "docs"}
    assert configs[bob] == {"legacy_shared_index": "docs"}
    assert configs[carol] == {"legacy_shared_index": "reports"}
    assert configs[dave] == {"legacy_shared_index": "reports"}
    assert "shares OpenSearch index docs" in caplog.text


def test_one_owners_colliding_names_are_pinned_together(connection) -> None:
    owner = uuid4()
    upper = _add(connection, owner, "Docs", {})
    lower = _add(connection, owner, "docs", {})

    _MIGRATION.upgrade()

    configs = _configs(connection)
    assert configs[upper]["index_name"] == "docs"
    assert configs[lower]["index_name"] == "docs"


def test_explicit_override_on_another_owners_kb_counts_as_sharing(connection) -> None:
    derived = _add(connection, uuid4(), "docs", {})
    explicit = _add(connection, uuid4(), "anything", {"index_name": "docs"})

    _MIGRATION.upgrade()

    configs = _configs(connection)
    assert configs[derived] == {"legacy_shared_index": "docs"}
    assert configs[explicit] == {"index_name": "docs"}


def test_other_backends_are_ignored(connection) -> None:
    opensearch_row = _add(connection, uuid4(), "docs", {})
    chroma_row = _add(connection, uuid4(), "docs", {"mode": "local"}, backend_type="chroma")

    _MIGRATION.upgrade()

    configs = _configs(connection)
    assert configs[opensearch_row]["index_name"] == "docs"
    assert configs[chroma_row] == {"mode": "local"}


def test_downgrade_pins_owner_scoped_rows_and_upgrade_is_then_a_no_op(connection) -> None:
    owner = uuid4()
    scoped = _add(connection, owner, "created after upgrade", {})
    legacy = _add(connection, owner, "legacy", {"index_name": "legacy", "index_name_origin": "legacy_kb_name"})
    shared = _add(connection, owner, "docs", {"legacy_shared_index": "docs"})

    _MIGRATION.downgrade()

    configs = _configs(connection)
    assert configs[scoped] == {
        "index_name": _MIGRATION.owner_scoped_index_name(owner, "created after upgrade"),
        "index_name_origin": "owner_scoped",
    }
    assert configs[legacy] == {"index_name": "legacy", "index_name_origin": "legacy_kb_name"}
    assert configs[shared]["index_name"] == _MIGRATION.owner_scoped_index_name(owner, "docs")

    _MIGRATION.upgrade()

    assert _configs(connection) == configs


def test_missing_table_is_a_no_op(monkeypatch) -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(conn)))
        _MIGRATION.upgrade()
        _MIGRATION.downgrade()
