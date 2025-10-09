"""Callback interfaces for logging and monitoring graph execution.

This module defines callback protocols that allow external systems to
monitor graph execution without coupling the graph to specific implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.graph.vertex.base import Vertex


class TransactionCallback(Protocol):
    """Protocol for transaction logging callbacks."""

    def __call__(
        self,
        flow_id: str | UUID,
        source: Vertex,
        status: str,
        target: Vertex | None = None,
        error: Any = None,
    ) -> None:
        """Called when a transaction should be logged.

        Args:
            flow_id: The flow identifier
            source: Source vertex
            status: Transaction status
            target: Optional target vertex
            error: Optional error information
        """
        ...


class VertexBuildCallback(Protocol):
    """Protocol for vertex build logging callbacks."""

    def __call__(
        self,
        flow_id: str | UUID,
        vertex_id: str,
        *,
        valid: bool,
        params: dict[str, Any],
        result_dict: dict[str, Any],
        artifacts: dict[str, Any] | None = None,
    ) -> None:
        """Called when a vertex build should be logged.

        Args:
            flow_id: The flow identifier
            vertex_id: ID of the vertex that was built
            valid: Whether the build was valid
            params: Build parameters
            result_dict: Build results
            artifacts: Optional build artifacts
        """
        ...


class LogCallbacks:
    """Container for all logging callbacks."""

    def __init__(
        self,
        transaction_callback: TransactionCallback | None = None,
        vertex_build_callback: VertexBuildCallback | None = None,
    ) -> None:
        """Initialize the callbacks container.

        Args:
            transaction_callback: Optional callback for transaction logging
            vertex_build_callback: Optional callback for vertex build logging
        """
        self.transaction = transaction_callback
        self.vertex_build = vertex_build_callback

    def log_transaction(
        self,
        flow_id: str | UUID,
        source: Vertex,
        status: str,
        target: Vertex | None = None,
        error: Any = None,
    ) -> None:
        """Log a transaction if callback is set."""
        if self.transaction:
            self.transaction(flow_id, source, status, target, error)

    def log_vertex_build(
        self,
        flow_id: str | UUID,
        vertex_id: str,
        *,
        valid: bool,
        params: dict[str, Any],
        result_dict: dict[str, Any],
        artifacts: dict[str, Any] | None = None,
    ) -> None:
        """Log a vertex build if callback is set."""
        if self.vertex_build:
            self.vertex_build(
                flow_id,
                vertex_id,
                valid=valid,
                params=params,
                result_dict=result_dict,
                artifacts=artifacts,
            )
