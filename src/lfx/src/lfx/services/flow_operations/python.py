"""Default Python implementation of the flow operation service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations.apply import FlowOperationsApplyResult, apply_flow_operations
from lfx.services.flow_operations.diff import DerivedFlowOperations, derive_flow_operations
from lfx.services.flow_operations.service import BaseFlowOperationService

if TYPE_CHECKING:
    from lfx.services.flow_operations.ops import FlowOperation


class PythonFlowOperationService(BaseFlowOperationService):
    """Default Python flow operation utility."""

    def apply(
        self,
        base_flow: dict[str, Any],
        operations: list[FlowOperation],
    ) -> FlowOperationsApplyResult:
        return apply_flow_operations(base_flow, operations)

    def derive(self, base_flow: dict[str, Any], target_flow: dict[str, Any]) -> DerivedFlowOperations:
        return derive_flow_operations(base_flow, target_flow)
