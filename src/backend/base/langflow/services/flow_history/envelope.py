"""The versioned envelope stored in ``flow_operation.ops``.

::

    {
      "version": 1,
      "operations": [
        {
          "revision": 42,
          "actor_user_id": "<uuid>",
          "request_id": "<uuid>",
          "cause": "upgrade_component",
          "operation": {...}
        }
      ]
    }

The array order is canonical: element ``i`` of a row starting at revision ``s``
carries revision ``s + i``. Every element names the authenticated actor and the
request that produced it, so a row never implies a single author. ``cause``
is optional: what made the write (an upgrade, a code edit, a restore, a file
sync, the assistant), a display hint the history uses to group a write's
operations. Nothing checks it.

Decoding validates all of it; a row that does not match is corruption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.services.flow_operations import FlowOperation, FlowOperationError, dump_flow_operation, parse_flow_operation

from langflow.services.flow_history.errors import FlowHistoryCorruptionError

if TYPE_CHECKING:
    from langflow.services.database.models.flow_operation import FlowOperation as FlowOperationRow

ENVELOPE_VERSION = 1

# Causes the server sets on its own writes. The editor sends its own
# (``upgrade_component``, ``edit_code``) with the write options.
FILE_SYNC_CAUSE = "file_sync"
ASSISTANT_CAUSE = "assistant"
RESTORE_CAUSE = "restore"

# Kinds of damage a stored row can show.
UNSUPPORTED_ENVELOPE = "unsupported operation envelope"
COUNT_MISMATCH = "operation count does not match the row's revision range"
REVISION_OUT_OF_ORDER = "operation revision out of order"
MALFORMED_OPERATION = "malformed operation"
REQUEST_NOT_CONTIGUOUS = "a request's operations are not contiguous"


@dataclass(frozen=True)
class RecordedOperation:
    """One accepted operation and everything recorded about it."""

    revision: int
    actor_user_id: UUID
    request_id: UUID
    operation: FlowOperation
    cause: str | None = None

    def to_json(self) -> dict[str, Any]:
        element: dict[str, Any] = {
            "revision": self.revision,
            "actor_user_id": str(self.actor_user_id),
            "request_id": str(self.request_id),
        }
        if self.cause is not None:
            element["cause"] = self.cause
        element["operation"] = dump_flow_operation(self.operation)
        return element


def encode_envelope(operations: list[RecordedOperation]) -> dict[str, Any]:
    return {"version": ENVELOPE_VERSION, "operations": [operation.to_json() for operation in operations]}


def distinct_actor_ids(operations: list[RecordedOperation]) -> list[str]:
    """Return the row's distinct actors, sorted so the list is deterministic."""
    return sorted({str(operation.actor_user_id) for operation in operations})


def request_ids_in_order(operations: list[RecordedOperation]) -> list[str]:
    """Return one entry per request in the row, in revision order."""
    request_ids: list[str] = []
    for operation in operations:
        request_id = str(operation.request_id)
        if not request_ids or request_ids[-1] != request_id:
            request_ids.append(request_id)
    return request_ids


def decode_row(row: FlowOperationRow) -> list[RecordedOperation]:
    """Decode and validate a stored row's envelope against its revision range."""

    def corrupt(kind: str, revision: int | None = None) -> FlowHistoryCorruptionError:
        return FlowHistoryCorruptionError(row.flow_id, kind, revision=revision)

    envelope = row.ops
    if not isinstance(envelope, dict) or envelope.get("version") != ENVELOPE_VERSION:
        raise corrupt(UNSUPPORTED_ENVELOPE, row.start_revision)
    elements = envelope.get("operations")
    if not isinstance(elements, list) or len(elements) != row.end_revision - row.start_revision + 1:
        raise corrupt(COUNT_MISMATCH, row.start_revision)

    decoded: list[RecordedOperation] = []
    finished_requests: set[UUID] = set()
    for index, element in enumerate(elements):
        expected_revision = row.start_revision + index
        if not isinstance(element, dict) or element.get("revision") != expected_revision:
            raise corrupt(REVISION_OUT_OF_ORDER, expected_revision)
        try:
            actor_user_id = UUID(str(element["actor_user_id"]))
            request_id = UUID(str(element["request_id"]))
            operation = parse_flow_operation(element["operation"])
        except (KeyError, ValueError, FlowOperationError) as exc:
            raise corrupt(MALFORMED_OPERATION, expected_revision) from exc
        cause = element.get("cause")
        if cause is not None and not isinstance(cause, str):
            raise corrupt(MALFORMED_OPERATION, expected_revision)

        # A request's operations are contiguous: once another request starts,
        # an earlier one cannot resume.
        if decoded and decoded[-1].request_id != request_id:
            finished_requests.add(decoded[-1].request_id)
        if request_id in finished_requests:
            raise corrupt(REQUEST_NOT_CONTIGUOUS, expected_revision)

        decoded.append(
            RecordedOperation(
                revision=expected_revision,
                actor_user_id=actor_user_id,
                request_id=request_id,
                operation=operation,
                cause=cause,
            )
        )
    return decoded
