from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from typing_extensions import override

from langflow.serialization.serialization import serialize
from langflow.services.tracing.base import BaseTracer

try:
    import noveum_trace
    from noveum_trace import NoveumClient
    from noveum_trace.core import _register_client
    from noveum_trace.integrations.langchain import NoveumTraceCallbackHandler
    from noveum_trace.core.context import set_current_trace
except ImportError:
    noveum_trace = None  # type: ignore[assignment]
    NoveumClient = None  # type: ignore[assignment, misc]
    _register_client = None  # type: ignore[assignment, misc]
    NoveumTraceCallbackHandler = None  # type: ignore[assignment, misc]
    set_current_trace = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log


class NoveumTracer(BaseTracer):
    """Tracer implementation for Noveum Trace SDK integration."""

    flow_id: str

    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: UUID,
        user_id: str | None = None,
        session_id: str | None = None,      
    ) -> None:
        """Initialize the Noveum tracer.

        Args:
            trace_name: Name of the trace (flow name + flow id)
            trace_type: Type of trace (e.g., "chain")
            project_name: Project name for organizing traces
            trace_id: Unique identifier for this trace
            user_id: Optional user identifier
            session_id: Optional session identifier
        """
        self.project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        self.spans: dict = OrderedDict()  # spans that are not ended

        config = self._get_config()
        self._ready: bool = self.setup_noveum(config) if config else False

    @property
    def ready(self):
        """Check if the tracer is ready to trace."""
        return self._ready

    def setup_noveum(self, config: dict) -> bool:
        """Setup the Noveum Trace client and initialize the main trace.

        Args:
            config: Configuration dictionary with api_key, project, environment, endpoint

        Returns:
            True if setup was successful, False otherwise
        """
        try:
            if noveum_trace is None:
                raise ImportError("noveum_trace not available")
            
            # Always create a new client for this tracer
            logger.debug("Creating new NoveumClient instance")
            self._client = NoveumClient(
                api_key=config["api_key"],
                project=config["project"],
                environment=config["environment"],
                endpoint=config.get("endpoint"),
            )
            
            # Register the client so NoveumTraceCallbackHandler can find it via get_client()
            _register_client(self._client)
            
            # Also set the module-level _client so get_client() and is_initialized() work
            # This is needed because get_client() checks the module-level _client, not _global_client
            if hasattr(noveum_trace, "_client_lock"):
                with noveum_trace._client_lock:
                    noveum_trace._client = self._client
            else:
                # Fallback: set directly if lock doesn't exist
                noveum_trace._client = self._client
            
            logger.debug("setup_noveum was called, a new trace will be created.")

            # Create the main trace for this graph run
            # Prepare trace attributes including metadata
            trace_attributes = {
                "trace_type": self.trace_type,
                "flow_id": self.flow_id,
            }
            
            # Add user_id and session_id to metadata if provided
            if self.user_id:
                trace_attributes["user_id"] = self.user_id
            if self.session_id:
                trace_attributes["session_id"] = self.session_id

            self.trace = self._client.start_trace(
                name=self.flow_id,
                attributes=trace_attributes,
            )

            # Set the trace in the context so the callback handler can use it
            # This ensures LangChain operations are traced under our main trace
            set_current_trace(self.trace)

            # Create the callback handler and associate it with the trace
            self._callback_handler = NoveumTraceCallbackHandler()

            logger.debug("Noveum Trace initialized successfully")
            logger.debug(f"Trace {self.trace.trace_id} set in context for callback handler")
            return True

        except ImportError:
            logger.exception(
                "Could not import noveum_trace. Please install it with `pip install noveum-trace`."
            )
            return False

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error setting up Noveum Trace: {e}")
            return False

    @override
    def add_trace(
        self,
        trace_id: str,  # actually component id
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex: Vertex | None = None,
    ) -> None:
        """Start tracing a component execution by creating a span.

        Args:
            trace_id: Component ID
            trace_name: Component name (with ID suffix)
            trace_type: Type of component
            inputs: Component inputs
            metadata: Additional metadata
            vertex: Graph vertex (optional)
        """
        start_time = datetime.now(tz=timezone.utc)
        if not self._ready:
            return

        # Build metadata attributes
        metadata_: dict = {"from_langflow_component": True, "component_id": trace_id}
        metadata_ |= {"trace_type": trace_type} if trace_type else {}
        metadata_ |= metadata or {}

        # Clean up component name (remove ID suffix)
        name = trace_name.removesuffix(f" ({trace_id})")

        # Serialize inputs for tracing
        serialized_inputs = serialize(inputs)

        # Create span attributes combining inputs and metadata
        span_attributes = {
            **metadata_,
            "inputs": serialized_inputs,
        }

        try:
            # Create component span under the main trace
            span = self.trace.create_span(
                name=name,
                attributes=span_attributes,
                start_time=start_time,
            )

            # Store the span for later retrieval
            self.spans[trace_id] = span
            logger.debug(f"Created span {span.span_id} for component {name} in trace {self.trace.trace_id}")

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error creating span for component {trace_name}: {e}")

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        """End tracing a component execution by finishing its span.

        Args:
            trace_id: Component ID
            trace_name: Component name
            outputs: Component outputs
            error: Exception if component failed
            logs: Execution logs
        """
        end_time = datetime.now(tz=timezone.utc)
        if not self._ready:
            return

        # Retrieve and remove the span
        span = self.spans.pop(trace_id, None)
        if not span:
            logger.debug(f"No span found for component {trace_name}")
            return

        try:
            # Build output data
            output_data: dict = {}
            output_data |= serialize(outputs) if outputs else {}
            output_data |= {"error": str(error)} if error else {}
            output_data |= {"logs": [serialize(log) if isinstance(log, dict) else log for log in logs]} if logs else {}

            # Set span attributes for outputs
            if output_data:
                span.set_attributes({"outputs": output_data})

            # Set error status if there was an error
            if error:
                span.set_status("error", str(error))

            # Finish the span
            span.finish(end_time=end_time)
            logger.debug(f"Finished span {span.span_id} for component {trace_name}")

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error ending span for component {trace_name}: {e}")

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Finalize the main trace for the graph run.

        Args:
            inputs: Graph inputs
            outputs: Graph outputs
            error: Exception if graph failed
            metadata: Additional metadata
        """
        if not self._ready:
            return

        try:
            # Update trace attributes with final inputs/outputs
            trace_attributes = {}
            
            if inputs:
                trace_attributes["final_inputs"] = serialize(inputs)
            if outputs:
                trace_attributes["final_outputs"] = serialize(outputs)
            if metadata:
                trace_attributes["final_metadata"] = serialize(metadata)
            if error:
                trace_attributes["error"] = str(error)

            if trace_attributes:
                self.trace.set_attributes(trace_attributes)

            # Set error status if there was an error
            if error:
                self.trace.set_status("error", str(error))

            # Finish and export the trace using client.finish_trace()
            self._client.finish_trace(self.trace)
            logger.debug(f"Finished and exported trace {self.trace.trace_id} via client.finish_trace()")

            # Flush the client to ensure all data is sent
            if hasattr(self._client, "flush"):
                self._client.flush()
                logger.debug("Flushed client after trace completion")

            # Shutdown the client
            # NoveumClient has a shutdown() method that flushes all pending data and cleans up resources
            try:
                self._client.shutdown()
                logger.debug("Shutdown NoveumClient after trace completion")
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Error shutting down NoveumClient: {e}")

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error finalizing trace: {e}")

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Get the LangChain callback handler for tracing LangChain operations.

        Returns:
            NoveumTraceCallbackHandler instance or None if not ready
        """
        if not self._ready:
            return None

        return self._callback_handler

    def _get_config(self) -> dict:
        """Read configuration from environment variables, falling back to instance parameters.

        Returns:
            Configuration dictionary with api_key, project, environment, endpoint
            Empty dict if required variables are missing
        """
        api_key = os.getenv("NOVEUM_API_KEY", None)
        project = os.getenv("NOVEUM_PROJECT", None) or self.project_name
        environment = os.getenv("NOVEUM_ENVIRONMENT", None)
        endpoint = os.getenv("NOVEUM_ENDPOINT", None)

        # All three required variables must be present (project can come from env var or parameter)
        if api_key and project and environment:
            config = {
                "api_key": api_key,
                "project": project,
                "environment": environment,
            }
            # Add endpoint if provided (otherwise NoveumClient will use default)
            if endpoint:
                config["endpoint"] = endpoint
            return config

        return {}
