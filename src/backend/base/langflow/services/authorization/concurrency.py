"""Shared strong-ETag and optimistic revision helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from langflow.services.authorization.collaboration import discover_collaboration_capabilities

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class RevisionPreconditionError(Exception):
    """Stable failure translated by the owning API boundary."""

    status_code: int
    code: str
    message: str

    @property
    def detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def strong_etag(resource_type: str, resource_id: UUID, revision: int) -> str:
    """Return the canonical quoted strong ETag for a mutable resource."""
    return f'"{resource_type}:{resource_id}:{revision}"'


def require_revision_precondition(
    *,
    resource_type: str,
    resource_id: UUID,
    current_revision: int,
    if_match: str | None,
    required: bool,
    changed_code: str,
) -> None:
    """Validate an optional or mandatory ``If-Match`` against locked state.

    Supplied conditions are always honored. Wildcards, weak validators, and
    lists are rejected because none identifies the revision the caller read.
    """
    if if_match is None:
        if required:
            raise RevisionPreconditionError(
                status_code=428,
                code="PRECONDITION_REQUIRED",
                message="An If-Match header with the observed revision is required.",
            )
        return

    supplied = if_match.strip()
    expected = strong_etag(resource_type, resource_id, current_revision)
    if supplied.startswith("W/") or "," in supplied or supplied != expected:
        raise RevisionPreconditionError(
            status_code=412,
            code=changed_code,
            message="The resource changed after it was read. Refresh and try again.",
        )


async def conditional_writes_required() -> bool:
    """Return the verified active contract; probe failures intentionally raise."""
    capabilities = await discover_collaboration_capabilities()
    return capabilities.conditional_writes_required


__all__ = [
    "RevisionPreconditionError",
    "conditional_writes_required",
    "require_revision_precondition",
    "strong_etag",
]
