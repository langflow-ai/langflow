"""Real persisted Chroma data upgrades without installing or executing its SDK."""

from __future__ import annotations

import json
import pickle
import shutil
import sqlite3
import struct
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from lfx.base.knowledge_bases.migration.inert_pickle import read_index_metadata
from lfx.base.knowledge_bases.migration.legacy_reader import export_local_snapshot
from lfx.base.knowledge_bases.migration.protocol import (
    AutomaticMigrationLimitError,
    MigrationProtocolError,
    qualify_export,
)


@pytest.fixture(params=["1.5.9", "0.5.23"])
def legacy_source(tmp_path, request):
    """Extract both supported Chroma generations into an isolated native store."""
    fixture = Path(__file__).with_name("fixtures") / f"chroma-{request.param}-local.tar.gz"
    with tarfile.open(fixture) as archive:
        for member in archive:
            assert member.isfile()
            assert not Path(member.name).is_absolute()
            assert ".." not in Path(member.name).parts
            destination = tmp_path / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as stream:
                destination.write_bytes(stream.read())
    return tmp_path / "source", json.loads((tmp_path / "expected.json").read_text())


@pytest.mark.parametrize("metric", ["l2", "cosine", "ip", "empty"])
def test_native_vectors_and_pending_operations_are_preserved(legacy_source, tmp_path, metric):
    """Verify documents, metadata and vectors after replaying pending native writes."""
    source, expected = legacy_source
    output = tmp_path / "export.jsonl"
    header = export_local_snapshot(
        source,
        output,
        collection_name=f"fixture-{metric}",
        source_id="fixture-id",
        source_fingerprint="f" * 64,
        model_fingerprint=None,
    )
    with output.open("rb") as stream, qualify_export(stream, expected_header=header) as verified:
        records = {
            document.id: {
                "content": document.content,
                "metadata": document.metadata,
                "embedding": document.embedding,
            }
            for offset in range(0, header.count, 500)
            for document in verified.read_batch(offset, batch_size=500)
        }
    assert set(records) == set(expected.get(metric, {}))
    for native_id, original in expected.get(metric, {}).items():
        assert records[native_id]["content"] == original["content"]
        assert records[native_id]["metadata"] == original["metadata"]
        # Pending cosine vectors retain the raw float32 log values. Chroma's
        # get() normalizes then denormalizes them, introducing a few ULPs.
        assert records[native_id]["embedding"] == pytest.approx(original["embedding"], rel=1e-6, abs=1e-7)
    assert header.dimensions == 4
    assert "doc-5" not in records
    assert "doc-9" not in records
    if metric != "empty":
        assert records["doc-2"]["content"] == "Updated document"
        assert records["pending-doc"]["embedding"] == [1.0, 2.0, 3.0, 4.0]


def test_executable_index_metadata_is_rejected_without_execution(legacy_source, tmp_path):
    """Reject executable pickle instructions without running their payload."""
    source, _ = legacy_source
    # GLOBAL + REDUCE would call os.system in a conventional pickle loader.
    hostile = b"cos\nsystem\n(S'touch " + str(tmp_path / "must-not-execute").encode() + b"'\ntR."
    for path in source.glob("*/index_metadata.pickle"):
        path.write_bytes(hostile)
    with pytest.raises(MigrationProtocolError):
        export_local_snapshot(
            source,
            tmp_path / "export.jsonl",
            collection_name="fixture-l2",
            source_id="fixture-id",
            source_fingerprint="f" * 64,
            model_fingerprint=None,
        )

    assert not (tmp_path / "must-not-execute").exists()


def test_corrupt_native_offsets_fail_without_a_completion_record(legacy_source, tmp_path):
    """Keep malformed native indexes from producing an apparently complete export."""
    source, _ = legacy_source
    for path in source.glob("*/header.bin"):
        header = bytearray(path.read_bytes())
        struct.pack_into("<Q", header, 28, 2**63)
        path.write_bytes(header)
    output = tmp_path / "export.jsonl"
    with pytest.raises(MigrationProtocolError):
        export_local_snapshot(
            source,
            output,
            collection_name="fixture-l2",
            source_id="fixture-id",
            source_fingerprint="f" * 64,
            model_fingerprint=None,
        )
    assert not output.exists() or b'"type":"complete"' not in output.read_bytes()


