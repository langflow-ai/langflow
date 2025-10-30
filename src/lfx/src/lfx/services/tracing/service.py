"""Lightweight tracing service for LFX package."""

# ruff: noqa: ARG002
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from lfx.services.tracing.base import BaseTracingService

if TYPE_CHECKING:
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler

    from lfx.custom.custom_component.component import Component


class TracingService(BaseTracingService):
    """Minimal tracing service implementation for LFX.

    This is a lightweight implementation that logs trace events
    but does not integrate with external tracing services. For full
    tracing functionality (LangSmith, LangFuse, etc.), use the
    Langflow TracingService.
    """

    def __init__(self):
        """Initialize the tracing service."""
        super().__init__()
        self.deactivated = False
        self.set_ready()

    @property
    def name(self) -> str:
        """Service name identifier.

        Returns:
            str: The service name.
        """
        return "tracing_service"

    async def start_tracers(
        self,
        run_id: UUID,
        run_name: str,
        user_id: str | None,
        session_id: str | None,
        project_name: str | None = None,
    ) -> None:
        """Start tracers (minimal implementation - just logs).

        Args:
            run_id: Run identifier
            run_name: Run name
            user_id: User identifier
            session_id: Session identifier
            project_name: Project name
        """
        logger.debug(f"Trace started: {run_name}")

    async def end_tracers(self, outputs: dict, error: Exception | None = None) -> None:
        """End tracers (minimal implementation - just logs).

        Args:
            outputs: Output data
            error: Exception if any
        """
        logger.debug("Trace ended")

    @asynccontextmanager
    async def trace_component(
        self,
        component: Component,
        trace_name: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ):
        """Trace a component (minimal implementation).

        Args:
            component: Component to trace
            trace_name: Trace name
            inputs: Input data
            metadata: Metadata
        """
        logger.debug(f"Tracing component: {trace_name}")
        yield self

    def add_log(self, trace_name: str, log: Any) -> None:
        """Add a log entry (minimal implementation - just logs).

        Args:
            trace_name: Trace name
            log: Log data
        """
        logger.debug(f"Trace log: {trace_name}")

    def set_outputs(
        self,
        trace_name: str,
        outputs: dict[str, Any],
        output_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Set outputs (minimal implementation - noop).

        Args:
            trace_name: Trace name
            outputs: Output data
            output_metadata: Output metadata
        """
        logger.debug(f"Trace outputs set: {trace_name}")

    def get_langchain_callbacks(self) -> list[BaseCallbackHandler]:
        """Get LangChain callbacks (minimal implementation - empty list).

        Returns:
            Empty list (no callbacks in minimal implementation)
        """
        return []

    @property
    def project_name(self) -> str | None:
        """Get project name (minimal implementation - returns None).

        Returns:
            None
        """
        return None

    async def teardown(self) -> None:
        """Teardown the tracing service."""
        logger.debug("Tracing service teardown")
