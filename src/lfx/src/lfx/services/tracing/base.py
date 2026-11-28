"""Abstract base class for tracing services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import ExitStack, asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any

from lfx.services.base import Service

if TYPE_CHECKING:
    from uuid import UUID

    from langchain_core.callbacks.base import BaseCallbackHandler

    from lfx.custom.custom_component.component import Component


def _callback_handlers(callbacks: Any) -> Any:
    """Return handlers from either a callback list or LangChain manager."""
    if callbacks is None:
        return ()
    handlers = getattr(callbacks, "handlers", None)
    return callbacks if handlers is None else handlers


@contextmanager
def callback_invocation_scope(callbacks: Any):
    """Enter optional tracer scopes for the duration of a model invocation."""
    with ExitStack() as stack:
        for callback in _callback_handlers(callbacks):
            scope_factory = getattr(callback, "langflow_invocation_scope", None)
            if scope_factory is not None:
                stack.enter_context(scope_factory())
        yield


class ScopedAsyncIterator:
    """Keep callback invocation scopes open while an async stream is consumed."""

    def __init__(self, iterator, callbacks: list[BaseCallbackHandler]):
        self._iterator = iterator
        self._callbacks = callbacks
        self._stack: ExitStack | None = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._stack is None:
            self._stack = ExitStack()
            for callback in _callback_handlers(self._callbacks):
                scope_factory = getattr(callback, "langflow_invocation_scope", None)
                if scope_factory is not None:
                    self._stack.enter_context(scope_factory())
        try:
            return await self._iterator.__anext__()
        except BaseException:
            self._stack.close()
            self._stack = None
            raise

    async def aclose(self):
        """Close the wrapped iterator and restore any active callback scopes."""
        try:
            aclose = getattr(self._iterator, "aclose", None)
            if aclose is not None:
                await aclose()
        finally:
            if self._stack is not None:
                self._stack.close()
                self._stack = None


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
        flow_id: str | None = None,
        tracing_user_id: str | None = None,
    ) -> None:
        """Start tracers for a graph run.

        Args:
            run_id: Unique identifier for the run
            run_name: Name of the run
            user_id: Authenticated Langflow user identifier (optional)
            session_id: Session identifier (optional)
            project_name: Project name (optional)
            flow_id: Flow identifier (optional)
            tracing_user_id: Optional caller-supplied label forwarded to tracing
                providers. Does not change ``trace.userId`` (which stays as the
                auth ``user_id``); each provider decides how to surface it (e.g.
                LangFuseTracer stamps it under ``langflow.tracing_user_id`` in
                trace metadata).
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
