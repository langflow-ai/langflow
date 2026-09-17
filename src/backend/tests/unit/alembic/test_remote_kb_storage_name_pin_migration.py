"""Tests for pinning OpenSearch and Chroma Cloud knowledge bases before owner-scoped storage names."""

from __future__ import annotations

import importlib
import logging
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from lfx.base.knowledge_bases.backends import chroma as chroma_backend
from lfx.base.knowledge_bases.backends import opensearch as opensearch_backend

_MIGRATION = importlib.import_module("langflow.alembic.versions.386662af02e9_pin_legacy_remote_kb_storage_names")

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

_CLOUD = {"mode": "cloud", "api_key_variable": "CHROMA_API_KEY"}  # pragma: allowlist secret


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


def test_legacy_collection_name_is_the_kb_name() -> None:
    assert _MIGRATION.legacy_collection_name("My.KB-2024") == "My.KB-2024"


def test_frozen_naming_matches_the_backends() -> None:
    owner = uuid4()
    scoped = _MIGRATION.owner_scoped_name(owner, "Team Docs")
    assert scoped == opensearch_backend.derive_index_name("Team Docs", owner)
    cloud = chroma_backend.ChromaCloudBackend(kb_name="Team Docs", backend_config=dict(_CLOUD), user_id=owner)
    assert scoped == cloud._resolve_collection_name()

    assert _MIGRATION.OPENSEARCH.name_key == "index_name"
    assert _MIGRATION.OPENSEARCH.origin_key == opensearch_backend.INDEX_NAME_ORIGIN_KEY
    assert _MIGRATION.OPENSEARCH.shared_key == opensearch_backend.LEGACY_SHARED_INDEX_KEY
    assert _MIGRATION.LEGACY_KB_NAME_ORIGIN == opensearch_backend.LEGACY_KB_NAME_ORIGIN
    assert _MIGRATION.CHROMA_CLOUD.name_key == chroma_backend.COLLECTION_NAME_KEY
    assert _MIGRATION.CHROMA_CLOUD.origin_key == chroma_backend.COLLECTION_NAME_ORIGIN_KEY
    assert _MIGRATION.CHROMA_CLOUD.shared_key == chroma_backend.LEGACY_SHARED_COLLECTION_KEY


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

    with caplog.at_level(logging.WARNING):
        _MIGRATION.upgrade()

    configs = _configs(connection)
    assert configs[alice] == {"url_variable": "OPENSEARCH_URL", "legacy_shared_index": "docs"}
    assert configs[bob] == {"legacy_shared_index": "docs"}
    assert configs[carol] == {"legacy_shared_index": "reports"}
    assert configs[dave] == {"legacy_shared_index": "reports"}
    assert "used OpenSearch index docs, but shares it with other users' knowledge bases" in caplog.text


@pytest.mark.parametrize(
    ("backend_type", "config", "kb_name", "shared_key"),
    [
        ("opensearch", {}, "LF_0123456789ABCDEF01234567", "legacy_shared_index"),
        ("chroma", dict(_CLOUD), "lf_0123456789abcdef01234567", "legacy_shared_collection"),
    ],
)
def test_legacy_name_shaped_like_an_owner_scoped_name_is_not_pinned(
    connection, caplog, backend_type, config, kb_name, shared_key
) -> None:
    # The backend refuses such a name unless it is the KB's own owner-scoped
    # name, so a pin would make the knowledge base unusable after the upgrade.
    row = _add(connection, uuid4(), kb_name, config, backend_type=backend_type)

    with caplog.at_level(logging.WARNING):
        _MIGRATION.upgrade()

    assert _configs(connection)[row] == {
        **config,
        shared_key: kb_name.lower() if backend_type == "opensearch" else kb_name,
    }
    assert "reserved for owner-scoped storage" in caplog.text


def test_one_owners_colliding_index_names_are_pinned_together(connection) -> None:
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


def test_single_owner_chroma_cloud_collection_is_pinned(connection) -> None:
    row = _add(connection, uuid4(), "Team.Docs", dict(_CLOUD), backend_type="chroma")

    _MIGRATION.upgrade()

    assert _configs(connection)[row] == {
        **_CLOUD,
        "collection_name": "Team.Docs",
        "collection_name_origin": "legacy_kb_name",
    }


