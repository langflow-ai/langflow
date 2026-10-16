"""Finding and removing the pre-upgrade Chroma copies that the automatic SQLite upgrade retains."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from uuid import uuid4

import pytest
from langflow.services.knowledge_base_storage import retained
from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError

END_USER = "eu-alice-7f3"


def _chroma_copy(path, *, metadata=(), queue=()):
    """A retained copy with just the two Chroma tables that carry chunk metadata."""
    path.mkdir(parents=True)
    with closing(sqlite3.connect(path / "chroma.sqlite3")) as connection:
        connection.executescript(
            "CREATE TABLE embedding_metadata (id INTEGER, key TEXT, string_value TEXT);"
            "CREATE TABLE embeddings_queue (seq_id INTEGER PRIMARY KEY, metadata TEXT);"
        )
        connection.executemany("INSERT INTO embedding_metadata VALUES (1, ?, ?)", metadata)
        connection.executemany("INSERT INTO embeddings_queue (metadata) VALUES (?)", [(row,) for row in queue])
        connection.commit()
    return path


def test_should_find_an_end_user_tagged_in_the_metadata_segment(tmp_path):
    copy = _chroma_copy(tmp_path / "copy", metadata=[("end_user_id", END_USER)])

    assert retained.copy_mentions(copy, END_USER)


def test_should_not_find_an_end_user_the_copy_never_held(tmp_path):
    copy = _chroma_copy(
        tmp_path / "copy",
        metadata=[("end_user_id", "eu-bob-2c9")],
        queue=[json.dumps({"end_user_id": "eu-bob-2c9"})],
    )

    assert not retained.copy_mentions(copy, END_USER)


def test_should_find_an_end_user_only_present_in_a_pending_log_entry(tmp_path):
    # Escaping every character keeps the raw bytes from matching, so only the parsed log entry can.
    escaped = "".join(f"\\u{ord(character):04x}" for character in END_USER)
    copy = _chroma_copy(tmp_path / "copy", queue=[f'{{"end_user_id": "{escaped}"}}'])

    assert retained.copy_mentions(copy, END_USER)


def test_should_find_a_non_ascii_end_user_escaped_by_json(tmp_path):
    end_user = "josé-eu"
    copy = _chroma_copy(tmp_path / "copy")
    # Rows deleted in Chroma linger in free pages and journals, where only the bytes remain.
    (copy / "chroma.sqlite3-wal").write_bytes(b"\x00" * 64 + json.dumps({"end_user_id": end_user}).encode())

    assert retained.copy_mentions(copy, end_user)


def test_should_find_an_end_user_split_across_read_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(retained, "_READ_CHUNK", 5)
    copy = _chroma_copy(tmp_path / "copy")
    (copy / "chroma.sqlite3-journal").write_bytes(b'abc"end_user_id":"' + END_USER.encode() + b'"xyz')

    assert retained.copy_mentions(copy, END_USER)


@pytest.mark.parametrize("end_user", ["a", END_USER])
def test_should_not_match_an_end_user_id_that_only_appears_in_chunk_text(tmp_path, end_user):
    copy = _chroma_copy(
        tmp_path / "copy",
        metadata=[("chroma:document", f"a note mentioning {END_USER}"), ("end_user_id", "eu-bob-2c9")],
        queue=[json.dumps({"chroma:document": f"about {END_USER}", "end_user_id": "eu-bob-2c9"})],
    )

    assert not retained.copy_mentions(copy, end_user)


def test_should_find_an_end_user_in_a_failed_runs_export(tmp_path):
    export = tmp_path / "export.jsonl"
    export.write_text('{"header":{}}\n{"id":"doc-1","metadata":{"end_user_id":"' + END_USER + '"}}\n')

    assert retained.file_mentions(export, END_USER)
    assert not retained.file_mentions(export, "eu-bob-2c9")


def test_should_treat_an_unreadable_database_as_holding_the_end_user(tmp_path):
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / "chroma.sqlite3").write_bytes(b"not a database")

    assert retained.copy_mentions(copy, END_USER)


def test_should_not_find_anything_in_a_copy_without_a_database(tmp_path):
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / "header.bin").write_bytes(END_USER.encode())

    assert not retained.copy_mentions(copy, END_USER)


def test_should_name_the_original_directory_and_the_snapshot_of_an_upgrade_run(tmp_path):
    kb_id, run_id = uuid4(), uuid4()

    copies = retained.retained_copies(tmp_path, kb_id=kb_id, run_id=run_id, source_identity="owner/memory")

    assert copies == (tmp_path / "owner" / "memory", tmp_path / ".migration" / str(kb_id) / str(run_id) / "source")


@pytest.mark.parametrize("identity", ["owner", "owner/../memory", "../owner/memory", "owner\\x/memory", "a/b/c"])
def test_should_reject_a_source_identity_outside_one_owner_directory(tmp_path, identity):
    with pytest.raises(MaintenanceRequiredError):
        retained.retained_copies(tmp_path, kb_id=uuid4(), run_id=uuid4(), source_identity=identity)


def test_should_remove_a_retained_copy(tmp_path):
    copy = _chroma_copy(tmp_path / "owner" / "memory")

    retained.remove_copy(copy, tmp_path)

    assert not copy.exists()
    assert (tmp_path / "owner").is_dir()
    assert not any((tmp_path / ".migration" / "erased").iterdir())


def test_should_finish_a_removal_that_was_interrupted(tmp_path):
    # A copy is renamed out of the inventory scan's sight before deletion, so a crash leaves it here.
    leftover = _chroma_copy(tmp_path / ".migration" / "erased" / "interrupted")

    retained.remove_copy(tmp_path / "owner" / "absent", tmp_path)

    assert not leftover.exists()


def test_should_refuse_to_remove_a_copy_reached_through_a_symlink(tmp_path):
    outside = _chroma_copy(tmp_path / "outside" / "memory")
    root = tmp_path / "root"
    root.mkdir()
    (root / "owner").symlink_to(outside.parent, target_is_directory=True)

    with pytest.raises(MaintenanceRequiredError):
        retained.remove_copy(root / "owner" / "memory", root)

    assert (outside / "chroma.sqlite3").is_file()


def test_should_remove_the_upgrade_evidence_of_one_knowledge_base(tmp_path):
    kb_id, other = uuid4(), uuid4()
    for identity in (kb_id, other):
        _chroma_copy(tmp_path / ".migration" / str(identity) / str(uuid4()) / "source")

    retained.remove_upgrade_evidence(tmp_path, kb_id)

    assert not (tmp_path / ".migration" / str(kb_id)).exists()
    assert (tmp_path / ".migration" / str(other)).is_dir()
