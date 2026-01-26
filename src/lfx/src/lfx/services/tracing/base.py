"""Abstract base class for tracing services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from lfx.services.base import Service

if TYPE_CHECKING:
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler

    from lfx.custom.custom_component.component import Component


class BaseTracingService(Service, ABC):
    """Abstract base class for tracing services.

    Defines the minimal interface that all tracing service implementations
    must provide, whether minimal (LFX) or full-featured (Langflow).
    """

    @abstractmethod
    def __init__(self):
        """Initialize the tracing service."""
        super().__init__()

    @abstractmethod
    async def start_tracers(
        self,
        run_id: UUID,
        run_name: str,
        user_id: str | None,
        session_id: str | None,
        project_name: str | None = None,
    ) -> None:
        """Start tracers for a graph run.

        Args:
            run_id: Unique identifier for the run
            run_name: Name of the run
            user_id: User identifier (optional)
            session_id: Session identifier (optional)
            project_name: Project name (optional)
        """

    @abstractmethod
    async def end_tracers(self, outputs: dict, error: Exception | None = None) -> None:
        """End tracers for a graph run.

        Args:
            outputs: Output data from the run
            error: Exception if run failed (optional)
        """

    @abstractmethod
    @asynccontextmanager
    async def trace_component(
        self,
        component: Component,
        trace_name: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ):
        """Context manager for tracing a component execution.

        Args:
            component: The component being traced
            trace_name: Name for the trace
            inputs: Input data to the component
            metadata: Additional metadata (optional)

        Yields:
            Self for method chaining
        """

    @abstractmethod
    def add_log(self, trace_name: str, log: Any) -> None:
        """Add a log entry to the current trace.

        Args:
            trace_name: Name of the trace
            log: Log data to add
        """

    @abstractmethod
    def set_outputs(
        self,
        trace_name: str,
        outputs: dict[str, Any],
        output_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Set outputs for the current trace.

        Args:
            trace_name: Name of the trace
            outputs: Output data
            output_metadata: Additional output metadata (optional)
        """

    @abstractmethod
    def get_langchain_callbacks(self) -> list[BaseCallbackHandler]:
        """Get LangChain callback handlers for tracing.

        Returns:
            List of callback handlers
        """

    @property
    @abstractmethod
    def project_name(self) -> str | None:
        """Get the current project name.

        Returns:
            Project name or None if not set
        """
