"""Errors raised while recording or replaying a flow's history."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from lfx.services.flow_operations import GraphViolation


class FlowHistoryError(Exception):
    """Base error for flow history."""

    code = "FLOW_HISTORY_ERROR"


class FlowRevisionMismatchError(FlowHistoryError):
    """The stored graph is not the graph its claimed revision replays to.

    It was changed outside the write path. Nothing is written; the caller can
    read the flow, keep a copy, and resend with ``repair_revision_mismatch``.
    """

    code = "FLOW_REVISION_MISMATCH"

    def __init__(self, flow_id: UUID, *, current_revision: int, latest_revision: int) -> None:
        super().__init__(f"Stored data of flow {flow_id} does not match its revision {current_revision}")
        self.flow_id = flow_id
        self.current_revision = current_revision
        self.latest_revision = latest_revision


class FlowVersionConflictError(FlowHistoryError):
    """The write's ``If-Match`` names a version someone has since replaced.

    Multi-edit safety's conflict: the caller resolves it in the conflict
    dialog. Raised only when the submitted graph differs from the stored one;
    a stale token whose graph already equals the stored graph loses nothing.
    """

    code = "flow_version_conflict"

    def __init__(
        self,
        flow_id: UUID,
        *,
        expected: UUID,
        current: UUID | None,
        author_id: UUID | None,
        author_name: str | None,
        modified_at: datetime | None,
    ) -> None:
        super().__init__(f"Flow {flow_id} was changed after version {expected} was read")
        self.flow_id = flow_id
        self.expected = expected
        self.current = current
        self.author_id = author_id
        self.author_name = author_name
        self.modified_at = modified_at


class FlowGraphInvalidError(FlowHistoryError):
    """A graph breaks the flow graph rules and repair was not requested."""

    code = "FLOW_GRAPH_INVALID"

    def __init__(self, violations: list[GraphViolation], *, graph: Literal["stored", "submitted"]) -> None:
        super().__init__(f"The {graph} flow graph breaks {len(violations)} flow graph rule(s)")
        self.graph = graph
        self.violations = violations


class FlowRevisionNotFoundError(FlowHistoryError):
    """The revision was never recorded for this flow."""

    code = "FLOW_REVISION_NOT_FOUND"


class FlowHistoryCorruptionError(FlowHistoryError):
    """Replay found the history damaged: a gap, a bad row, or a failed hash.

    Under the normal write path this cannot happen. It means someone wrote to
    the database outside the API. The message names the flow, revision and
    kind of damage, never graph values.
    """

    code = "FLOW_HISTORY_CORRUPT"

    def __init__(self, flow_id: UUID, kind: str, *, revision: int | None = None) -> None:
        location = f" at revision {revision}" if revision is not None else ""
        super().__init__(f"History of flow {flow_id} is damaged{location}: {kind}")
        self.flow_id = flow_id
        self.kind = kind
        self.revision = revision
