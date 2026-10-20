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
from langflow.services.flow_history.secrets import SecretPart
from lfx.services.flow_operations import parse_flow_operation

ALICE = UUID(int=1)
BOB = UUID(int=2)
HEADERS = ["data", "node", "template", "api_headers", "value"]


def _recorded(revision: int, request_id: UUID, actor: UUID, cause: str | None = None) -> RecordedOperation:
    operation = parse_flow_operation({"type": "delete_nodes", "ids": [f"n{revision}"]})
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


def _with_secrets(revision: int, request_id: UUID) -> RecordedOperation:
    row = {"__id__": "r1", "__pos__": 1, "key": "Authorization", "value": "Bearer k"}
    operation = parse_flow_operation(
        {
            "type": "update_nodes",
            "updates": [
                {"id": "a", "op": "set_field", "path": [*HEADERS, {"key": "r1"}], "value": row},
                {"id": "a", "op": "set_field", "path": ["position"], "value": {"x": 1, "y": 2}},
            ],
        }
    )
    return RecordedOperation(
        revision=revision,
        actor_user_id=ALICE,
        request_id=request_id,
        operation=operation,
        secrets=((SecretPart(path=("value",), kind="literal"),), ()),
    )


def test_a_removed_part_is_stored_and_decoded():
    operation = parse_flow_operation(
        {
            "type": "update_nodes",
            "updates": [
                {
                    "id": "a",
                    "op": "set_field",
                    "path": ["data", "node", "template", "mcp_server", "value"],
                    "value": {"name": "github", "config": {"command": "npx"}},
                }
            ],
        }
    )
    recorded = RecordedOperation(
        revision=1,
        actor_user_id=ALICE,
        request_id=uuid4(),
        operation=operation,
        secrets=((SecretPart(path=("config",), kind="removed"),),),
    )
    envelope = encode_envelope([recorded])

    assert _first_write(envelope)["secrets"] == [{"path": ["config"], "kind": "removed"}]
    (decoded,) = decode_row(_row(envelope, 1, 1))
    assert decoded == recorded


def test_a_part_inside_a_list_is_stored_by_its_index():
    rows = [
        {"__id__": "r1", "__pos__": 1, "key": "Accept", "value": "DOCLING_TOKEN"},
        {"__id__": "r2", "__pos__": 2, "key": "Authorization", "value": "Bearer k"},
    ]
    operation = parse_flow_operation(
        {"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": HEADERS, "value": rows}]}
    )
    recorded = RecordedOperation(
        revision=1,
        actor_user_id=ALICE,
        request_id=uuid4(),
        operation=operation,
        secrets=((SecretPart(path=(0, "value"), kind="variable"), SecretPart(path=(1, "value"), kind="literal")),),
    )
    envelope = encode_envelope([recorded])

    assert _first_write(envelope)["secrets"] == [
        {"path": [0, "value"], "kind": "variable"},
        {"path": [1, "value"], "kind": "literal"},
    ]
    (decoded,) = decode_row(_row(envelope, 1, 1))
    assert decoded == recorded


def _first_write(envelope: dict) -> dict:
    return envelope["batches"][0]["operations"][0]["operation"]["updates"][0]


def test_a_write_stores_its_secret_parts_and_decoding_keeps_them_beside_the_operation():
    recorded = _with_secrets(1, uuid4())
    envelope = encode_envelope([recorded])
    stored = copy.deepcopy(envelope)

    updates = envelope["batches"][0]["operations"][0]["operation"]["updates"]
    assert updates[0]["secrets"] == [{"path": ["value"], "kind": "literal"}]
    # A write without secret parts has no key.
    assert "secrets" not in updates[1]
    (decoded,) = decode_row(_row(envelope, 1, 1))
    assert decoded == recorded
    assert decoded.stored_operation() == envelope["batches"][0]["operations"][0]["operation"]
    # Decoding copies the operation; the row's own JSON keeps its parts.
    assert envelope == stored


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(lambda write: write.update(secrets=[{"path": [], "kind": "mcp"}]), id="unknown kind"),
        pytest.param(lambda write: write.update(secrets=[{"path": ["missing"], "kind": "literal"}]), id="no such part"),
        pytest.param(lambda write: write.update(secrets=[{"path": [{"key": "r1"}], "kind": "literal"}]), id="selector"),
        pytest.param(lambda write: write.update(secrets=[{"path": [0], "kind": "literal"}]), id="index on object"),
        pytest.param(
            lambda write: write.update(
                secrets=[{"path": [], "kind": "literal"}, {"path": ["value"], "kind": "literal"}]
            ),
            id="part inside a part",
        ),
        pytest.param(lambda write: write.update(secrets=[{"path": [], "kind": "removed"}]), id="removed whole"),
        pytest.param(lambda write: write.update(secrets=[]), id="empty list"),
        pytest.param(lambda write: write.update(secrets=None), id="null"),
        pytest.param(lambda write: write.update({"secret": "literal"}), id="the old class"),
        pytest.param(lambda write: (write.update(op="delete_field"), write.pop("value")), id="on a delete"),
    ],
)
def test_malformed_secret_parts_are_damage(damage):
    envelope = encode_envelope([_with_secrets(1, uuid4())])
    damage(_first_write(envelope))

    _assert_corrupt(envelope, 1, 1, MALFORMED_OPERATION, 1)
