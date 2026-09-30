"""State shared by the erase steps of one request."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

    from langflow.services.data_subjects.identity import EndUserKeys
    from langflow.services.memory_base.flow_cleanup import FlowMemoryBaseCleanup


@dataclass
class EraseContext:
    request_id: UUID
    subject_user_id: UUID
    username: str | None = None
    end_user: EndUserKeys | None = None
    scope_flow_ids: tuple[UUID, ...] = ()
    memory_base_cleanups: list[FlowMemoryBaseCleanup] = field(default_factory=list)
    cursor: dict[str, Any] = field(default_factory=dict)

    @property
    def is_end_user(self) -> bool:
        return self.end_user is not None
