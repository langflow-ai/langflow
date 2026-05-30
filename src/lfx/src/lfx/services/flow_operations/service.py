"""Service boundary for flow operation application."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from lfx.services.base import Service
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.flow_operations.apply import FlowOperationsApplyResult
    from lfx.services.flow_operations.ops import FlowOperation


class BaseFlowOperationService(Service):
    """Interface for applying collaborative editing operation batches."""

    name = ServiceType.FLOW_OPERATIONS_SERVICE.value

    @abstractmethod
    def apply(
        self,
        base_flow: dict[str, Any],
        operations: list[FlowOperation],
    ) -> FlowOperationsApplyResult:
        """Apply a submitted operation batch to a base flow JSON."""

    async def teardown(self) -> None:
        """No resources to release in the base implementation."""
