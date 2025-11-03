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


def _get_agent_tracer():
    """Get the AgentTracer for real-time tracing."""
    try:
        from autonomize_observer.tracing import AgentTracer
        logger.info("🔡 Using AgentTracer for real-time monitoring")
        return AgentTracer
    except ImportError:
        logger.warning("AgentTracer not available - autonomize_observer not installed (optional)")
        return None
    except Exception as e:
        logger.warning(f"AgentTracer initialization failed (non-critical): {e}")
        return None


def _get_autonomize_tracer():
    """Get the custom AutonomizeTracer."""
    try:
        from langflow.services.tracing.autonomize_tracing.autonomize_tracer import AutonomizeTracer
        logger.info("🎯 Using AutonomizeTracer for custom tracing")
        return AutonomizeTracer
    except ImportError:
        logger.warning("AutonomizeTracer not available")
        return None
    except Exception as e:
        logger.warning(f"AutonomizeTracer initialization failed: {e}")
        return None


def _get_langsmith_tracer():
    from langflow.services.tracing.langsmith import LangSmithTracer
    return LangSmithTracer


def _get_langwatch_tracer():
    from langflow.services.tracing.langwatch import LangWatchTracer
    return LangWatchTracer


def _get_langfuse_tracer():
    from langflow.services.tracing.langfuse import LangFuseTracer
    return LangFuseTracer


def _get_arize_phoenix_tracer():
    from langflow.services.tracing.arize_phoenix import ArizePhoenixTracer
    return ArizePhoenixTracer


def _get_opik_tracer():
    from langflow.services.tracing.opik import OpikTracer
    return OpikTracer


def _get_traceloop_tracer():
    from langflow.services.tracing.traceloop import TraceloopTracer
    return TraceloopTracer


# Context variables following Langflow's pattern
trace_context_var: ContextVar[TraceContext | None] = ContextVar("trace_context", default=None)
component_context_var: ContextVar[ComponentTraceContext | None] = ContextVar("component_trace_context", default=None)


class TraceContext:
    """Simple trace context without queue complexity."""

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
        self.all_inputs: dict[str, dict] = defaultdict(dict)
        self.all_outputs: dict[str, dict] = defaultdict(dict)