def test_metadata_checkpoint_replays_pending_text_and_addition(legacy_source, tmp_path):
    """Recover updated and newly added documents beyond the metadata checkpoint."""
    import sqlite3

    source, expected = legacy_source
    with sqlite3.connect(source / "chroma.sqlite3") as connection:
        collection_id = connection.execute("SELECT id FROM collections WHERE name='fixture-l2'").fetchone()[0]
        segment_id = connection.execute(
            "SELECT id FROM segments WHERE collection=? AND scope='METADATA'", (collection_id,)
        ).fetchone()[0]
        checkpoint = connection.execute(
            "SELECT seq_id FROM embeddings_queue WHERE topic LIKE ? AND id='doc-239'", ("%/" + collection_id,)
        ).fetchone()[0]
        old = connection.execute("SELECT seq_id FROM max_seq_id WHERE segment_id=?", (segment_id,)).fetchone()[0]
        connection.execute(
            "UPDATE max_seq_id SET seq_id=? WHERE segment_id=?",
            (checkpoint.to_bytes(8, "big") if isinstance(old, bytes) else checkpoint, segment_id),
        )
        connection.execute(
            "UPDATE embedding_metadata SET string_value='Old document' WHERE key='chroma:document' "
            "AND id IN (SELECT id FROM embeddings WHERE segment_id=? AND embedding_id='doc-2')",
            (segment_id,),
        )
        connection.execute(
            "DELETE FROM embedding_metadata WHERE id IN "
            "(SELECT id FROM embeddings WHERE segment_id=? AND embedding_id='pending-doc')",
            (segment_id,),
        )
        connection.execute("DELETE FROM embeddings WHERE segment_id=? AND embedding_id='pending-doc'", (segment_id,))
    output = tmp_path / "recovered.jsonl"
    header = export_local_snapshot(
        source,
        output,
        collection_name="fixture-l2",
        source_id="fixture-id",
        source_fingerprint="f" * 64,
        model_fingerprint=None,
    )
    with output.open("rb") as stream, qualify_export(stream, expected_header=header) as verified:
        records = {record.id: record for record in verified.read_batch(0)}
    assert records["doc-2"].content == expected["l2"]["doc-2"]["content"]
    assert records["pending-doc"].content == expected["l2"]["pending-doc"]["content"]
    assert header.count == len(expected["l2"])


def test_sqlite_wal_is_read_without_changing_pristine_source(legacy_source, tmp_path):
    """Include committed WAL text while leaving the original database files intact."""
    import sqlite3

    source, _ = legacy_source
    with sqlite3.connect(source / "chroma.sqlite3") as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute(
            "UPDATE embedding_metadata SET string_value='Text in the WAL' WHERE key='chroma:document' "
            "AND id IN (SELECT e.id FROM embeddings e JOIN segments s ON e.segment_id=s.id "
            "JOIN collections c ON s.collection=c.id WHERE c.name='fixture-l2' AND e.embedding_id='doc-2')"
        )
        connection.commit()
        before = {path.name: path.read_bytes() for path in source.glob("chroma.sqlite3*")}
        output = tmp_path / "wal.jsonl"
        header = export_local_snapshot(
            source,
            output,
            collection_name="fixture-l2",
            source_id="fixture-id",
            source_fingerprint="f" * 64,
            model_fingerprint=None,
        )
        with output.open("rb") as stream, qualify_export(stream, expected_header=header) as verified:
            records = {record.id: record for record in verified.read_batch(0)}
        assert records["doc-2"].content == "Text in the WAL"
        assert {path.name: path.read_bytes() for path in source.glob("chroma.sqlite3*")} == before


