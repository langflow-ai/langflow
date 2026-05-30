"""Factory for the flow operation service."""

from __future__ import annotations

from lfx.services.factory import ServiceFactory
from lfx.services.flow_operations.python import PythonFlowOperationService


class FlowOperationServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        # TODO: Rust-based implementation instead of the default Python implementation.
        super().__init__()
        self.service_class = PythonFlowOperationService

    def create(self, **_kwargs) -> PythonFlowOperationService:
        return PythonFlowOperationService()
