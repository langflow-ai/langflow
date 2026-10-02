"""Real persisted Chroma data upgrades without installing or executing its SDK."""

from __future__ import annotations

import json
import struct
import tarfile
from pathlib import Path

import pytest
from lfx.base.knowledge_bases.migration.legacy_reader import export_local_snapshot
from lfx.base.knowledge_bases.migration.protocol import MigrationProtocolError, qualify_export


@pytest.fixture(params=["1.5.9", "0.5.23"])
def legacy_source(tmp_path, request):
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
