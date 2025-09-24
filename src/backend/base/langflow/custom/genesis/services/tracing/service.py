# app/services/tracing/service.py
"""
Streaming-only tracing service for Genesis Studio Backend.
Integrates with AgentTracer for real-time observability.
"""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from langflow.services.base import Service
from loguru import logger

if TYPE_CHECKING:
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from langflow.custom.custom_component.component import Component
    from langflow.graph.vertex.base import Vertex
    from langflow.services.settings.service import SettingsService
    from langflow.services.tracing.base import BaseTracer
    from langflow.services.tracing.schema import Log


def _get_tracer():
    """Get the streaming tracer for real-time tracing."""
    try:
        from autonomize_observer.tracing import AgentTracer

        logger.info("📡 Using AgentTracer for real-time monitoring")
        return AgentTracer
    except ImportError:
        logger.warning(
            "AgentTracer not available - confluent-kafka not installed (optional)"
        )
        return None
    except Exception as e:
        logger.warning(f"AgentTracer initialization failed (non-critical): {e}")
        return None


# Context variables following Langflow's pattern
trace_context_var: ContextVar[TraceContext | None] = ContextVar(
    "trace_context", default=None
)
component_context_var: ContextVar[ComponentTraceContext | None] = ContextVar(
    "component_trace_context", default=None
)


class TraceContext:
    """Simple trace context for async tracing."""

    def __init__(
        self,
        run_id: UUID | None,
        run_name: str | None,
        project_name: str | None,
        user_id: str | None,
        session_id: str | None,
    ):
        self.run_id: UUID | None = run_id
        self.run_name: str | None = run_name
        self.project_name: str | None = project_name
        self.user_id: str | None = user_id
        self.session_id: str | None = session_id
        self.tracers: dict[str, BaseTracer] = {}
        # Keep these for Langflow compatibility
        self.all_inputs: dict[str, dict] = defaultdict(dict)
        self.all_outputs: dict[str, dict] = defaultdict(dict)

        # 🔗 Parent relationship tracking
        self.component_stack: list[str] = []  # Stack of active component IDs
        self.component_parents: dict[str, str | None] = (
            {}
        )  # component_id -> parent_component_id
        self.component_start_times: dict[str, float] = {}  # component_id -> start_time


class ComponentTraceContext:
    """Context for a component trace."""

    def __init__(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        vertex: "Vertex",
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ):
        self.trace_id = trace_id
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.vertex = vertex
        self.inputs = inputs
        self.inputs_metadata = metadata or {}
        self.outputs: dict[str, dict] = defaultdict(dict)
        self.outputs_metadata: dict[str, dict] = defaultdict(dict)
        self.logs: dict[str, list[Log]] = defaultdict(list)


