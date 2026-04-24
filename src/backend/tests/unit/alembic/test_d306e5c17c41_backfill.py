"""Tests for the api_key_hash backfill helper in migration d306e5c17c41."""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import create_engine, text

# Migration filenames start with a digit, so we must import via importlib.
_MIGRATION = importlib.import_module("langflow.alembic.versions.d306e5c17c41_add_api_key_hash_column_to_apikey_table")
_backfill_hashes = _MIGRATION._backfill_hashes
_hash_key = _MIGRATION._hash_key


@pytest.fixture
def conn():
    """In-memory SQLite with a minimal apikey table matching the post-add-column shape."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        connection.execute(text("CREATE TABLE apikey (id TEXT PRIMARY KEY, api_key TEXT, api_key_hash TEXT)"))
        yield connection


def _insert(conn, rows):
    for row_id, api_key in rows:
        conn.execute(
            text("INSERT INTO apikey (id, api_key, api_key_hash) VALUES (:id, :k, NULL)"),
            {"id": row_id, "k": api_key},
        )


def _hashes(conn) -> dict[str, str | None]:
    result = conn.execute(text("SELECT id, api_key_hash FROM apikey")).fetchall()
    return {row[0]: row[1] for row in result}


def _decrypter(mapping: dict[str, str]):
    """Build a decrypt function that returns plaintexts from a mapping."""

    def decrypt(value):
        return mapping[value]

    return decrypt


def test_backfill_unique_keys_get_hashed(conn):
    """Every row with a unique decrypted plaintext gets a SHA-256 hash."""
    _insert(conn, [("a", "gAAAAA-enc-1"), ("b", "gAAAAA-enc-2")])

    decrypt = _decrypter({"gAAAAA-enc-1": "sk-one", "gAAAAA-enc-2": "sk-two"})
    backfilled, skipped, dup_groups, dup_rows = _backfill_hashes(conn, decrypt)

    assert (backfilled, skipped, dup_groups, dup_rows) == (2, 0, 0, 0)
    assert _hashes(conn) == {"a": _hash_key("sk-one"), "b": _hash_key("sk-two")}


def test_backfill_skips_undecryptable_rows(conn):
    """Rows whose decrypt returns empty string are counted as skipped, not hashed."""
    _insert(conn, [("a", "gAAAAA-orphan"), ("b", "gAAAAA-good")])

    def decrypt(value):
        return "" if value == "gAAAAA-orphan" else "sk-good"

    backfilled, skipped, dup_groups, dup_rows = _backfill_hashes(conn, decrypt)

    assert (backfilled, skipped, dup_groups, dup_rows) == (1, 1, 0, 0)
    hashes = _hashes(conn)
    assert hashes["a"] is None
    assert hashes["b"] == _hash_key("sk-good")


def test_backfill_skips_when_decrypt_raises(conn):
    """Rows whose decrypt raises are also counted as skipped."""
    _insert(conn, [("a", "gAAAAA-explodes")])

    def decrypt(_value):
        msg = "boom"
        raise ValueError(msg)

    backfilled, skipped, dup_groups, dup_rows = _backfill_hashes(conn, decrypt)

    assert (backfilled, skipped, dup_groups, dup_rows) == (0, 1, 0, 0)
    assert _hashes(conn) == {"a": None}


def test_backfill_treats_legacy_plaintext_keys_as_plaintext(conn):
    """Pre-1.7 rows store the key in plaintext (no gAAAAA prefix); decrypt is not called."""
    _insert(conn, [("a", "sk-plaintext")])

    def decrypt(_value):
        msg = "decrypt should not be called for plaintext rows"
        raise AssertionError(msg)

    backfilled, skipped, dup_groups, dup_rows = _backfill_hashes(conn, decrypt)

    assert (backfilled, skipped, dup_groups, dup_rows) == (1, 0, 0, 0)
    assert _hashes(conn) == {"a": _hash_key("sk-plaintext")}


def test_backfill_leaves_duplicate_plaintext_rows_unhashed(conn):
    """When two rows decrypt to the same plaintext, neither gets hashed.

    This is the core safety property: post-migration the runtime fast-path
    cannot return multiple matches for these rows, so it cannot fail closed.
    The runtime slow-path will match and backfill exactly one of them on
    first use.
    """
    _insert(
        conn,
        [
            ("dup-1", "gAAAAA-enc-A"),
            ("dup-2", "gAAAAA-enc-B"),  # different ciphertext, same plaintext
            ("unique", "gAAAAA-enc-C"),
        ],
    )

    decrypt = _decrypter(
        {
            "gAAAAA-enc-A": "sk-shared",
            "gAAAAA-enc-B": "sk-shared",
            "gAAAAA-enc-C": "sk-unique",
        }
    )
    backfilled, skipped, dup_groups, dup_rows = _backfill_hashes(conn, decrypt)

    assert (backfilled, skipped, dup_groups, dup_rows) == (1, 0, 1, 2)
    hashes = _hashes(conn)
    assert hashes["dup-1"] is None
    assert hashes["dup-2"] is None
    assert hashes["unique"] == _hash_key("sk-unique")


def test_backfill_counts_multiple_duplicate_groups(conn):
    """Counters aggregate across independent duplicate groups."""
    _insert(
        conn,
        [
            ("g1-a", "gAAAAA-1a"),
            ("g1-b", "gAAAAA-1b"),
            ("g2-a", "gAAAAA-2a"),
            ("g2-b", "gAAAAA-2b"),
            ("g2-c", "gAAAAA-2c"),
        ],
    )

    decrypt = _decrypter(
        {
            "gAAAAA-1a": "sk-one",
            "gAAAAA-1b": "sk-one",
            "gAAAAA-2a": "sk-two",
            "gAAAAA-2b": "sk-two",
            "gAAAAA-2c": "sk-two",
        }
    )
    backfilled, skipped, dup_groups, dup_rows = _backfill_hashes(conn, decrypt)

    assert (backfilled, skipped, dup_groups, dup_rows) == (0, 0, 2, 5)
    assert all(h is None for h in _hashes(conn).values())


def test_backfill_handles_empty_table(conn):
    """No rows means zero counters and no error."""

    def decrypt(value):
        return value

    backfilled, skipped, dup_groups, dup_rows = _backfill_hashes(conn, decrypt)
    assert (backfilled, skipped, dup_groups, dup_rows) == (0, 0, 0, 0)


def test_backfill_skips_rows_with_null_api_key(conn):
    """Rows with a NULL api_key column are silently ignored."""
    _insert(conn, [("a", None), ("b", "gAAAAA-good")])

    def decrypt(_value):
        return "sk-good"

    backfilled, skipped, dup_groups, dup_rows = _backfill_hashes(conn, decrypt)

    assert (backfilled, skipped, dup_groups, dup_rows) == (1, 0, 0, 0)
    assert _hashes(conn) == {"a": None, "b": _hash_key("sk-good")}


def test_backfill_only_processes_null_hash_rows(conn):
    """Rows that already have a hash are not re-processed."""
    _insert(conn, [("a", "gAAAAA-enc-1")])
    conn.execute(text("UPDATE apikey SET api_key_hash = 'preset' WHERE id = 'a'"))  # pragma: allowlist secret
    _insert(conn, [("b", "gAAAAA-enc-2")])

    def decrypt(_value):
        return "sk-only-b"

    backfilled, skipped, dup_groups, dup_rows = _backfill_hashes(conn, decrypt)

    assert (backfilled, skipped, dup_groups, dup_rows) == (1, 0, 0, 0)
    hashes = _hashes(conn)
    assert hashes["a"] == "preset"  # pragma: allowlist secret
    assert hashes["b"] == _hash_key("sk-only-b")
