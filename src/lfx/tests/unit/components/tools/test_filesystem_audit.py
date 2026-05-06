"""Unit tests for the audit log layer of the FileSystem tool."""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class TestAuditRecord:
    """Slice C1 — value object capturing one tool call's outcome."""

    def test_should_serialize_with_mandatory_fields(self) -> None:
        from lfx.components.tools._filesystem_audit import AuditRecord

        record = AuditRecord(
            ts=1_700_000_000.5,
            user_id="user-123",
            flow_id="flow-456",
            action="read_file",
            path="notes.md",
            ok=True,
            err=None,
        )

        payload = record.to_json_dict()

        assert payload == {
            "ts": 1_700_000_000.5,
            "user_id": "user-123",
            "flow_id": "flow-456",
            "action": "read_file",
            "path": "notes.md",
            "ok": True,
            "err": None,
        }

    def test_should_accept_none_for_optional_fields(self) -> None:
        from lfx.components.tools._filesystem_audit import AuditRecord

        record = AuditRecord(
            ts=0.0,
            user_id=None,
            flow_id=None,
            action="glob_search",
            path=None,
            ok=False,
            err="Path escapes workspace boundary",
        )

        payload = record.to_json_dict()

        assert payload["user_id"] is None
        assert payload["flow_id"] is None
        assert payload["path"] is None
        assert payload["ok"] is False
        assert payload["err"] == "Path escapes workspace boundary"


class TestNDJSONAuditSink:
    """Slice C2 — write JSON-lines to a file, one record per line."""

    def test_should_append_one_line_per_record(self, tmp_path: Path) -> None:
        from lfx.components.tools._filesystem_audit import (
            AuditRecord,
            NDJSONAuditSink,
        )

        log_path = tmp_path / "audit.jsonl"
        sink = NDJSONAuditSink(log_path)

        sink.write(
            AuditRecord(
                ts=1.0,
                user_id="u1",
                flow_id="f1",
                action="read_file",
                path="a.txt",
                ok=True,
                err=None,
            )
        )
        sink.write(
            AuditRecord(
                ts=2.0,
                user_id="u1",
                flow_id="f1",
                action="write_file",
                path="b.txt",
                ok=False,
                err="boundary",
            )
        )

        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["action"] == "read_file"
        assert json.loads(lines[1])["err"] == "boundary"

    def test_should_create_parent_directory_when_missing(self, tmp_path: Path) -> None:
        from lfx.components.tools._filesystem_audit import (
            AuditRecord,
            NDJSONAuditSink,
        )

        log_path = tmp_path / "nested" / "logs" / "audit.jsonl"
        sink = NDJSONAuditSink(log_path)

        sink.write(
            AuditRecord(
                ts=1.0,
                user_id=None,
                flow_id=None,
                action="read_file",
                path=None,
                ok=True,
                err=None,
            )
        )

        assert log_path.exists()

    def test_should_be_threadsafe_when_multiple_threads_write(self, tmp_path: Path) -> None:
        # Why this test: tool calls happen concurrently in async flows.
        # Two threads writing simultaneously must not produce torn lines.
        from lfx.components.tools._filesystem_audit import (
            AuditRecord,
            NDJSONAuditSink,
        )

        log_path = tmp_path / "audit.jsonl"
        sink = NDJSONAuditSink(log_path)
        writes_per_thread = 25
        threads_count = 4

        def worker(idx: int) -> None:
            for j in range(writes_per_thread):
                sink.write(
                    AuditRecord(
                        ts=float(idx * writes_per_thread + j),
                        user_id=f"u{idx}",
                        flow_id="f",
                        action="read_file",
                        path=f"{idx}-{j}",
                        ok=True,
                        err=None,
                    )
                )

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == writes_per_thread * threads_count
        # Every line must be a complete, parsable JSON object — no torn writes.
        for line in lines:
            parsed = json.loads(line)
            assert "action" in parsed


class TestNullAuditSink:
    """Slice C3 — quiet sink for when audit logging is disabled."""

    def test_should_accept_writes_without_side_effects(self) -> None:
        from lfx.components.tools._filesystem_audit import (
            AuditRecord,
            NullAuditSink,
        )

        sink = NullAuditSink()

        # Should not raise, should not touch any file.
        sink.write(
            AuditRecord(
                ts=0.0,
                user_id=None,
                flow_id=None,
                action="read_file",
                path=None,
                ok=True,
                err=None,
            )
        )


class TestMakeAuditSink:
    """Slice C4 — factory selects the right sink based on config."""

    def test_should_return_null_sink_when_path_is_none(self) -> None:
        from lfx.components.tools._filesystem_audit import (
            NullAuditSink,
            make_audit_sink,
        )

        sink = make_audit_sink(audit_log_path=None)

        assert isinstance(sink, NullAuditSink)

    def test_should_return_ndjson_sink_when_path_is_provided(self, tmp_path: Path) -> None:
        from lfx.components.tools._filesystem_audit import (
            NDJSONAuditSink,
            make_audit_sink,
        )

        sink = make_audit_sink(audit_log_path=tmp_path / "audit.jsonl")

        assert isinstance(sink, NDJSONAuditSink)