def test_chroma_cloud_collection_shared_by_two_owners_is_not_pinned(connection, caplog) -> None:
    alice = _add(connection, uuid4(), "docs", dict(_CLOUD), backend_type="chroma")
    bob = _add(connection, uuid4(), "docs", {"mode": "CLOUD"}, backend_type="chroma")
    # Chroma collection names are case-sensitive, so these never shared one.
    carol = _add(connection, uuid4(), "Docs", dict(_CLOUD), backend_type="chroma")

    with caplog.at_level(logging.WARNING):
        _MIGRATION.upgrade()

    configs = _configs(connection)
    assert configs[alice] == {**_CLOUD, "legacy_shared_collection": "docs"}
    assert configs[bob] == {"mode": "CLOUD", "legacy_shared_collection": "docs"}
    assert configs[carol]["collection_name"] == "Docs"
    assert "used Chroma Cloud collection docs, but shares it with other users' knowledge bases" in caplog.text


def test_backends_do_not_collide_with_each_other(connection) -> None:
    opensearch_row = _add(connection, uuid4(), "docs", {})
    cloud_row = _add(connection, uuid4(), "docs", dict(_CLOUD), backend_type="chroma")

    _MIGRATION.upgrade()

    configs = _configs(connection)
    assert configs[opensearch_row]["index_name"] == "docs"
    assert configs[cloud_row]["collection_name"] == "docs"


def test_local_chroma_and_other_backends_are_ignored(connection) -> None:
    cloud_row = _add(connection, uuid4(), "docs", dict(_CLOUD), backend_type="chroma")
    # Local Chroma is isolated per owner on disk; a local row never shares a
    # collection with a cloud row and must not be rewritten.
    local_row = _add(connection, uuid4(), "docs", {"mode": "local"}, backend_type="chroma")
    default_local_row = _add(connection, uuid4(), "docs", {}, backend_type="chroma")
    postgres_row = _add(connection, uuid4(), "docs", {}, backend_type="postgres")

    _MIGRATION.upgrade()

    configs = _configs(connection)
    assert configs[cloud_row]["collection_name"] == "docs"
    assert configs[local_row] == {"mode": "local"}
    assert configs[default_local_row] == {}
    assert configs[postgres_row] == {}


def test_downgrade_pins_owner_scoped_opensearch_rows_and_upgrade_is_then_a_no_op(connection) -> None:
    owner = uuid4()
    scoped = _add(connection, owner, "created after upgrade", {})
    legacy = _add(connection, owner, "legacy", {"index_name": "legacy", "index_name_origin": "legacy_kb_name"})
    shared = _add(connection, owner, "docs", {"legacy_shared_index": "docs"})

    _MIGRATION.downgrade()

    configs = _configs(connection)
    assert configs[scoped] == {
        "index_name": _MIGRATION.owner_scoped_name(owner, "created after upgrade"),
        "index_name_origin": "owner_scoped",
    }
    assert configs[legacy] == {"index_name": "legacy", "index_name_origin": "legacy_kb_name"}
    assert configs[shared]["index_name"] == _MIGRATION.owner_scoped_name(owner, "docs")

    _MIGRATION.upgrade()

    assert _configs(connection) == configs


def test_downgrade_leaves_chroma_cloud_rows_and_logs_the_ones_older_code_cannot_read(connection, caplog) -> None:
    owner = uuid4()
    scoped = _add(connection, owner, "created after upgrade", dict(_CLOUD), backend_type="chroma")
    pinned = _add(
        connection,
        owner,
        "legacy",
        {**_CLOUD, "collection_name": "legacy", "collection_name_origin": "legacy_kb_name"},
        backend_type="chroma",
    )
    before = _configs(connection)

    with caplog.at_level(logging.WARNING):
        _MIGRATION.downgrade()

    assert _configs(connection) == before
    assert str(scoped) in caplog.text
    assert str(pinned) not in caplog.text


def test_missing_table_is_a_no_op(monkeypatch) -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(conn)))
        _MIGRATION.upgrade()
        _MIGRATION.downgrade()
