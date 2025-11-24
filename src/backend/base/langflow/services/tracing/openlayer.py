from __future__ import annotations

import json
import os
import re
import time
import types
from typing import TYPE_CHECKING, Any

from typing_extensions import override

from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log

from openlayer.lib.tracing.context import UserSessionContext


# Component name constants
CHAT_OUTPUT_NAMES = ("Chat Output", "ChatOutput")
CHAT_INPUT_NAMES = ("Text Input", "Chat Input", "TextInput", "ChatInput")


class OpenlayerTracer(BaseTracer):
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
        self.project_name = project_name
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
        self.flow_id = trace_name.split(" - ")[-1]
        
        # Store component steps using SDK Step objects
        self.component_steps: dict = {}  # component_id -> Step object from SDK
        self.component_parent_ids: dict = {}  # component_id -> parent_component_id
        self.trace_obj = None  # Trace object from SDK
        self.langchain_handler: Any = None  # Store handler to access its trace later

        # Get config based on flow name
        config = self._get_config(trace_name)
        self._ready: bool = self.setup_openlayer(config) if config else False

    @property
    def ready(self):
        return self._ready

    def setup_openlayer(self, config) -> bool:
        """Initialize Openlayer SDK utilities."""
        # Validate configuration
        if not config:
            return False
        
        required_keys = ["api_key", "inference_pipeline_id"]
        for key in required_keys:
            if key not in config or not config[key]:
                return False
        
        try:
            from openlayer.lib.tracing import enums as openlayer_enums
            from openlayer.lib.tracing import steps as openlayer_steps
            from openlayer.lib.tracing import tracer as openlayer_tracer
            from openlayer.lib.tracing import traces as openlayer_traces
            from openlayer.lib.tracing.context import UserSessionContext
            from openlayer.lib.tracing import configure

            self._openlayer_tracer = openlayer_tracer
            self._openlayer_steps = openlayer_steps
            self._openlayer_traces = openlayer_traces
            self._openlayer_enums = openlayer_enums
            self._inference_pipeline_id = config["inference_pipeline_id"]

            if self.user_id:
                UserSessionContext.set_user_id(self.user_id)
            if self.session_id:
                UserSessionContext.set_session_id(self.session_id)

            configure(inference_pipeline_id=config["inference_pipeline_id"])
            return True

        except ImportError:
            return False
        except Exception as e:  # noqa: BLE001
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
        """Create SDK Step object for component."""
        if not self._ready:
            return

        # Create trace on first component and set in SDK context
        if self.trace_obj is None:
            self.trace_obj = self._openlayer_traces.Trace()
            self._openlayer_tracer._current_trace.set(self.trace_obj)

        # Extract session/user from inputs and update SDK context
        if inputs and "session_id" in inputs and inputs["session_id"] != self.flow_id:
            self.session_id = inputs["session_id"]
            UserSessionContext.set_session_id(self.session_id)
        if inputs and "user_id" in inputs:
            self.user_id = inputs["user_id"]
            UserSessionContext.set_user_id(self.user_id)

        # Clean component name
        name = trace_name.removesuffix(f" ({trace_id})")

        # Map LangFlow trace_type to Openlayer StepType
        step_type_map = {
            "llm": self._openlayer_enums.StepType.CHAT_COMPLETION,
            "chain": self._openlayer_enums.StepType.USER_CALL,
            "tool": self._openlayer_enums.StepType.TOOL,
            "agent": self._openlayer_enums.StepType.AGENT,
            "retriever": self._openlayer_enums.StepType.RETRIEVER,
            "prompt": self._openlayer_enums.StepType.USER_CALL,
        }
        step_type = step_type_map.get(trace_type, self._openlayer_enums.StepType.USER_CALL)

        # Convert inputs and metadata
        converted_inputs = self._convert_to_openlayer_types(inputs) if inputs else {}
        converted_metadata = self._convert_to_openlayer_types(metadata) if metadata else {}

        # Create Step using SDK step_factory
        try:
            step = self._openlayer_steps.step_factory(
                step_type=step_type,
                name=name,
                inputs=converted_inputs,
                metadata=converted_metadata,
            )
            step.start_time = time.time()
        except Exception as e:  # noqa: BLE001
            return

        # Store step and set as current in SDK context
        self.component_steps[trace_id] = step
        
        # Set as current step so LangChain callbacks can nest under it
        self._openlayer_tracer._current_step.set(step)

        # Find parent from vertex edges for hierarchy tracking
        if vertex and hasattr(vertex, "incoming_edges") and len(vertex.incoming_edges) > 0:
            valid_parents = [edge.source_id for edge in vertex.incoming_edges if edge.source_id in self.component_steps]
            if valid_parents:
                self.component_parent_ids[trace_id] = valid_parents[-1]

    @override
    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs: Sequence[Log | dict] = (),
    ) -> None:
        """Update SDK Step with outputs."""
        if not self._ready:
            return

        step = self.component_steps.get(trace_id)
        if not step:
            return

        # Set end time and latency (as int for API compatibility)
        step.end_time = time.time()
        if hasattr(step, "start_time") and step.start_time:
            step.latency = int((step.end_time - step.start_time) * 1000)  # ms as int

        # Update output
        if outputs:
            step.output = self._convert_to_openlayer_types(outputs)

        # Add error and logs to metadata
        if error:
            if not step.metadata:
                step.metadata = {}
            step.metadata["error"] = str(error)
        if logs:
            if not step.metadata:
                step.metadata = {}
            step.metadata["logs"] = [log if isinstance(log, dict) else log.model_dump() for log in logs]

        # Clear current step context
        # Use None as positional argument to avoid LookupError when ContextVar is not set
        current_step = self._openlayer_tracer._current_step.get(None)
        if current_step == step:
            self._openlayer_tracer._current_step.set(None)

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Build hierarchy and send using SDK."""
        if not self._ready or not self.trace_obj:
            return

        try:
            # Build hierarchy and add to trace
            # This will integrate handler's traces and then clear them
            root_steps = self._build_and_add_hierarchy()

            # Use SDK's post_process_trace
            try:
                trace_data, input_variable_names = self._openlayer_tracer.post_process_trace(self.trace_obj)
            except Exception as e:  # noqa: BLE001
                return
            
            # Validate trace_data
            if not trace_data or not isinstance(trace_data, dict):
                return

            # Build config using SDK's ConfigLlmData
            config = dict(
                self._openlayer_tracer.ConfigLlmData(
                    output_column_name="output",
                    input_variable_names=input_variable_names,
                    latency_column_name="latency",
                    cost_column_name="cost",
                    timestamp_column_name="inferenceTimestamp",
                    inference_id_column_name="inferenceId",
                    num_of_token_column_name="tokens",
                )
            )

            # Add reserved column configurations
            if "user_id" in trace_data:
                config["user_id_column_name"] = "user_id"
            if "session_id" in trace_data:
                config["session_id_column_name"] = "session_id"
            if "context" in trace_data:
                config["context_column_name"] = "context"

            # Send using SDK client
            if self._openlayer_tracer._publish:
                client = self._openlayer_tracer._get_client()
                if client:
                    response = client.inference_pipelines.data.stream(
                        inference_pipeline_id=self._inference_pipeline_id,
                        rows=[trace_data],
                        config=config,
                    )
            
            # Clean up SDK context
            self._cleanup_sdk_context()

        except Exception as e:  # noqa: BLE001
            # Still clean up even on error
            self._cleanup_sdk_context()

    def _cleanup_sdk_context(self) -> None:
        try:
            self._openlayer_tracer._current_trace.set(None)
            self._openlayer_tracer._current_step.set(None)
        except Exception:  # noqa: BLE001
            pass

    def _extract_flow_metadata(self, components: list[Any]) -> dict[str, Any]:
        metadata = {
            "chat_output": "Flow completed",
            "chat_input": {},
            "start_time": None,
            "end_time": None,
        }
        
        for step in components:
            # Extract Chat Output
            if step.name in CHAT_OUTPUT_NAMES:
                chat_output = self._safe_get_input(step, "input_value")
                if chat_output:
                    metadata["chat_output"] = chat_output
            
            # Extract Chat Input
            if step.name in CHAT_INPUT_NAMES:
                input_val = self._safe_get_input(step, "input_value")
                if input_val:
                    metadata["chat_input"] = {"user_query": input_val}
            
            # Extract timing
            if hasattr(step, "start_time") and step.start_time:
                if metadata["start_time"] is None or step.start_time < metadata["start_time"]:
                    metadata["start_time"] = step.start_time
            if hasattr(step, "end_time") and step.end_time:
                if metadata["end_time"] is None or step.end_time > metadata["end_time"]:
                    metadata["end_time"] = step.end_time
        
        return metadata

    def _safe_get_input(self, step: Any, key: str, default: Any = None) -> Any:
        if not hasattr(step, "inputs") or not isinstance(step.inputs, dict):
            return default
        return step.inputs.get(key, default)

    def _is_tool_provider(self, step: Any) -> bool:
        if not hasattr(step, "output") or not isinstance(step.output, dict):
            return False
        return len(step.output) == 1 and "component_as_tool" in step.output

    def _build_and_add_hierarchy(self) -> list[Any]:
        if self.langchain_handler and hasattr(self.langchain_handler, '_traces_by_root'):
            langchain_traces = self.langchain_handler._traces_by_root
            
            if langchain_traces:
                target_component = None
                for component_step in self.component_steps.values():
                    if component_step.name == "Agent":
                        target_component = component_step
                        break

                if target_component is None:
                    for component_step in self.component_steps.values():
                        if hasattr(component_step, 'step_type') and component_step.step_type.value in ['llm', 'chain', 'agent', 'chat_completion']:
                            target_component = component_step

                for run_id, lc_trace in langchain_traces.items():
                    for lc_step in lc_trace.steps:
                        if target_component:
                            target_component.add_nested_step(lc_step)

                # Clear handler's traces after integration
                self.langchain_handler._traces_by_root.clear()
        
        flow_name = self.trace_name.split(" - ")[0] if " - " in self.trace_name else self.trace_name
        
        flow_metadata = self._extract_flow_metadata(self.component_steps.values())
        
        root_step = self._openlayer_steps.UserCallStep(
            name=flow_name,
            inputs=flow_metadata["chat_input"],
            output=flow_metadata["chat_output"],
            metadata={"flow_name": flow_name}
        )
        
        # Set timing from extracted metadata
        if flow_metadata["start_time"] and flow_metadata["end_time"]:
            root_step.start_time = flow_metadata["start_time"]
            root_step.end_time = flow_metadata["end_time"]
            root_step.latency = int((root_step.end_time - root_step.start_time) * 1000)
        
        for step in self.component_steps.values():
            root_step.add_nested_step(step)
        
        # Add root to trace
        self.trace_obj.add_step(root_step)

        return [root_step]

    def _convert_to_openlayer_types(self, io_dict: dict[str, Any]) -> dict[str, Any]:
        if io_dict is None:
            return {}
        return {str(key): self._convert_to_openlayer_type(value) for key, value in io_dict.items()}

    def _convert_to_openlayer_type(self, value: Any) -> Any:
        from langchain_core.documents import Document
        from langchain_core.messages import BaseMessage

        from langflow.schema.data import Data
        from langflow.schema.message import Message

        if isinstance(value, dict):
            return {key: self._convert_to_openlayer_type(val) for key, val in value.items()}

        if isinstance(value, list):
            return [self._convert_to_openlayer_type(v) for v in value]

        if isinstance(value, Message):
            return value.text

        if isinstance(value, Data):
            return value.get_text()

        if isinstance(value, BaseMessage):
            return value.content

        if isinstance(value, Document):
            return value.page_content

        if isinstance(value, (types.GeneratorType | types.NoneType)):
            return str(value)

        if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
            if isinstance(value, type):
                pass
            else:
                try:
                    return self._convert_to_openlayer_type(value.model_dump())
                except Exception:  # noqa: BLE001
                    pass

        # Handle LangChain tools
        if hasattr(value, "name") and hasattr(value, "description"):
            try:
                return {
                    "name": str(value.name),
                    "description": str(value.description) if value.description else None,
                }
            except Exception:  # noqa: BLE001
                pass

        # Fallback to string
        try:
            return str(value)
        except Exception:  # noqa: BLE001
            return None

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Return AsyncOpenlayerHandler for LangChain integration."""
        if not self._ready:
            return None

        # Reuse existing handler if already created
        if self.langchain_handler is not None:
            return self.langchain_handler

        try:
            from openlayer.lib.integrations.langchain_callback import AsyncOpenlayerHandler

            # Ensure trace exists
            if self.trace_obj is None:
                self.trace_obj = self._openlayer_traces.Trace()
            
            # Set trace in ContextVar - handler will detect and use it automatically
            self._openlayer_tracer._current_trace.set(self.trace_obj)

            # Create handler - it will automatically detect our trace from context
            # and integrate all steps into it (no standalone traces, no uploads)
            handler = AsyncOpenlayerHandler(
                ignore_llm=False,
                ignore_chat_model=False,
                ignore_chain=False,
                ignore_retriever=False,
                ignore_agent=False,
            )

            # Store reference to handler
            self.langchain_handler = handler
            return handler
        except Exception as e:  # noqa: BLE001
            return None

    @staticmethod
    def _sanitize_flow_name(flow_name: str) -> str:
        """Sanitize flow name for use in environment variable names.

        Converts to uppercase and replaces non-alphanumeric characters with underscores.
        Example: "My Flow-Name" -> "MY_FLOW_NAME"
        """
        # Replace non-alphanumeric characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9]+', '_', flow_name)
        # Remove leading/trailing underscores and convert to uppercase
        return sanitized.strip('_').upper()

    @staticmethod
    def _get_config(trace_name: str | None = None) -> dict:
        """Get Openlayer configuration from environment variables.

        Configuration is resolved in the following order (highest priority first):
        1. Flow-specific env var: OPENLAYER_PIPELINE_<FLOW_NAME>
        2. JSON mapping: OPENLAYER_LANGFLOW_MAPPING
        3. Default env var: OPENLAYER_INFERENCE_PIPELINE_ID

        Args:
            trace_name: The trace name which may contain the flow name

        Returns:
            Configuration dict with 'api_key' and 'inference_pipeline_id', or empty dict
        """
        api_key = os.getenv("OPENLAYER_API_KEY", None)
        if not api_key:
            return {}

        inference_pipeline_id = None

        # Extract flow name from trace_name (format: "flow_name - flow_id")
        flow_name = None
        if trace_name:
            flow_name = trace_name.split(" - ")[0] if " - " in trace_name else trace_name

        # 1. Try flow-specific environment variable (highest priority)
        if flow_name:
            sanitized_flow_name = OpenlayerTracer._sanitize_flow_name(flow_name)
            flow_specific_var = f"OPENLAYER_PIPELINE_{sanitized_flow_name}"
            inference_pipeline_id = os.getenv(flow_specific_var)

        # 2. Try JSON mapping (medium priority)
        if not inference_pipeline_id:
            mapping_json = os.getenv("OPENLAYER_LANGFLOW_MAPPING")
            if mapping_json and flow_name:
                try:
                    mapping = json.loads(mapping_json)
                    if isinstance(mapping, dict) and flow_name in mapping:
                        inference_pipeline_id = mapping[flow_name]
                except json.JSONDecodeError as e:
                    pass

        # 3. Fall back to default environment variable (lowest priority)
        if not inference_pipeline_id:
            inference_pipeline_id = os.getenv("OPENLAYER_INFERENCE_PIPELINE_ID")

        if api_key and inference_pipeline_id:
            return {
                "api_key": api_key,
                "inference_pipeline_id": inference_pipeline_id,
            }

        return {}