class TracingService(Service):
    """
    Streaming-only tracing service for Genesis Studio Backend.

    This service provides:
    - Ultra-low latency tracing (~1-2ms per component)
    - Real-time streaming of trace events
    - Zero memory accumulation
    - Infinite scalability with AgentTracer
    """

    name = "tracing_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self.deactivated = self.settings_service.settings.deactivate_tracing
        self._tracing_config = None
        self._initialize_tracing_config()

    def _initialize_tracing_config(self):
        """Initialize streaming tracing configuration from settings."""
        if self.deactivated:
            return

        try:
            # Import config here to avoid circular imports
            from src.backend.base.langflow.custom.genesis.core.config import settings

            if (
                settings.AUTONOMIZE_TRACING_ENABLED
                and settings.AUTONOMIZE_KAFKA_BROKERS
            ):
                # Use streaming topic
                streaming_topic = getattr(
                    settings,
                    "AUTONOMIZE_KAFKA_STREAMING_TOPIC",
                    "genesis-traces-streaming",
                )

                self._tracing_config = {
                    "kafka_bootstrap_servers": settings.kafka_brokers_clean,
                    "kafka_username": settings.kafka_username_clean,
                    "kafka_password": (
                        settings.AUTONOMIZE_KAFKA_PASSWORD.get_secret_value()
                        if settings.AUTONOMIZE_KAFKA_PASSWORD
                        else None
                    ),
                    "security_protocol": settings.kafka_security_protocol_clean,
                    "sasl_mechanism": settings.kafka_mechanism_clean,
                    "kafka_topic": settings._strip_quotes(streaming_topic),
                }
                logger.info(
                    f"✅ Streaming tracing configured with topic: '{streaming_topic}'"
                )
            else:
                logger.info("Streaming tracing disabled or not configured")
        except Exception as e:
            logger.warning(f"Failed to initialize streaming tracing configuration: {e}")

    def _initialize_tracer(self, trace_context: TraceContext) -> None:
        """Initialize the streaming tracer with authentication."""
        if self.deactivated or not self._tracing_config:
            return

        try:
            tracer_class = _get_tracer()
            if not tracer_class:
                logger.warning(
                    "AgentTracer not available - tracing disabled (non-critical)"
                )
                return

            # Create tracer instance
            tracer = tracer_class(
                trace_name=trace_context.run_name,
                trace_id=trace_context.run_id,
                flow_id=str(trace_context.run_id),
                project_name=trace_context.project_name,
                user_id=trace_context.user_id,
                session_id=trace_context.session_id,
                **self._tracing_config,  # Pass all tracing config parameters
            )

            # AgentTracer requires start_trace()
            tracer.start_trace()
            logger.info("✅ Streaming trace started")

            trace_context.tracers["autonomize"] = tracer
            logger.info("✅ AgentTracer initialized")

        except Exception as e:
            logger.warning(f"Failed to initialize AgentTracer (non-critical): {e}")

    async def start_tracers(
        self,
        run_id: UUID,
        run_name: str,
        user_id: str | None,
        session_id: str | None,
        project_name: str | None = None,
    ) -> None:
        """Start a trace for a graph run."""
        if self.deactivated:
            return

        try:
            project_name = project_name or os.getenv(
                "AUTONOMIZE_EXPERIMENT_NAME", "GenesisStudio"
            )
            trace_context = TraceContext(
                run_id, run_name, project_name, user_id, session_id
            )
            trace_context_var.set(trace_context)

            # Initialize tracer
            self._initialize_tracer(trace_context)

        except Exception as e:
            logger.debug(f"Error initializing tracers: {e}")

    def _end_all_tracers_async(
        self, trace_context: TraceContext, outputs: dict, error: Exception | None = None
    ) -> None:
        """End all tracers asynchronously in background."""

        async def async_end_tracers():
            """Background task to end tracers without blocking."""
            for tracer in trace_context.tracers.values():
                if tracer.ready:
                    try:
                        # Run tracer.end() in thread pool to avoid blocking
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None,
                            tracer.end,
                            trace_context.all_inputs,
                            trace_context.all_outputs,
                            error,
                            outputs,
                        )
                    except Exception as e:
                        logger.error(f"Error ending tracer: {e}")

        # Fire and forget - don't wait for completion
        asyncio.create_task(async_end_tracers())

    async def end_tracers(self, outputs: dict, error: Exception | None = None) -> None:
        """End the trace for a graph run - now truly async."""
        if self.deactivated:
            return

        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called end_tracers but no trace context found"
            raise RuntimeError(msg)

        # End tracers asynchronously without blocking the response
        self._end_all_tracers_async(trace_context, outputs, error)

    @staticmethod
    def _cleanup_inputs(inputs: dict[str, Any]):
        """Clean sensitive data from inputs."""
        inputs = inputs.copy()
        for key in inputs:
            if "api_key" in key:
                inputs[key] = "*****"
        return inputs

    def _start_component_traces(
        self,
        component_trace_context: ComponentTraceContext,
        trace_context: TraceContext,
    ) -> None:
        """Start component traces with parent relationship tracking."""
        import time

        inputs = self._cleanup_inputs(component_trace_context.inputs)
        component_trace_context.inputs = inputs
        component_trace_context.inputs_metadata = (
            component_trace_context.inputs_metadata or {}
        )

        component_id = component_trace_context.trace_id

        # 🔗 Determine parent component based on execution stack
        parent_id = None
        if trace_context.component_stack:
            # Parent is the most recent component on the stack
            parent_id = trace_context.component_stack[-1]
            logger.debug(
                f"🔗 Setting parent {parent_id} for {component_trace_context.trace_name}"
            )

        # Record parent relationship and timing
        trace_context.component_parents[component_id] = parent_id
        trace_context.component_start_times[component_id] = time.time()

        # Add current component to the execution stack
        trace_context.component_stack.append(component_id)

        # Call add_trace with parent information
        for tracer in trace_context.tracers.values():
            if not tracer.ready:
                continue
            try:
                # Check if tracer supports parent_id parameter
                if (
                    hasattr(tracer.add_trace, "__code__")
                    and "parent_id" in tracer.add_trace.__code__.co_varnames
                ):
                    tracer.add_trace(
                        component_trace_context.trace_id,
                        component_trace_context.trace_name,
                        component_trace_context.trace_type,
                        inputs,
                        component_trace_context.inputs_metadata,
                        component_trace_context.vertex,
                        parent_id,  # Pass parent relationship
                    )
                else:
                    # Fallback for tracers that don't support parent_id
                    tracer.add_trace(
                        component_trace_context.trace_id,
                        component_trace_context.trace_name,
                        component_trace_context.trace_type,
                        inputs,
                        component_trace_context.inputs_metadata,
                        component_trace_context.vertex,
                    )
            except Exception:
                logger.exception(
                    f"Error starting trace {component_trace_context.trace_name}"
                )

    def _end_component_traces(
        self,
        component_trace_context: ComponentTraceContext,
        trace_context: TraceContext,
        error: Exception | None = None,
    ) -> None:
        """End component traces and update execution stack."""
        component_id = component_trace_context.trace_id

        # 🔗 Remove component from execution stack
        if component_id in trace_context.component_stack:
            trace_context.component_stack.remove(component_id)
            logger.debug(
                f"🔗 Removed {component_trace_context.trace_name} from execution stack"
            )

        for tracer in trace_context.tracers.values():
            if tracer.ready:
                try:
                    tracer.end_trace(
                        trace_id=component_trace_context.trace_id,
                        trace_name=component_trace_context.trace_name,
                        outputs=trace_context.all_outputs[
                            component_trace_context.trace_name
                        ],
                        error=error,
                        logs=component_trace_context.logs[
                            component_trace_context.trace_name
                        ],
                    )
                except Exception:
                    logger.exception(
                        f"Error ending trace {component_trace_context.trace_name}"
                    )

    @asynccontextmanager
    async def trace_component(
        self,
        component: Component,
        trace_name: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ):
        """Trace a component using high-performance async capabilities."""
        if self.deactivated:
            yield self
            return

        trace_id = trace_name
        if component._vertex:
            trace_id = component._vertex.id
        trace_type = component.trace_type

        component_trace_context = ComponentTraceContext(
            trace_id, trace_name, trace_type, component._vertex, inputs, metadata
        )
        component_context_var.set(component_trace_context)

        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called trace_component but no trace context found"
            raise RuntimeError(msg)

        trace_context.all_inputs[trace_name] |= inputs or {}

        # Start component traces (async handled by tracer)
        self._start_component_traces(component_trace_context, trace_context)

        try:
            yield self
        except Exception as e:
            # End traces with error (async handled by tracer)
            self._end_component_traces(component_trace_context, trace_context, e)
            raise
        else:
            # End traces successfully (async handled by tracer)
            self._end_component_traces(component_trace_context, trace_context, None)

    @property
    def project_name(self):
        """Get project name from context."""
        if self.deactivated:
            return os.getenv("AUTONOMIZE_EXPERIMENT_NAME", "GenesisStudio")
        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called project_name but no trace context found"
            raise RuntimeError(msg)
        return trace_context.project_name

    def add_log(self, trace_name: str, log: Log) -> None:
        """Add a log to the current component trace context."""
        if self.deactivated:
            return
        component_context = component_context_var.get()
        if component_context is None:
            msg = "called add_log but no component context found"
            raise RuntimeError(msg)
        component_context.logs[trace_name].append(log)

    def set_outputs(
        self,
        trace_name: str,
        outputs: dict[str, Any],
        output_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Set the outputs for the current component trace context."""
        if self.deactivated:
            return
        component_context = component_context_var.get()
        if component_context is None:
            msg = "called set_outputs but no component context found"
            raise RuntimeError(msg)
        component_context.outputs[trace_name] |= outputs or {}
        component_context.outputs_metadata[trace_name] |= output_metadata or {}
        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called set_outputs but no trace context found"
            raise RuntimeError(msg)
        trace_context.all_outputs[trace_name] |= outputs or {}

    def get_tracer(self, tracer_name: str) -> BaseTracer | None:
        """Get a specific tracer by name."""
        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called get_tracer but no trace context found"
            raise RuntimeError(msg)
        return trace_context.tracers.get(tracer_name)

    def get_langchain_callbacks(self) -> list[BaseCallbackHandler]:
        """Get LangChain callbacks from all ready tracers."""
        if self.deactivated:
            return []
        callbacks = []
        trace_context = trace_context_var.get()
        if trace_context is None:
            msg = "called get_langchain_callbacks but no trace context found"
            raise RuntimeError(msg)
        for tracer in trace_context.tracers.values():
            if not tracer.ready:
                continue
            langchain_callback = tracer.get_langchain_callback()
            if langchain_callback:
                callbacks.append(langchain_callback)
        return callbacks