def test_hot_rollback_journal_recovers_committed_text_without_touching_source(legacy_source, tmp_path):
    """Recover committed text from a crashed writer in a private database copy."""
    source, expected = legacy_source
    code = """
import os, sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.execute('PRAGMA journal_mode=DELETE')
c.execute('PRAGMA cache_size=1')
c.execute('BEGIN IMMEDIATE')
c.execute("UPDATE embedding_metadata SET string_value=upper(string_value) WHERE string_value IS NOT NULL")
os._exit(0)
"""
    subprocess.run([sys.executable, "-c", code, str(source / "chroma.sqlite3")], check=True)  # noqa: S603 -- fixed program and private fixture
    assert (source / "chroma.sqlite3-journal").stat().st_size > 512
    before = {path.name: path.read_bytes() for path in source.glob("chroma.sqlite3*")}
    output = tmp_path / "journal.jsonl"
    header = export_local_snapshot(
        source,
        output,
        collection_name="fixture-l2",
        source_id="fixture-id",
        source_fingerprint="f" * 64,
        model_fingerprint=None,
    )
    with output.open("rb") as stream, qualify_export(stream, expected_header=header) as verified:
        records = {record.id: record for record in verified.read_batch(0)}
    assert {key: record.content for key, record in records.items()} == {
        key: record["content"] for key, record in expected["l2"].items()
    }
    assert {path.name: path.read_bytes() for path in source.glob("chroma.sqlite3*")} == before


@pytest.mark.parametrize("metric", ["cosine", "ip"])
def test_early_rust_vector_index_configuration_preserves_metric(legacy_source, tmp_path, metric):
    """Read the original distance metric from early Rust collection configuration."""
    source, _ = legacy_source
    with sqlite3.connect(source / "chroma.sqlite3") as connection:
        collection = connection.execute("SELECT id FROM collections WHERE name=?", (f"fixture-{metric}",)).fetchone()[0]
        connection.execute("DELETE FROM collection_metadata WHERE collection_id=? AND key='hnsw:space'", (collection,))
        connection.execute(
            "DELETE FROM segment_metadata WHERE segment_id IN (SELECT id FROM segments WHERE collection=?) "
            "AND key='hnsw:space'",
            (collection,),
        )
        connection.execute(
            "UPDATE collections SET config_json_str=? WHERE id=?",
            (json.dumps({"vector_index": {"hnsw": {"space": metric}}}), collection),
        )
        if "schema_str" in {row[1] for row in connection.execute("PRAGMA table_info(collections)")}:
            connection.execute("UPDATE collections SET schema_str=NULL WHERE id=?", (collection,))
    header = export_local_snapshot(
        source,
        tmp_path / "metric.jsonl",
        collection_name=f"fixture-{metric}",
        source_id="fixture-id",
        source_fingerprint="f" * 64,
        model_fingerprint=None,
    )
    assert header.metric == metric


def test_uninitialized_empty_collection_directory_can_migrate(legacy_source, tmp_path):
    """Accept an empty collection before its native vector checkpoint exists."""
    source, _ = legacy_source
    with sqlite3.connect(source / "chroma.sqlite3") as connection:
        collection = connection.execute("SELECT id FROM collections WHERE name='fixture-empty'").fetchone()[0]
        connection.execute("UPDATE collections SET dimension=NULL WHERE id=?", (collection,))
        segment = connection.execute(
            "SELECT id FROM segments WHERE collection=? AND scope='VECTOR'", (collection,)
        ).fetchone()[0]
        connection.execute("DELETE FROM embeddings_queue WHERE topic LIKE ?", (f"%/{collection}",))
        connection.execute(
            "DELETE FROM max_seq_id WHERE segment_id IN (SELECT id FROM segments WHERE collection=?)", (collection,)
        )
    shutil.rmtree(source / segment, ignore_errors=True)
    (source / segment).mkdir()
    assert not list((source / segment).iterdir())
    header = export_local_snapshot(
        source,
        tmp_path / "empty.jsonl",
        collection_name="fixture-empty",
        source_id="fixture-id",
        source_fingerprint="f" * 64,
        model_fingerprint=None,
    )
    assert header.count == 0


