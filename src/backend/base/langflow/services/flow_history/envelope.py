"""The versioned envelope stored in ``flow_operation.ops``.

::

    {
      "version": 1,
      "batches": [
        {
          "request_id": "<uuid>",
          "actor_user_id": "<uuid>",
          "operations": [
            {"revision": 42, "cause": "upgrade_component", "operation": {...}},
            {"revision": 43, "operation": {...}}
          ]
        }
      ]
    }

A row holds one batch per request, in revision order. Each batch names the
authenticated actor and the request that produced its operations, so a row
never implies a single author. Today each write fills its own rows, so a row
holds one request; a queued multiplayer write can put several requests from
several users in one row. A request that spans rows has one batch in each.

The operation order is canonical: operation ``i`` of a row starting at revision
``s`` carries revision ``s + i``, counted across the row's batches. ``cause`` is
optional: what made the write (an upgrade, a code edit, a restore, a file sync,
the assistant), a display hint the history uses to group a write's operations.
Nothing checks it.

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

# Kinds of damage a stored row can show.
UNSUPPORTED_ENVELOPE = "unsupported operation envelope"
COUNT_MISMATCH = "operation count does not match the row's revision range"
REVISION_OUT_OF_ORDER = "operation revision out of order"
MALFORMED_OPERATION = "malformed operation"
MALFORMED_BATCH = "malformed request batch"
REQUEST_REPEATED = "a request has more than one batch in the row"


@dataclass(frozen=True)
class RecordedOperation:
    """One accepted operation and everything recorded about it."""

    revision: int
    actor_user_id: UUID
    request_id: UUID
    operation: FlowOperation
    cause: str | None = None

    def to_json(self) -> dict[str, Any]:
        """Return the operation's element inside its request's batch."""
        element: dict[str, Any] = {"revision": self.revision}
        if self.cause is not None:
            element["cause"] = self.cause
        element["operation"] = dump_flow_operation(self.operation)
        return element


def batch_header(request_id: UUID, actor_user_id: UUID) -> dict[str, Any]:
    """Return an empty batch for one request."""
    return {"request_id": str(request_id), "actor_user_id": str(actor_user_id), "operations": []}


def encode_envelope(operations: list[RecordedOperation]) -> dict[str, Any]:
    """Group a row's operations into one batch per request, in revision order."""
    batches: list[dict[str, Any]] = []
    for operation in operations:
        if not batches or batches[-1]["request_id"] != str(operation.request_id):
            batches.append(batch_header(operation.request_id, operation.actor_user_id))
        elif batches[-1]["actor_user_id"] != str(operation.actor_user_id):
            msg = f"request {operation.request_id} has operations from two actors"
            raise ValueError(msg)
        batches[-1]["operations"].append(operation.to_json())
    return {"version": ENVELOPE_VERSION, "batches": batches}


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
    batches = envelope.get("batches")
    if not isinstance(batches, list):
        raise corrupt(UNSUPPORTED_ENVELOPE, row.start_revision)

    decoded: list[RecordedOperation] = []
    seen_requests: set[UUID] = set()
    for batch in batches:
        first_revision = row.start_revision + len(decoded)
        if not isinstance(batch, dict) or not isinstance(batch.get("operations"), list) or not batch["operations"]:
            raise corrupt(MALFORMED_BATCH, first_revision)
        try:
            request_id = UUID(str(batch["request_id"]))
            actor_user_id = UUID(str(batch["actor_user_id"]))
        except (KeyError, ValueError) as exc:
            raise corrupt(MALFORMED_BATCH, first_revision) from exc
        # A request's operations are contiguous, so a row holds one batch per request.
        if request_id in seen_requests:
            raise corrupt(REQUEST_REPEATED, first_revision)
        seen_requests.add(request_id)

        for element in batch["operations"]:
            expected_revision = row.start_revision + len(decoded)
            if not isinstance(element, dict) or element.get("revision") != expected_revision:
                raise corrupt(REVISION_OUT_OF_ORDER, expected_revision)
            try:
                operation = parse_flow_operation(element["operation"])
            except (KeyError, FlowOperationError) as exc:
                raise corrupt(MALFORMED_OPERATION, expected_revision) from exc
            cause = element.get("cause")
            if cause is not None and not isinstance(cause, str):
                raise corrupt(MALFORMED_OPERATION, expected_revision)
            decoded.append(
                RecordedOperation(
                    revision=expected_revision,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                    operation=operation,
                    cause=cause,
                )
            )

    if len(decoded) != row.end_revision - row.start_revision + 1:
        raise corrupt(COUNT_MISMATCH, row.start_revision)
    return decoded
