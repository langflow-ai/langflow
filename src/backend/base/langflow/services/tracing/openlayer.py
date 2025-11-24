from __future__ import annotations

import os
import time
import types
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
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

        config = self._get_config()
        self._ready: bool = self.setup_openlayer(config) if config else False

    @property
    def ready(self):
        return self._ready

    def setup_openlayer(self, config) -> bool:
        """Initialize Openlayer SDK utilities."""
        logger.debug("[Openlayer] Setting up Openlayer tracer with SDK")
        
        # Validate configuration
        if not config:
            logger.warning("[Openlayer] No configuration provided")
            return False
        
        required_keys = ["api_key", "inference_pipeline_id"]
        for key in required_keys:
            if key not in config or not config[key]:
                logger.warning(f"[Openlayer] Missing required config: {key}")
                return False
        
        try:
            from openlayer.lib.tracing import enums as openlayer_enums
            from openlayer.lib.tracing import steps as openlayer_steps
            from openlayer.lib.tracing import tracer as openlayer_tracer
            from openlayer.lib.tracing import traces as openlayer_traces
            from openlayer.lib.tracing.context import UserSessionContext
            from openlayer.lib.integrations.langchain_callback import OpenlayerHandler

            self._openlayer_tracer = openlayer_tracer
            self._openlayer_steps = openlayer_steps
            self._openlayer_traces = openlayer_traces
            self._openlayer_enums = openlayer_enums
            self._UserSessionContext = UserSessionContext
            self._OpenlayerHandler = OpenlayerHandler
            self._inference_pipeline_id = config["inference_pipeline_id"]

            if self.user_id:
                UserSessionContext.set_user_id(self.user_id)
            if self.session_id:
                UserSessionContext.set_session_id(self.session_id)

            client = self._openlayer_tracer._get_client()
            if not client:
                logger.debug("[Openlayer] SDK client not available")
                return False

            return True

        except ImportError:
            logger.exception("Could not import openlayer SDK. Please install it with `pip install openlayer`.")
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
            logger.error(f"[Openlayer] Failed to create step '{name}': {e}")
            return

        # Store step and set as current in SDK context
        self.component_steps[trace_id] = step
        self._openlayer_tracer._current_step.set(step)

        # Find parent from vertex edges for hierarchy tracking
        if vertex and hasattr(vertex, "incoming_edges") and len(vertex.incoming_edges) > 0:
            valid_parents = [edge.source_id for edge in vertex.incoming_edges if edge.source_id in self.component_steps]
            if valid_parents:
                self.component_parent_ids[trace_id] = valid_parents[-1]

        logger.debug(f"[Openlayer] Added {trace_type} step: {name}")

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
            logger.warning(f"[Openlayer] Step not found: {trace_id}")
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
            logger.error(f"[Openlayer] Error in {step.name}: {error}")
        if logs:
            if not step.metadata:
                step.metadata = {}
            step.metadata["logs"] = [log if isinstance(log, dict) else log.model_dump() for log in logs]

        logger.debug(f"[Openlayer] Completed: {step.name} ({step.latency:.0f}ms)")

    @override
    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Build hierarchy and send using SDK (like OpenAI Agents pattern)."""
        if not self._ready or not self.trace_obj:
            return

        logger.debug(f"[Openlayer] Finalizing trace: {len(self.component_steps)} components")

        try:
            # Build hierarchy and add to trace
            root_steps = self._build_and_add_hierarchy()

            # Use SDK's post_process_trace
            try:
                trace_data, input_variable_names = self._openlayer_tracer.post_process_trace(self.trace_obj)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[Openlayer] post_process_trace failed: {e}")
                return
            
            # Validate trace_data
            if not trace_data or not isinstance(trace_data, dict):
                logger.error("[Openlayer] Invalid trace_data from SDK")
                return
            
            logger.debug(f"[Openlayer] Processed {len(trace_data.get('steps', []))} steps")

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
                    logger.info(f"[Openlayer] Sent trace {self.trace_id} ({len(trace_data.get('steps', []))} steps)")
                    logger.debug(f"[Openlayer] Response: {response}")
            else:
                logger.debug("[Openlayer] Publish disabled")
            
            # Clean up SDK context
            self._cleanup_sdk_context()

        except Exception as e:  # noqa: BLE001
            logger.error(f"[Openlayer] Failed to send trace: {e}")
            import traceback
            logger.debug(f"[Openlayer] Traceback: {traceback.format_exc()}")
            # Still clean up even on error
            self._cleanup_sdk_context()

    def _cleanup_sdk_context(self) -> None:
        try:
            self._openlayer_tracer._current_trace.set(None)
            self._openlayer_tracer._current_step.set(None)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[Openlayer] Cleanup error: {e}")

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
        logger.debug(f"[Openlayer] Building trace from {len(self.component_steps)} steps")

        # Filter out tool provider components using list comprehension
        component_steps_list = [
            step for step in self.component_steps.values()
            # if not self._is_tool_provider(step)
        ]
        
        filtered_count = len(self.component_steps) - len(component_steps_list)
        if filtered_count > 0:
            logger.debug(f"[Openlayer] Filtered {filtered_count} tool providers")
        logger.debug(f"[Openlayer] Processing {len(component_steps_list)} components")
        

        flow_name = self.trace_name.split(" - ")[0] if " - " in self.trace_name else self.trace_name
        
        flow_metadata = self._extract_flow_metadata(component_steps_list)
        
        root_step = self._openlayer_steps.UserCallStep(
            name=flow_name,
            inputs=flow_metadata["chat_input"],
            output=flow_metadata["chat_output"],
            metadata={"component_count": len(component_steps_list)}
        )
        
        # Set timing from extracted metadata
        if flow_metadata["start_time"] and flow_metadata["end_time"]:
            root_step.start_time = flow_metadata["start_time"]
            root_step.end_time = flow_metadata["end_time"]
            # Ensure latency is int (API requires int32/int64/float32/float64)
            root_step.latency = int((root_step.end_time - root_step.start_time) * 1000)  # ms as int
            logger.debug(f"[Openlayer] Flow latency: {root_step.latency}ms")
        
        for step in component_steps_list:
            root_step.add_nested_step(step)
        
        # Add root step to trace
        self.trace_obj.add_step(root_step)
        logger.debug(f"[Openlayer] Created root step '{flow_name}' with {len(component_steps_list)} nested components")

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
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"[Openlayer] Pydantic model_dump() failed for {type(value).__name__}: {e}")
                    pass

        # Handle LangChain tools
        if hasattr(value, "name") and hasattr(value, "description"):
            try:
                return {
                    "name": str(value.name),
                    "description": str(value.description) if value.description else None,
                }
            except Exception as e:  # noqa: BLE001
                logger.debug(f"[Openlayer] Tool conversion failed for {type(value).__name__}: {e}")
                pass

        # Fallback to string
        try:
            return str(value)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[Openlayer] String conversion failed for {type(value).__name__}: {e}")
            return None

    def get_langchain_callback(self) -> BaseCallbackHandler | None:
        """Return OpenlayerHandler (will integrate with our trace via SDK context)."""
        if not self._ready:
            return None

        return self._OpenlayerHandler()

    @staticmethod
    def _get_config() -> dict:
        """Get Openlayer configuration from environment variables."""
        api_key = os.getenv("OPENLAYER_API_KEY", None)
        inference_pipeline_id = os.getenv("OPENLAYER_INFERENCE_PIPELINE_ID", None)

        if api_key and inference_pipeline_id:
            return {
                "api_key": api_key,
                "inference_pipeline_id": inference_pipeline_id,
            }
        return {}
