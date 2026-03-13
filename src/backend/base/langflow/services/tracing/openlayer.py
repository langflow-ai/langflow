from __future__ import annotations

import json
import os
import re
import time
from typing import TYPE_CHECKING, Any, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from loguru import logger
from typing_extensions import override

from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.tracing.base import BaseTracer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langchain.callbacks.base import BaseCallbackHandler
    from lfx.graph.vertex.base import Vertex

    from langflow.services.tracing.schema import Log

# Component name constants
CHAT_OUTPUT_NAMES = ("Chat Output", "ChatOutput")
CHAT_INPUT_NAMES = ("Text Input", "Chat Input", "TextInput", "ChatInput")


class FlowMetadata(TypedDict):
    """Metadata extracted from flow component steps."""

    chat_output: str
    chat_input: dict[str, Any]
    start_time: float | None
    end_time: float | None
    error: str | None


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
        _, self.flow_id = self._parse_trace_name(trace_name)

        # Store component steps using SDK Step objects
        self.component_steps: dict[str, Any] = {}
        # Track the LangFlow trace_type per component (e.g. "agent", "tool", "llm")
        self.component_trace_types: dict[str, str] = {}
        self.trace_obj: Any | None = None
        self.langchain_handler: Any | None = None

        # Get config based on flow name
        config = self._get_config(trace_name)
        if not config:
            logger.debug("Openlayer tracer not initialized: no configuration found (check OPENLAYER_API_KEY)")
            self._ready = False
        else:
            self._ready = self.setup_openlayer(config)

    @staticmethod
    def _parse_trace_name(trace_name: str) -> tuple[str, str]:
        """Parse trace name into (flow_name, flow_id).

        Trace names follow the format "flow_name - flow_id".
        If no separator is found, both values default to the full trace_name.
        """
        if " - " in trace_name:
            return trace_name.split(" - ")[0], trace_name.split(" - ")[-1]
        return trace_name, trace_name

    @property
    def ready(self):
        return self._ready

    def setup_openlayer(self, config) -> bool:
        """Initialize Openlayer SDK utilities."""
        # Validate configuration
        if not config:
            logger.debug("Openlayer tracer not initialized: empty configuration")
            return False

        required_keys = ["api_key", "inference_pipeline_id"]
        for key in required_keys:
            if key not in config or not config[key]:
                logger.debug("Openlayer tracer not initialized: missing required key '%s'", key)
                return False

        try:
            from openlayer import Openlayer
            from openlayer.lib.tracing import configure
            from openlayer.lib.tracing import enums as openlayer_enums
            from openlayer.lib.tracing import steps as openlayer_steps
            from openlayer.lib.tracing import tracer as openlayer_tracer
            from openlayer.lib.tracing import traces as openlayer_traces
            from openlayer.lib.tracing.context import UserSessionContext

            self._openlayer_tracer = openlayer_tracer
            self._openlayer_steps = openlayer_steps
            self._openlayer_traces = openlayer_traces
            self._openlayer_enums = openlayer_enums
            self._user_session_context = UserSessionContext
            self._inference_pipeline_id = config["inference_pipeline_id"]

            # Create our own client for manual uploads (bypasses _publish check)
            self._client = Openlayer(api_key=config["api_key"])

            if self.user_id:
                self._user_session_context.set_user_id(self.user_id)
            if self.session_id:
                self._user_session_context.set_session_id(self.session_id)

            # Disable auto-publishing to prevent duplicate uploads.
            # We manually upload in end() method using self._client.
            # Setting the module-level _publish directly is required because
            # the env var OPENLAYER_DISABLE_PUBLISH is only read at import time.
            openlayer_tracer._publish = False
            configure(inference_pipeline_id=config["inference_pipeline_id"])

            # Build step type map once for reuse in add_trace.
            # LangFlow "llm" components are model builders (e.g. LiteLLM Proxy,
            # Language Model) - they configure the model object but the actual LLM call
            # is captured as a nested ChatCompletionStep by the LangChain callback handler.
            # So we map "llm" to USER_CALL to avoid duplicate chat_completion steps.
            self._step_type_map = {
                "llm": self._openlayer_enums.StepType.USER_CALL,
                "chain": self._openlayer_enums.StepType.USER_CALL,
                "tool": self._openlayer_enums.StepType.TOOL,
                "agent": self._openlayer_enums.StepType.AGENT,
                "retriever": self._openlayer_enums.StepType.RETRIEVER,
                "prompt": self._openlayer_enums.StepType.USER_CALL,
            }
        except ImportError:
            logger.debug("Openlayer tracer not initialized: openlayer package not installed")
            return False
        except Exception:  # noqa: BLE001
            logger.debug("Openlayer tracer not initialized: unexpected error during setup", exc_info=True)
            return False
        else:
            return True

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
            self._user_session_context.set_session_id(self.session_id)
        if inputs and "user_id" in inputs:
            self.user_id = inputs["user_id"]
            self._user_session_context.set_user_id(self.user_id)

        # Resolve component name: prefer vertex display_name (reflects user renames),
        # fall back to trace_name stripped of the id suffix.
        name = (
            vertex.display_name
            if vertex and hasattr(vertex, "display_name")
            else trace_name.removesuffix(f" ({trace_id})")
        )

        # For tool-type components, prefer the actual tool name from metadata
        if trace_type == "tool" and metadata:
            tool_name = metadata.get("display_name") or metadata.get("tool_name")
            if not tool_name and isinstance(metadata.get("serialized"), dict):
                tool_name = metadata["serialized"].get("name")
            if tool_name:
                name = tool_name

        # Map LangFlow trace_type to Openlayer StepType
        step_type = self._step_type_map.get(trace_type, self._openlayer_enums.StepType.USER_CALL)

        # Convert inputs; keep metadata lightweight (only selected keys)
        converted_inputs = self._convert_to_openlayer_types(inputs) if inputs else {}
        converted_metadata = self._slim_metadata(metadata) if metadata else {}

        # Create Step using SDK step_factory
        try:
            step = self._openlayer_steps.step_factory(
                step_type=step_type,
                name=name,
                inputs=converted_inputs,
                metadata=converted_metadata,
            )
            step.start_time = time.time()
        except Exception:  # noqa: BLE001
            return

        # Store step and trace_type, set as current in SDK context
        self.component_steps[trace_id] = step
        self.component_trace_types[trace_id] = trace_type

        # Set as current step so LangChain callbacks can nest under it
        self._openlayer_tracer._current_step.set(step)

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
            converted = self._convert_to_openlayer_types(outputs)
            # For agent steps, prefer the "output" key over the full dict
            # (which also contains "messages" with the raw LangChain message list)
            trace_type = self.component_trace_types.get(trace_id)
            if trace_type == "agent" and "output" in converted:
                step.output = converted["output"]
            else:
                step.output = converted

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
        # Early guard return before entering try/finally
        if not self._ready or not self.trace_obj:
            return

        try:
            # Build hierarchy and add to trace
            # This will integrate handler's traces and then clear them
            self._build_and_add_hierarchy(
                flow_inputs=inputs,
                flow_outputs=outputs,
                error=error,
                flow_metadata=metadata,
            )

            # Use SDK's post_process_trace
            try:
                trace_data, input_variable_names = self._openlayer_tracer.post_process_trace(self.trace_obj)
            except Exception:  # noqa: BLE001
                return  # finally block will still execute

            # Validate trace_data
            if not trace_data or not isinstance(trace_data, dict):
                return  # finally block will still execute

            # Add agent names to trace output for visibility
            agent_names = [
                step.name
                for tid, step in self.component_steps.items()
                if self.component_trace_types.get(tid) == "agent"
            ]
            if agent_names:
                trace_data["agents"] = agent_names

            # Collect agent and tool names from the final serialized steps tree
            agents_called, tools_called = self._collect_step_names(trace_data)
            trace_data["agents_called"] = agents_called
            trace_data["tools_called"] = tools_called

            # Aggregate token/model data from nested ChatCompletionSteps.
            # post_process_trace only reads tokens from the root step (UserCallStep),
            # which has no token data. We walk nested steps to surface this info.
            self._aggregate_llm_data(trace_data)

            # Build config using SDK's ConfigLlmData
            config = dict(
                self._openlayer_tracer.ConfigLlmData(
                    output_column_name="output",
                    input_variable_names=input_variable_names,
                    latency_column_name="latency",
                    cost_column_name="cost",
                    timestamp_column_name="inferenceTimestamp",
                    inference_id_column_name="inferenceId",
                    num_of_token_column_name="tokens",  # noqa: S106
                )
            )

            # Add reserved column configurations
            if "user_id" in trace_data:
                config["user_id_column_name"] = "user_id"
            if "session_id" in trace_data:
                config["session_id_column_name"] = "session_id"
            if "context" in trace_data:
                config["context_column_name"] = "context"

            # Send using our own client (we disabled auto-publish, so we always upload here)
            if self._client:
                self._client.inference_pipelines.data.stream(
                    inference_pipeline_id=self._inference_pipeline_id,
                    rows=[trace_data],
                    config=config,
                )

        except Exception:  # noqa: BLE001
            logger.warning("Openlayer tracing/upload failed", exc_info=True)
        finally:
            # Always clean up SDK context regardless of early returns or exceptions
            self._cleanup_sdk_context()

    def _cleanup_sdk_context(self) -> None:
        try:
            self._openlayer_tracer._current_trace.set(None)
            self._openlayer_tracer._current_step.set(None)
        except Exception:  # noqa: BLE001, S110
            pass

    def _collect_step_names(self, trace_data: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Collect agent and tool step names from the serialized trace steps tree."""
        agent_names: list[str] = []
        tool_names: list[str] = []
        agent_val = self._openlayer_enums.StepType.AGENT.value
        tool_val = self._openlayer_enums.StepType.TOOL.value

        def _walk(steps: list[dict[str, Any]]) -> None:
            for step in steps:
                st = step.get("type")
                name = step.get("name", "")
                if st == agent_val and name:
                    agent_names.append(name)
                elif st == tool_val and name:
                    tool_names.append(name)
                nested = step.get("steps")
                if nested:
                    _walk(nested)

        _walk(trace_data.get("steps", []))
        return agent_names, tool_names

    def _aggregate_llm_data(self, trace_data: dict[str, Any]) -> None:
        """Aggregate token and model data from nested ChatCompletionStep dicts.

        post_process_trace() only reads tokens/cost from processed_steps[0] (the root
        UserCallStep), so nested ChatCompletionStep data is lost at the trace level.
        This walks the steps tree and sums tokens/cost from all chat_completion steps,
        and captures the model/provider from the first one found.
        """
        steps_list = trace_data.get("steps", [])
        if not steps_list:
            return

        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0
        total_cost = 0.0
        model = None
        provider = None
        model_parameters = None

        def _walk_steps(steps: list[dict[str, Any]]) -> None:
            nonlocal total_prompt_tokens, total_completion_tokens, total_tokens
            nonlocal total_cost, model, provider, model_parameters

            for step in steps:
                if step.get("type") == self._openlayer_enums.StepType.CHAT_COMPLETION.value:
                    total_prompt_tokens += step.get("promptTokens") or 0
                    total_completion_tokens += step.get("completionTokens") or 0
                    total_tokens += step.get("tokens") or 0
                    total_cost += step.get("cost") or 0.0

                    # Capture model info from the first ChatCompletionStep
                    if model is None and step.get("model"):
                        model = step["model"]
                    if provider is None and step.get("provider"):
                        provider = step["provider"]
                    if model_parameters is None and step.get("modelParameters"):
                        model_parameters = step["modelParameters"]

                # Recurse into nested steps
                nested = step.get("steps")
                if nested:
                    _walk_steps(nested)

        _walk_steps(steps_list)

        # Only override trace-level values if we found actual data
        if total_tokens > 0:
            trace_data["tokens"] = total_tokens
            trace_data["promptTokens"] = total_prompt_tokens
            trace_data["completionTokens"] = total_completion_tokens
        if total_cost > 0:
            trace_data["cost"] = total_cost
        if model:
            trace_data["model"] = model
        if provider:
            trace_data["provider"] = provider
        if model_parameters:
            trace_data["modelParameters"] = model_parameters

    def _extract_flow_metadata(
        self,
        components: dict[str, Any],
        error: Exception | None = None,
    ) -> FlowMetadata:
        metadata: FlowMetadata = {
            "chat_output": "Flow completed",
            "chat_input": {},
            "start_time": None,
            "end_time": None,
            "error": None,
        }

        # Handle error case - set output to error message
        if error:
            metadata["error"] = str(error)
            metadata["chat_output"] = f"Error: {error}"

        for trace_id, step in components.items():
            trace_type = self.component_trace_types.get(trace_id)
            # Extract Chat Output (only if no error, since error takes precedence)
            if step.name in CHAT_OUTPUT_NAMES and not error:
                chat_output = self._safe_get_input(step, "input_value")
                if chat_output:
                    metadata["chat_output"] = chat_output

            # Extract Agent response as fallback (when no Chat Output component)
            if (
                trace_type == "agent"
                and not error
                and metadata["chat_output"] == "Flow completed"
                and hasattr(step, "output")
                and step.output
            ):
                if isinstance(step.output, str):
                    metadata["chat_output"] = step.output
                elif isinstance(step.output, dict):
                    response = step.output.get("response")
                    if response:
                        metadata["chat_output"] = response if isinstance(response, str) else str(response)

            # Extract Chat Input
            if step.name in CHAT_INPUT_NAMES:
                input_val = self._safe_get_input(step, "input_value")
                if input_val:
                    metadata["chat_input"] = {"flow_input": input_val}

            # Extract timing
            if (
                hasattr(step, "start_time")
                and step.start_time
                and (metadata["start_time"] is None or step.start_time < metadata["start_time"])
            ):
                metadata["start_time"] = step.start_time
            if (
                hasattr(step, "end_time")
                and step.end_time
                and (metadata["end_time"] is None or step.end_time > metadata["end_time"])
            ):
                metadata["end_time"] = step.end_time

        return metadata

    def _safe_get_input(self, step: Any, key: str, default: Any = None) -> Any:
        if not hasattr(step, "inputs") or not isinstance(step.inputs, dict):
            return default
        return step.inputs.get(key, default)

    def _integrate_langchain_traces(self) -> None:
        """Merge LangChain handler traces into the appropriate component step.

        Also converts LangChain objects in the steps to JSON-serializable format,
        since _convert_step_objects_recursively is skipped when _has_external_trace=True.
        """
        if not self.langchain_handler or not hasattr(self.langchain_handler, "_traces_by_root"):
            return

        langchain_traces = self.langchain_handler._traces_by_root
        if not langchain_traces:
            return

        # Build a default target: prefer agent, then llm/chain component
        default_target = None
        for trace_id, component_step in self.component_steps.items():
            if self.component_trace_types.get(trace_id) == "agent":
                default_target = component_step
                break
        if default_target is None:
            for trace_id, component_step in self.component_steps.items():
                if self.component_trace_types.get(trace_id) in ("llm", "chain"):
                    default_target = component_step
                    break

        # Integrate each LangChain root trace into the matching component step.
        # When multiple roots exist, try to match each root to its component;
        # fall back to the default target if no match is found.
        for root_id, lc_trace in langchain_traces.items():
            target = self.component_steps.get(str(root_id)) or default_target
            for lc_step in lc_trace.steps:
                self._convert_langchain_step(lc_step)
                self._fix_tool_step_names(lc_step)
                if target:
                    target.add_nested_step(lc_step)

        # Clear handler's traces after integration
        self.langchain_handler._traces_by_root.clear()

    def _fix_tool_step_names(self, step: Any) -> None:
        """Fix generic 'Tool' names on ToolStep objects from the LangChain handler.

        The Openlayer SDK's LangChain callback falls back to 'Tool' when the
        `name` kwarg is absent.  The actual tool name lives in the step's
        metadata (display_name, serialized.name, or tags).
        """
        if (
            hasattr(step, "step_type")
            and hasattr(step.step_type, "value")
            and step.step_type.value == "tool"
            and step.name == "Tool"
            and step.metadata
        ):
            tool_name = step.metadata.get("display_name") or step.metadata.get("tool_name")
            if not tool_name and isinstance(step.metadata.get("serialized"), dict):
                tool_name = step.metadata["serialized"].get("name")
            if not tool_name:
                tags = step.metadata.get("tags")
                if tags and isinstance(tags, list) and tags:
                    tool_name = tags[0]
            if tool_name:
                step.name = tool_name
                if hasattr(step, "function_name") and step.function_name == "Tool":
                    step.function_name = tool_name

        for nested in getattr(step, "steps", []):
            self._fix_tool_step_names(nested)

    def _convert_langchain_step(self, step: Any) -> None:
        """Convert LangChain objects in a step to JSON-serializable format.

        Delegates to the handler's _convert_step_objects_recursively when available,
        falling back to our own _convert_to_openlayer_types for inputs/output.
        """
        handler = self.langchain_handler
        if handler is not None and hasattr(handler, "_convert_step_objects_recursively"):
            handler._convert_step_objects_recursively(step)
        else:
            # Fallback: convert inputs and output ourselves
            if step.inputs is not None:
                step.inputs = (
                    self._convert_to_openlayer_types(step.inputs)
                    if isinstance(step.inputs, dict)
                    else self._convert_to_openlayer_type(step.inputs)
                )
            if step.output is not None:
                step.output = self._convert_to_openlayer_type(step.output)
            for nested_step in getattr(step, "steps", []):
                self._convert_langchain_step(nested_step)

    def _resolve_root_input(
        self,
        flow_inputs: dict[str, Any] | None,
        extracted_metadata: FlowMetadata,
    ) -> dict[str, Any]:
        """Determine the root input from flow-level inputs or component extraction."""
        root_input = extracted_metadata["chat_input"]
        if flow_inputs:
            if "input_value" in flow_inputs:
                root_input = {"flow_input": flow_inputs["input_value"]}
            elif not root_input:
                # Look for input_value inside Chat Input / Agent component data
                extracted = self._extract_input_from_components(flow_inputs)
                root_input = {"flow_input": extracted if extracted else self._convert_to_openlayer_types(flow_inputs)}
        return root_input

    def _extract_input_from_components(self, flow_inputs: dict[str, Any]) -> str | None:
        """Extract user input from nested component inputs in flow_inputs.

        Searches Chat Input components first, then Agent components.
        """
        # First try Chat Input components by name
        for key, value in flow_inputs.items():
            if isinstance(value, dict) and any(name in key for name in CHAT_INPUT_NAMES):
                input_val = value.get("input_value")
                if input_val:
                    return self._convert_to_openlayer_type(input_val)
        # Fall back to agent components by trace_type
        agent_ids = {tid for tid, tt in self.component_trace_types.items() if tt == "agent"}
        for key, value in flow_inputs.items():
            if isinstance(value, dict) and any(aid in key for aid in agent_ids):
                input_val = value.get("input_value")
                if input_val:
                    return self._convert_to_openlayer_type(input_val)
        return None

    def _resolve_root_output(
        self,
        flow_outputs: dict[str, Any] | None,
        error: Exception | None,
        extracted_metadata: FlowMetadata,
    ) -> str:
        """Determine the root output from flow outputs, error, or component extraction."""
        root_output = extracted_metadata["chat_output"]
        if not error and flow_outputs:
            # Look for Chat Output component's message in flow_outputs
            chat_output_found = False
            for key, value in flow_outputs.items():
                if any(name in key for name in CHAT_OUTPUT_NAMES) and isinstance(value, dict) and "message" in value:
                    chat_output_msg = self._convert_to_openlayer_type(value["message"])
                    if chat_output_msg:
                        root_output = chat_output_msg
                        chat_output_found = True
                        break

            # If no Chat Output found, try Agent component output (by trace_type)
            if not chat_output_found:
                agent_ids = {tid for tid, tt in self.component_trace_types.items() if tt == "agent"}
                for key, value in flow_outputs.items():
                    if isinstance(value, dict) and any(aid in key for aid in agent_ids):
                        response = value.get("response")
                        if response:
                            root_output = self._convert_to_openlayer_type(response)
                            chat_output_found = True
                            break

            # If still not found, try common output keys at top level
            if not chat_output_found:
                converted_outputs = self._convert_to_openlayer_types(flow_outputs)
                for key_name in ("message", "response", "result", "output"):
                    if key_name in converted_outputs:
                        root_output = converted_outputs[key_name]
                        break

        return root_output

    def _build_and_add_hierarchy(
        self,
        flow_inputs: dict[str, Any] | None = None,
        flow_outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        flow_metadata: dict[str, Any] | None = None,
    ) -> list[Any]:
        self._integrate_langchain_traces()

        flow_name, _ = self._parse_trace_name(self.trace_name)

        # Extract metadata from components with error handling
        extracted_metadata = self._extract_flow_metadata(self.component_steps, error=error)

        root_input = self._resolve_root_input(flow_inputs, extracted_metadata)
        root_output = self._resolve_root_output(flow_outputs, error, extracted_metadata)

        # Build root step metadata
        root_step_metadata = {"flow_name": flow_name}
        if flow_metadata:
            root_step_metadata.update(self._convert_to_openlayer_types(flow_metadata))
        error_msg = extracted_metadata.get("error")
        if error_msg:
            root_step_metadata["error"] = error_msg

        root_step = self._openlayer_steps.UserCallStep(
            name=flow_name,
            inputs=root_input,
            output=root_output,
            metadata=root_step_metadata,
        )

        # Set timing from extracted metadata
        if extracted_metadata["start_time"] and extracted_metadata["end_time"]:
            root_step.start_time = extracted_metadata["start_time"]
            root_step.end_time = extracted_metadata["end_time"]
            root_step.latency = int((root_step.end_time - root_step.start_time) * 1000)

        for step in self.component_steps.values():
            root_step.add_nested_step(step)

        # Add root to trace
        if self.trace_obj is not None:
            self.trace_obj.add_step(root_step)

        return [root_step]

    # Keys worth keeping in step metadata (lightweight context for debugging)
    _METADATA_KEEP_KEYS = frozenset(
        {
            "display_name",
            "tool_name",
            "tool_description",
            "model_name",
            "model_provider",
            "temperature",
            "error",
            "logs",
            "tags",
        }
    )

    def _slim_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        """Return a lightweight version of metadata for the step payload.

        Only keeps a curated set of keys to avoid bloating the trace with
        large serialized objects, full tool code, etc.
        """
        if not metadata:
            return {}
        return {
            str(k): self._convert_to_openlayer_type(v) for k, v in metadata.items() if k in self._METADATA_KEEP_KEYS
        }

    def _convert_to_openlayer_types(self, io_dict: dict[str, Any]) -> dict[str, Any]:
        if io_dict is None:
            return {}
        return {str(key): self._convert_to_openlayer_type(value) for key, value in io_dict.items()}

    def _convert_to_openlayer_type(self, value: Any) -> Any:
        """Convert LangFlow/LangChain types to Openlayer-compatible primitives.

        Args:
            value: Input value to convert

        Returns:
            Converted value suitable for Openlayer ingestion
        """
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

        # Handle Pydantic models
        if hasattr(value, "model_dump") and callable(value.model_dump) and not isinstance(value, type):
            try:
                return self._convert_to_openlayer_type(value.model_dump())
            except Exception:  # noqa: BLE001, S110
                pass

        # Handle LangChain tools
        if hasattr(value, "name") and hasattr(value, "description"):
            try:
                return {
                    "name": str(value.name),
                    "description": str(value.description) if value.description else None,
                }
            except Exception:  # noqa: BLE001, S110
                pass

        # Fallback to string for all other types (including generators, None, etc.)
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
        except Exception:  # noqa: BLE001
            return None
        else:
            return handler

    @staticmethod
    def _sanitize_flow_name(flow_name: str) -> str:
        """Sanitize flow name for use in environment variable names.

        Converts to uppercase and replaces non-alphanumeric characters with underscores.
        Example: "My Flow-Name" -> "MY_FLOW_NAME"
        """
        # Replace non-alphanumeric characters with underscores
        sanitized = re.sub(r"[^a-zA-Z0-9]+", "_", flow_name)
        # Remove leading/trailing underscores and convert to uppercase
        return sanitized.strip("_").upper()

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
            flow_name, _ = OpenlayerTracer._parse_trace_name(trace_name)

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
                except json.JSONDecodeError:
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
