"""Stored values must stay out of relocation diagnostics and JSON events."""

from __future__ import annotations

import json
import traceback
from uuid import uuid4

import pytest
from langflow.api.utils.knowledge_base_relocation import KBRelocationResult, _describe
from langflow.cli import relocate_kb_events
from lfx.base.knowledge_bases.backends.opensearch import _refused_documents_left_out
from sqlalchemy.exc import DataError


def _assert_events_contain_only_safe_diagnostics(reason: str, capsys: pytest.CaptureFixture[str]) -> None:
    result = KBRelocationResult(
        kb_id=uuid4(),
        kb_name="diagnostics",
        owner="owner",
        source_backend="sqlite",
        target_backend="postgres",
        status="failed",
        code="kb_failed",
        reason=reason,
    )
    relocate_kb_events.item(result)
    relocate_kb_events.report([result], {"failed": 1}, dry_run=False)
    output = capsys.readouterr().out
    assert "private" not in output
    item, report = [json.loads(line) for line in output.splitlines()]
    assert item["item"]["reason"] == report["attention"][0]["reason"] == reason
    assert item["item"]["code"] == "kb_failed"


def test_database_driver_first_line_cannot_expose_stored_values(capsys: pytest.CaptureFixture[str]) -> None:
    # Drivers can quote an invalid value on the first line, before SQLAlchemy's
    # statement/parameter dump. Keeping only that line still discloses the value.
    driver_error = ValueError('invalid input syntax for type json: "private metadata"\nDETAIL: refused value')
    error = DataError("INSERT INTO chunks", {"document": "private chunk text"}, driver_error)

    reason = _describe(error)

    assert reason == "ValueError: database operation failed"
    _assert_events_contain_only_safe_diagnostics(reason, capsys)


@pytest.mark.usefixtures("fake_opensearchpy")
def test_bulk_refusal_cannot_quote_stored_values(capsys: pytest.CaptureFixture[str]) -> None:
    from opensearchpy.helpers import BulkIndexError

    # A mapping refusal quotes the invalid metadata both in its reason and its
    # cause. Neither is safe diagnostic text, even after omitting the document.
    errors = [
        {
            "index": {
                "error": {
                    "type": "mapper_parsing_exception",
                    "reason": "failed to parse field [metadata.note]. Preview of field's value: 'private note'",
                    "caused_by": {"type": "illegal_argument_exception", "reason": 'For input string: "private note"'},
                },
                "data": {"metadata": {"note": "private note"}, "text": "private chunk text"},
            }
        }
    ]
    error = BulkIndexError("1 document(s) failed to index.", errors)

    with pytest.raises(RuntimeError) as rejected, _refused_documents_left_out():
        raise error

    reason = _describe(rejected.value)
    assert reason == "RuntimeError: 1 document(s) failed to index. Error type(s): mapper_parsing_exception."
    printed = "".join(traceback.format_exception(rejected.value))
    assert "private note" not in printed
    assert "private chunk text" not in printed
    _assert_events_contain_only_safe_diagnostics(reason, capsys)