@pytest.mark.parametrize("key", [-1, 2**64, (2**61 - 1) * 100])
def test_pickle_rejects_integer_dictionary_keys_outside_native_label_range(key):
    """Reject integer labels outside the native range before dictionary insertion."""
    with pytest.raises(MigrationProtocolError):
        read_index_metadata(pickle.dumps({"label_to_id": {key: "document"}}, protocol=4))


@pytest.mark.parametrize("cap", ["MAX_INDEX_METADATA_BYTES", "_MAX_OPERATIONS", "_MAX_STACK"])
def test_native_reader_limits_report_specific_recovery_requirement(monkeypatch, cap):
    """Oversized indexes should request a managed helper instead of blind retries."""
    from lfx.base.knowledge_bases.migration import inert_pickle

    monkeypatch.setattr(inert_pickle, cap, 1)
    with pytest.raises(AutomaticMigrationLimitError):
        read_index_metadata(pickle.dumps({"labels": {1: "one", 2: "two"}}, protocol=4))


def test_typed_array_metadata_preserves_order_and_pending_updates(legacy_source, tmp_path):
    """Preserve list order and scalar types from the native array metadata table."""
    source, _ = legacy_source
    with sqlite3.connect(source / "chroma.sqlite3") as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS embedding_metadata_array (id INTEGER NOT NULL, key TEXT NOT NULL, "
            "string_value TEXT, int_value INTEGER, float_value REAL, bool_value INTEGER)"
        )
        identity = connection.execute(
            "SELECT e.id FROM embeddings e JOIN segments s ON e.segment_id=s.id "
            "JOIN collections c ON s.collection=c.id WHERE c.name='fixture-l2' AND e.embedding_id='doc-0'"
        ).fetchone()[0]
        connection.executemany(
            "INSERT INTO embedding_metadata_array VALUES (?,?,?,?,?,?)",
            [
                (identity, "tags", "z", None, None, None),
                (identity, "tags", "a", None, None, None),
                (identity, "nums", None, 3, None, None),
                (identity, "nums", None, 1, None, None),
                (identity, "flags", None, None, None, 1),
                (identity, "flags", None, None, None, 0),
                (identity, "floats", None, None, 0.5, None),
            ],
        )
    output = tmp_path / "arrays.jsonl"
    header = export_local_snapshot(
        source,
        output,
        collection_name="fixture-l2",
        source_id="fixture-id",
        source_fingerprint="f" * 64,
        model_fingerprint=None,
    )
    with output.open("rb") as stream, qualify_export(stream, expected_header=header) as verified:
        records = {record.id: record for record in verified.read_batch(0)}
    assert records["doc-0"].metadata["tags"] == ["z", "a"]
    assert records["doc-0"].metadata["nums"] == [3, 1]
    assert records["doc-0"].metadata["flags"] == [True, False]
    assert records["doc-0"].metadata["floats"] == [0.5]


def test_cosine_restore_overflow_is_a_validation_failure(legacy_source, tmp_path):
    """Report invalid cosine restoration as a bounded export validation failure."""
    source, _ = legacy_source
    with sqlite3.connect(source / "chroma.sqlite3") as connection:
        segment = connection.execute(
            "SELECT s.id FROM segments s JOIN collections c ON s.collection=c.id "
            "WHERE c.name='fixture-cosine' AND s.scope='VECTOR'"
        ).fetchone()[0]
    directory = source / segment
    header = struct.Struct("<i6QiI3QdQ").unpack((directory / "header.bin").read_bytes())
    data = bytearray((directory / "data_level0.bin").read_bytes())
    # Make every live slot finite but too large to round back into float32.
    for offset in range(header[3]):
        struct.pack_into("<4f", data, offset * header[4] + header[6], *([3e38] * 4))
    (directory / "data_level0.bin").write_bytes(data)
    (directory / "length.bin").write_bytes(struct.pack("<f", 3e38) * (len(data) // header[4]))
    with pytest.raises(MigrationProtocolError, match="float32"):
        export_local_snapshot(
            source,
            tmp_path / "overflow.jsonl",
            collection_name="fixture-cosine",
            source_id="fixture-id",
            source_fingerprint="f" * 64,
            model_fingerprint=None,
        )
