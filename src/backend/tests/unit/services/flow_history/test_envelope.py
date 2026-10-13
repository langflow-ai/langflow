"""The ``flow_operation.ops`` envelope: one batch per request, validated on decode."""

from __future__ import annotations

import copy
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow_operation import FlowOperation as FlowOperationRow
from langflow.services.flow_history.envelope import (
    COUNT_MISMATCH,
    MALFORMED_BATCH,
    MALFORMED_OPERATION,
    REQUEST_REPEATED,
    REVISION_OUT_OF_ORDER,
    UNSUPPORTED_ENVELOPE,
    RecordedOperation,
    decode_row,
    encode_envelope,
)
from langflow.services.flow_history.errors import FlowHistoryCorruptionError
from lfx.services.flow_operations import parse_flow_operation

ALICE = UUID(int=1)
BOB = UUID(int=2)


def _recorded(revision: int, request_id: UUID, actor: UUID, cause: str | None = None) -> RecordedOperation:
    operation = parse_flow_operation({"type": "update_metadata", "fields": {"name": f"r{revision}"}})
    return RecordedOperation(
        revision=revision, actor_user_id=actor, request_id=request_id, operation=operation, cause=cause
    )


def _row(ops: dict, start: int, end: int) -> FlowOperationRow:
    return FlowOperationRow(
        flow_id=uuid4(), start_revision=start, end_revision=end, ops=ops, actor_user_ids=[], request_ids=[]
    )


def _assert_corrupt(ops: dict, start: int, end: int, kind: str, revision: int) -> None:
    with pytest.raises(FlowHistoryCorruptionError) as caught:
        decode_row(_row(ops, start, end))
    assert (caught.value.kind, caught.value.revision) == (kind, revision)


def _two_requests() -> tuple[list[RecordedOperation], dict]:
    first, second = uuid4(), uuid4()
    operations = [
        _recorded(5, first, ALICE, cause="upgrade_component"),
        _recorded(6, first, ALICE),
        _recorded(7, second, BOB),
    ]
    return operations, encode_envelope(operations)


def test_a_row_stores_one_batch_per_request_in_order():
    operations, envelope = _two_requests()

    assert envelope["version"] == 1
    assert [(batch["request_id"], batch["actor_user_id"]) for batch in envelope["batches"]] == [
        (str(operations[0].request_id), str(ALICE)),
        (str(operations[2].request_id), str(BOB)),
    ]
    assert [[element["revision"] for element in batch["operations"]] for batch in envelope["batches"]] == [[5, 6], [7]]
    assert envelope["batches"][0]["operations"][0]["cause"] == "upgrade_component"
    assert "cause" not in envelope["batches"][0]["operations"][1]
    assert decode_row(_row(envelope, 5, 7)) == operations


def test_one_request_with_two_actors_is_refused():
    request_id = uuid4()

    with pytest.raises(ValueError, match="two actors"):
        encode_envelope([_recorded(1, request_id, ALICE), _recorded(2, request_id, BOB)])


def test_an_unknown_version_or_shape_is_unsupported():
    _, envelope = _two_requests()

    _assert_corrupt({**envelope, "version": 2}, 5, 7, UNSUPPORTED_ENVELOPE, 5)
    _assert_corrupt({"version": 1, "operations": []}, 5, 7, UNSUPPORTED_ENVELOPE, 5)


def test_a_request_with_two_batches_in_one_row_is_damage():
    operations, envelope = _two_requests()
    split = copy.deepcopy(envelope)
    split["batches"].insert(1, split["batches"][0] | {"operations": [split["batches"][0]["operations"].pop()]})
    resumed = encode_envelope([*operations, _recorded(8, operations[0].request_id, ALICE)])

    _assert_corrupt(split, 5, 7, REQUEST_REPEATED, 6)
    _assert_corrupt(resumed, 5, 8, REQUEST_REPEATED, 8)


def test_a_malformed_batch_is_damage():
    _, envelope = _two_requests()
    empty = copy.deepcopy(envelope)
    empty["batches"][1]["operations"] = []
    bad_actor = copy.deepcopy(envelope)
    bad_actor["batches"][1]["actor_user_id"] = "not-a-uuid"
    no_request = copy.deepcopy(envelope)
    del no_request["batches"][0]["request_id"]

    _assert_corrupt(empty, 5, 7, MALFORMED_BATCH, 7)
    _assert_corrupt(bad_actor, 5, 7, MALFORMED_BATCH, 7)
    _assert_corrupt(no_request, 5, 7, MALFORMED_BATCH, 5)


def test_revisions_count_across_batches_and_must_fill_the_range():
    _, envelope = _two_requests()
    gap = copy.deepcopy(envelope)
    gap["batches"][1]["operations"][0]["revision"] = 8
    bad_operation = copy.deepcopy(envelope)
    bad_operation["batches"][1]["operations"][0]["operation"] = {"type": "nope"}

    _assert_corrupt(gap, 5, 7, REVISION_OUT_OF_ORDER, 7)
    _assert_corrupt(bad_operation, 5, 7, MALFORMED_OPERATION, 7)
    _assert_corrupt(envelope, 5, 8, COUNT_MISMATCH, 5)