class ComponentTraceContext:
    """Context for a component trace."""

    def __init__(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        vertex: Vertex | None,
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
        self.logs: dict[str, list[Log | dict[Any, Any]]] = defaultdict(list)


class TracingService(Service):
    """
    Simplified tracing service supporting multiple tracers without async queue complexity.
    
    Supports:
    - Standard Langflow tracers (LangSmith, LangFuse, etc.)
    - AgentTracer for real-time streaming
    - Custom AutonomizeTracer
    - Direct synchronous trace operations
    """

    name = "tracing_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self.deactivated = self.settings_service.settings.deactivate_tracing
        self._tracing_config = None
        self._initialize_tracing_config()

    def _initialize_tracing_config(self):
        """Initialize streaming tracing configuration from environment variables."""
        if self.deactivated:
            return

        try:
            # Read from environment variables
            autonomize_enabled = os.getenv("AUTONOMIZE_TRACING_ENABLED", "false").lower() == "true"
            kafka_brokers = os.getenv("AUTONOMIZE_KAFKA_BROKERS")
            kafka_topic = os.getenv("AUTONOMIZE_KAFKA_STREAMING_TOPIC", "genesis-traces-streaming")
            kafka_username = os.getenv("AUTONOMIZE_KAFKA_USERNAME")
            kafka_password = os.getenv("AUTONOMIZE_KAFKA_PASSWORD")
            kafka_security_protocol = os.getenv("AUTONOMIZE_KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
            kafka_mechanism = os.getenv("AUTONOMIZE_KAFKA_MECHANISM", "PLAIN")

            if autonomize_enabled and kafka_brokers:
                self._tracing_config = {
                    "kafka_bootstrap_servers": kafka_brokers.strip(),
                    "kafka_username": kafka_username.strip() if kafka_username else None,
                    "kafka_password": kafka_password.strip() if kafka_password else None,
                    "security_protocol": kafka_security_protocol.strip(),
                    "sasl_mechanism": kafka_mechanism.strip(),
                    "kafka_topic": kafka_topic.strip(),
                }
                logger.info(f"✅ Streaming tracing configured from env with topic: '{kafka_topic}'")
            else:
                logger.info("Streaming tracing disabled or missing env vars")

        except Exception as e:
            logger.warning(f"Failed to initialize streaming tracing configuration from env: {e}")

    def _initialize_standard_tracers(self, trace_context: TraceContext) -> None:
        """Initialize standard Langflow tracers."""
        tracer_configs = [
            ("langsmith", _get_langsmith_tracer, {}),
            ("langwatch", _get_langwatch_tracer, {}),
            ("langfuse", _get_langfuse_tracer, {"user_id": trace_context.user_id, "session_id": trace_context.session_id}),
            ("arize_phoenix", _get_arize_phoenix_tracer, {}),
            ("opik", _get_opik_tracer, {"user_id": trace_context.user_id, "session_id": trace_context.session_id}),
            ("traceloop", _get_traceloop_tracer, {"user_id": trace_context.user_id, "session_id": trace_context.session_id}),
        ]

        for tracer_name, tracer_getter, extra_kwargs in tracer_configs:
            try:
                tracer_class = tracer_getter()
                if tracer_class:
                    tracer = tracer_class(
                        trace_name=trace_context.run_name,
                        trace_type="chain",
                        project_name=trace_context.project_name,
                        trace_id=trace_context.run_id,
                        **extra_kwargs
                    )
                    if tracer.ready:
                        trace_context.tracers[tracer_name] = tracer
            except Exception as e:
                logger.debug(f"Failed to initialize {tracer_name}: {e}")

    def _initialize_agent_tracer(self, trace_context: TraceContext) -> None:
        """Initialize AgentTracer for real-time streaming."""
        try:
            tracer_class = _get_agent_tracer()
            if tracer_class and self._tracing_config:
                tracer = tracer_class(
                    trace_name=trace_context.run_name,
                    trace_id=trace_context.run_id,
                    flow_id=str(trace_context.run_id),
                    project_name=trace_context.project_name,
                    user_id=trace_context.user_id,
                    session_id=trace_context.session_id,
                    **self._tracing_config,
                )
                tracer.start_trace()
                trace_context.tracers["agent_tracer"] = tracer
                logger.info("✅ AgentTracer initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize AgentTracer: {e}")

    def _initialize_autonomize_tracer(self, trace_context: TraceContext) -> None:
        """Initialize custom AutonomizeTracer."""
        try:
            tracer_class = _get_autonomize_tracer()
            if tracer_class:
                tracer = tracer_class(
                    trace_name=trace_context.run_name,
                    trace_type="flow",
                    project_name=trace_context.project_name,
                    trace_id=trace_context.run_id,
                    user_id=trace_context.user_id,
                    session_id=trace_context.session_id,
                )
                if tracer.ready:
                    trace_context.tracers["autonomize"] = tracer
                    logger.info("✅ AutonomizeTracer initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize AutonomizeTracer: {e}")

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
            project_name = project_name or os.getenv("LANGCHAIN_PROJECT", "Langflow")
            trace_context = TraceContext(run_id, run_name, project_name, user_id, session_id)
            trace_context_var.set(trace_context)

            # Initialize all tracers
            self._initialize_standard_tracers(trace_context)
            self._initialize_agent_tracer(trace_context)
            self._initialize_autonomize_tracer(trace_context)

            active_tracers = [name for name, tracer in trace_context.tracers.items() if tracer.ready]
            logger.info(f"📊 Initialized {len(active_tracers)} active tracers: {active_tracers}")

        except Exception as e:
            logger.debug(f"Error initializing tracers: {e}")

    def _end_all_tracers_sync(self, trace_context: TraceContext, outputs: dict, error: Exception | None = None) -> None:
        """End all tracers synchronously."""
        for tracer_name, tracer in trace_context.tracers.items():
            if tracer.ready:
                try:
                    logger.debug(f"🏁 Ending {tracer_name} tracer")
                    tracer.end(
                        trace_context.all_inputs,
                        outputs=trace_context.all_outputs,
                        error=error,
                        metadata=outputs,
                    )
                except Exception as e:
                    logger.error(f"❌ Error ending {tracer_name} tracer: {e}")

    async def end_tracers(self, outputs: dict, error: Exception | None = None) -> None:
        """End the trace for a graph run."""
        if self.deactivated:
            return
            
        trace_context = trace_context_var.get()
        if trace_context is None:
            raise RuntimeError("called end_tracers but no trace context found")

        # Run tracer ending in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._end_all_tracers_sync, trace_context, outputs, error)

    @staticmethod
    def _cleanup_inputs(inputs: dict[str, Any]):
        """Clean sensitive data from inputs."""
        inputs = inputs.copy()
        sensitive_keywords = {"api_key", "password", "server_url"}

        def _mask(obj: Any):
            if isinstance(obj, dict):
                return {
                    k: "*****" if any(word in k.lower() for word in sensitive_keywords) else _mask(v)
                    for k, v in obj.items()
                }
            if isinstance(obj, list):
                return [_mask(i) for i in obj]
            return obj

        return _mask(inputs)

    def _start_component_traces(
        self,
        component_trace_context: ComponentTraceContext,
        trace_context: TraceContext,
    ) -> None:
        """Start component traces for all active tracers."""
        inputs = self._cleanup_inputs(component_trace_context.inputs)
        component_trace_context.inputs = inputs

        # Start traces for all active tracers
        for tracer_name, tracer in trace_context.tracers.items():
            if not tracer.ready:
                continue
            try:
                logger.debug(f"🔍 Starting {tracer_name} trace for {component_trace_context.trace_name}")
                
                tracer.add_trace(
                    component_trace_context.trace_id,
                    component_trace_context.trace_name,
                    component_trace_context.trace_type,
                    inputs,
                    component_trace_context.inputs_metadata,
                    component_trace_context.vertex,
                )
            except Exception as e:
                logger.exception(f"❌ Error starting {tracer_name} trace: {e}")

    def _end_component_traces(
        self,
        component_trace_context: ComponentTraceContext,
        trace_context: TraceContext,
        error: Exception | None = None,
    ) -> None:
        """End component traces for all active tracers."""
        for tracer_name, tracer in trace_context.tracers.items():
            if tracer.ready:
                try:
                    logger.debug(f"🏁 Ending {tracer_name} trace for {component_trace_context.trace_name}")
                    tracer.end_trace(
                        trace_id=component_trace_context.trace_id,
                        trace_name=component_trace_context.trace_name,
                        outputs=trace_context.all_outputs[component_trace_context.trace_name],
                        error=error,
                        logs=component_trace_context.logs[component_trace_context.trace_name],
                    )
                except Exception as e:
                    logger.exception(f"❌ Error ending {tracer_name} trace: {e}")

    @asynccontextmanager
    async def trace_component(
        self,
        component: Component,
        trace_name: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ):
        """Trace a component execution - simplified without queue."""
        if self.deactivated:
            yield self
            return

        trace_id = component._vertex.id if component._vertex else trace_name
        trace_type = component.trace_type
        
        component_trace_context = ComponentTraceContext(
            trace_id, trace_name, trace_type, component._vertex, inputs, metadata
        )
        component_context_var.set(component_trace_context)
        
        trace_context = trace_context_var.get()
        if trace_context is None:
            raise RuntimeError("called trace_component but no trace context found")

        trace_context.all_inputs[trace_name] |= inputs or {}

        # Start component traces directly (no queue)
        self._start_component_traces(component_trace_context, trace_context)

        try:
            yield self
        except Exception as e:
            # End traces with error
            self._end_component_traces(component_trace_context, trace_context, e)
            raise
        else:
            # End traces successfully
            self._end_component_traces(component_trace_context, trace_context, None)

    @property
    def project_name(self):
        if self.deactivated:
            return os.getenv("AUTONOMIZE_EXPERIMENT_NAME", "GenesisStudio")
        trace_context = trace_context_var.get()
        if trace_context is None:
            raise RuntimeError("called project_name but no trace context found")
        return trace_context.project_name

    def add_log(self, trace_name: str, log: Log) -> None:
        """Add a log to the current component trace context."""
        if self.deactivated:
            return
        component_context = component_context_var.get()
        if component_context is None:
            raise RuntimeError("called add_log but no component context found")
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
            raise RuntimeError("called set_outputs but no component context found")
        component_context.outputs[trace_name] |= outputs or {}
        component_context.outputs_metadata[trace_name] |= output_metadata or {}
        trace_context = trace_context_var.get()
        if trace_context is None:
            raise RuntimeError("called set_outputs but no trace context found")
        trace_context.all_outputs[trace_name] |= outputs or {}

    def get_tracer(self, tracer_name: str) -> BaseTracer | None:
        """Get a specific tracer by name."""
        trace_context = trace_context_var.get()
        if trace_context is None:
            raise RuntimeError("called get_tracer but no trace context found")
        return trace_context.tracers.get(tracer_name)

    def get_langchain_callbacks(self) -> list[BaseCallbackHandler]:
        """Get LangChain callbacks from all ready tracers."""
        if self.deactivated:
            return []
        callbacks = []
        trace_context = trace_context_var.get()
        if trace_context is None:
            raise RuntimeError("called get_langchain_callbacks but no trace context found")
        for tracer in trace_context.tracers.values():
            if tracer.ready:
                langchain_callback = tracer.get_langchain_callback()
                if langchain_callback:
                    callbacks.append(langchain_callback)
        return callbacks