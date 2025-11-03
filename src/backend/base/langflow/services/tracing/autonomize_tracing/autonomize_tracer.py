from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from typing_extensions import override

from langflow.logging.logger import logger
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler

    from langflow.graph.vertex.base import Vertex
    from langflow.services.tracing.schema import Log


class AutonomizeTracer(BaseTracer):
    """Custom Autonomize tracer for Genesis Studio Backend with enhanced debug logging."""

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ):
        logger.info(f"🎯 AutonomizeTracer.__init__ called with trace_name='{trace_name}'")
        
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1] if " - " in trace_name else trace_name
        
        # Store component traces
        self.component_traces: dict[str, dict] = {}
        self.start_time = time.time()
        
        # Initialize the tracer
        self._ready = self._setup_autonomize_tracer()
        
        logger.info(f"🎯 AutonomizeTracer initialized: ready={self._ready}, flow_id='{self.flow_id}'")

    @property
    def ready(self) -> bool:
        """Check if the tracer is ready."""
        logger.debug(f"🎯 AutonomizeTracer.ready called: {self._ready}")
        return self._ready

    def _setup_autonomize_tracer(self) -> bool:
        """Setup the Autonomize tracer with configuration."""
        try:
            logger.info("🎯 Setting up AutonomizeTracer...")
            
            tracing_enabled = os.getenv("AUTONOMIZE_TRACING_ENABLED", "false").lower() == "true"
            logger.info(f"🎯 AUTONOMIZE_TRACING_ENABLED={tracing_enabled}")
            
            if not tracing_enabled:
                logger.warning("❌ Autonomize tracing is disabled via AUTONOMIZE_TRACING_ENABLED")
                return False

            logger.info(f"✅ Autonomize tracer setup successful for flow: {self.flow_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize Autonomize tracer: {e}", exc_info=True)
            return False

    @override
    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        """Add a new component trace."""
        logger.info(f"📝 AutonomizeTracer.add_trace called: trace_name='{trace_name}', trace_id='{trace_id}', ready={self._ready}")
        logger.debug(f"📝 Raw inputs received: {inputs}")
        logger.debug(f"📝 Raw metadata received: {metadata}")
        
        if not self._ready:
            logger.warning("❌ AutonomizeTracer not ready, skipping add_trace")
            return

        # Convert inputs - keep original structure
        converted_inputs = self._convert_to_autonomize_types(inputs)
        logger.debug(f"📝 Converted inputs: {converted_inputs}")

        component_trace = {
            "trace_id": trace_id,
            "trace_name": trace_name,
            "trace_type": trace_type,
            "inputs": converted_inputs,
            "metadata": metadata or {},
            "vertex_id": vertex.id if vertex else None,
            "start_time": datetime.now(timezone.utc),
            "parent_trace_id": str(self.trace_id),
            "flow_id": self.flow_id,
            "project_name": self.project_name,
            "user_id": self.user_id,
            "session_id": self.session_id,
        }

        self.component_traces[trace_id] = component_trace
        
        self._send_trace_event("component_start", component_trace)
        
        logger.info(f"✅ Started trace for {trace_name} (ID: {trace_id})")

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        """End a component trace."""
        logger.info(f"🏁 AutonomizeTracer.end_trace called: trace_name='{trace_name}', trace_id='{trace_id}', ready={self._ready}")
        
        if not self._ready or trace_id not in self.component_traces:
            logger.warning(f"❌ AutonomizeTracer not ready or trace not found: ready={self._ready}, trace_exists={trace_id in self.component_traces}")
            return

        component_trace = self.component_traces[trace_id]
        component_trace.update({
            "outputs": self._convert_to_autonomize_types(outputs) if outputs else {},
            "error": str(error) if error else None,
            "logs": [log if isinstance(log, dict) else log.model_dump() for log in logs],
            "end_time": datetime.now(timezone.utc),
            "duration_ms": (datetime.now(timezone.utc) - component_trace["start_time"]).total_seconds() * 1000,
        })

        # Send trace end event to your backend
        self._send_trace_event("component_end", component_trace)
        
        logger.info(f"✅ Ended trace for {trace_name} (ID: {trace_id})")

        # Clean up
        del self.component_traces[trace_id]

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End the main flow trace."""
        logger.info(f"🎯 AutonomizeTracer.end called: ready={self._ready}")
        
        if not self._ready:
            logger.warning("❌ AutonomizeTracer not ready, skipping end")
            return

        end_time = time.time()
        duration_ms = (end_time - self.start_time) * 1000

        flow_trace = {
            "trace_id": str(self.trace_id),
            "trace_name": self.trace_name,
            "trace_type": self.trace_type,
            "project_name": self.project_name,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "flow_id": self.flow_id,
            "inputs": self._convert_to_autonomize_types(inputs),
            "outputs": self._convert_to_autonomize_types(outputs),
            "error": str(error) if error else None,
            "metadata": metadata or {},
            "start_time": datetime.fromtimestamp(self.start_time, timezone.utc),
            "end_time": datetime.fromtimestamp(end_time, timezone.utc),
            "duration_ms": duration_ms,
        }

        self._send_trace_event("flow_end", flow_trace)
        
        logger.info(f"🎯 Flow trace completed: {self.flow_id} ({duration_ms:.2f}ms)")

    def _convert_to_autonomize_types(self, data: dict[str, Any] | None) -> dict[str, Any]:
        """Convert data types to Autonomize-compatible formats while preserving structure."""
        if not data:
            return {}

        converted = {}
        for key, value in data.items():
            converted[key] = self._convert_value(value)
        return converted

    def _convert_value(self, value: Any) -> Any:
        """Convert individual values to Autonomize-compatible types."""
        # Handle None
        if value is None:
            return None
            
        # Handle dictionaries recursively
        if isinstance(value, dict):
            return {k: self._convert_value(v) for k, v in value.items()}
        
        # Handle lists recursively
        elif isinstance(value, list):
            return [self._convert_value(v) for v in value]
        
        # Handle Langflow Message objects
        elif isinstance(value, Message):
            return value.text if hasattr(value, 'text') else str(value)
        
        # Handle Langflow Data objects
        elif isinstance(value, Data):
            # Try to get text, otherwise get the data dict
            if hasattr(value, 'get_text'):
                return value.get_text()
            elif hasattr(value, 'data'):
                return value.data
            return str(value)
        
        # Handle LangChain messages (BaseMessage and subclasses)
        elif hasattr(value, 'content'):
            return value.content
        
        # Handle LangChain documents
        elif hasattr(value, 'page_content'):
            return value.page_content
        
        # Handle datetime objects
        elif isinstance(value, datetime):
            return value.isoformat()
        
        # For any other type, convert to string
        # This ensures we don't lose data
        else:
            try:
                # Try to return the value as-is if it's a basic type
                if isinstance(value, (str, int, float, bool)):
                    return value
                # Otherwise convert to string
                return str(value)
            except Exception as e:
                logger.warning(f"Failed to convert value of type {type(value)}: {e}")
                return f"<unconvertible: {type(value).__name__}>"

    def _send_trace_event(self, event_type: str, trace_data: dict) -> None:
        """Send trace event to your Autonomize backend."""
        try:
            event = {
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_data": trace_data,
            }
            
            logger.info(f"📤 [DEBUG] Sent {event_type} event for trace {trace_data.get('trace_id')} - Event: {event}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send trace event: {e}", exc_info=True)

    @override
    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Get LangChain callback handler if needed."""
        # Implement if you need LangChain integration
        return None