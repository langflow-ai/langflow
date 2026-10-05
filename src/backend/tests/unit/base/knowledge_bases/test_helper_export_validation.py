"""Reject unsafe helper input before importing any retired native reader."""

import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
def exporter():
    """Load the isolated entry point without installing or invoking Chroma."""
    path = Path(__file__).resolve().parents[6] / "tools/chroma_migration_helper/export.py"
    spec = importlib.util.spec_from_file_location("migration_helper_export_validation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"collection_name": "private"},
        {"collection_name": "", "source_id": "id", "source_fingerprint": "f", "model_fingerprint": None},
    ],
)
def test_invalid_request_never_reaches_native_reader(exporter, monkeypatch, payload):
    def unexpected_reader(*_args):
        pytest.fail("Invalid requests must be rejected before native code is loaded")

    monkeypatch.setattr(exporter, "export", unexpected_reader)
    monkeypatch.setattr(
        exporter, "sys", SimpleNamespace(stdin=SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode())))
    )
    with pytest.raises(ValueError, match=r"Invalid export request|Invalid request identity"):
        exporter.main()


def test_oversized_request_is_rejected_before_json_decoding(exporter, monkeypatch):
    monkeypatch.setattr(
        exporter,
        "sys",
        SimpleNamespace(stdin=SimpleNamespace(buffer=io.BytesIO(b"x" * (exporter.MAX_REQUEST_BYTES + 1)))),
    )
    with pytest.raises(ValueError, match="Request exceeds byte limit"):
        exporter.main()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_snapshot_cannot_follow_links_or_special_files(exporter, tmp_path, kind):
    source = tmp_path / "source"
    source.mkdir()
    database = source / "chroma.sqlite3"
    database.write_bytes(b"synthetic database")
    unsafe = source / "unsafe"
    if kind == "symlink":
        unsafe.symlink_to(database)
    elif kind == "hardlink":
        os.link(database, unsafe)
    elif hasattr(os, "mkfifo"):
        os.mkfifo(unsafe)
    else:
        pytest.skip("This platform does not support FIFO files")
    with pytest.raises(ValueError, match=r"link|special file"):
        exporter.clone_snapshot(source, tmp_path / "working")
    assert not (tmp_path / "working").exists()


@pytest.mark.parametrize("limit", ["MAX_SOURCE_FILES", "MAX_SOURCE_BYTES"])
def test_snapshot_limits_leave_source_intact(exporter, tmp_path, monkeypatch, limit):
    source = tmp_path / "source"
    source.mkdir()
    database = source / "chroma.sqlite3"
    database.write_bytes(b"original")
    monkeypatch.setattr(exporter, limit, 0)
    with pytest.raises(ValueError, match="Snapshot exceeds helper limits"):
        exporter.clone_snapshot(source, tmp_path / "working")
    assert database.read_bytes() == b"original"
    assert not (tmp_path / "working").exists()


@pytest.mark.parametrize("metadata", [{1: "non-string key"}, {"unsupported"}, {"value": object()}])
def test_unsupported_metadata_is_rejected(exporter, metadata):
    with pytest.raises(ValueError, match=r"Metadata key|Unsupported metadata"):
        exporter.metadata_depth(metadata)


def test_deep_metadata_and_nonfinite_output_are_rejected(exporter, monkeypatch):
    monkeypatch.setattr(exporter, "MAX_METADATA_DEPTH", 2)
    with pytest.raises(ValueError, match="Metadata exceeds depth limit"):
        exporter.metadata_depth({"a": {"b": {"c": 1}}})
    with pytest.raises(ValueError, match="Out of range float"):
        exporter.encode({"embedding": [float("nan")]})


def test_oversized_record_is_not_partially_emitted(exporter, monkeypatch):
    stream = io.BytesIO()
    monkeypatch.setattr(exporter, "sys", SimpleNamespace(stdout=SimpleNamespace(buffer=stream)))
    monkeypatch.setattr(exporter, "MAX_LINE_BYTES", 32)
    with pytest.raises(ValueError, match="Export record exceeds byte limit"):
        exporter.emit({"content": "x" * 32})
    assert stream.getvalue() == b""
