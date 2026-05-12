import logging
import re
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any, ClassVar

from langchain_core.agents import AgentFinish
from langchain_core.runnables import Runnable, RunnableConfig

from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.inputs.inputs import BoolInput, DataInput, DropdownInput, MessageTextInput, MultilineInput
from lfx.io import HandleInput, IntInput
from lfx.schema.message import Message
from lfx.template.field.base import RangeSpec


class OpenDsStarAgentRunnable(Runnable):
    """Runnable wrapper for OpenDsStarAgent that can emit LangChain events."""

    def __init__(self, agent):
        super().__init__()
        self.agent = agent

    def _build_graph_input(self, query: str, agent: Any | None = None) -> dict[str, Any]:
        """Build the input dict for the underlying LangGraph graph.

        Centralizes the state dict so all call sites (invoke, astream,
        astream_events, run_agent) stay in sync when fields change.
        """
        a = agent or self.agent
        return {
            "user_query": query,
            "max_steps": a.max_steps,
            "code_mode": a.code_mode,
            "output_max_length": a.output_max_length,
            "logs_max_length": a.logs_max_length,
            "tools": a._graph.tools,  # noqa: SLF001
            "max_debug_tries": a.max_debug_tries,
        }

    def invoke(
        self,
        input_value: dict[str, Any] | str,
        config: RunnableConfig | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """Invoke the underlying graph synchronously."""
        if isinstance(input_value, dict) and "input" in input_value:
            query = input_value["input"]
        elif isinstance(input_value, str):
            query = input_value
        else:
            query = str(input_value)

        recursion_limit = max(100, self.agent.max_steps * 10)
        merged_config = {"recursion_limit": recursion_limit}
        if config:
            merged_config.update(config)

        return self.agent._graph.graph.invoke(  # noqa: SLF001
            self._build_graph_input(query),
            config=merged_config,
        )

    async def astream(
        self,
        input_value: dict[str, Any] | str,
        config: RunnableConfig | None = None,
        **_kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async stream the agent output node by node.

        Yields intermediate results as each node in the graph executes,
        allowing real-time display of the agent's progress.

        Note: LangGraph's stream() is synchronous, so we wrap it in an async generator.
        """
        import asyncio

        # Extract the input message
        if isinstance(input_value, dict) and "input" in input_value:
            query = input_value["input"]
        elif isinstance(input_value, str):
            query = input_value
        else:
            query = str(input_value)

        # Create the stream generator
        recursion_limit = max(100, self.agent.max_steps * 10)
        merged_config = {"recursion_limit": recursion_limit}
        if config:
            merged_config.update(config)
        stream_gen: Iterator[dict[str, Any]] = self.agent._graph.graph.stream(  # noqa: SLF001
            self._build_graph_input(query),
            config=merged_config,
        )

        # Yield chunks from the synchronous stream using asyncio.to_thread
        last_chunk = None
        while True:
            try:
                # Get next chunk in a thread to avoid blocking
                chunk = await asyncio.to_thread(next, stream_gen, StopIteration)
                if chunk is StopIteration:
                    break

                last_chunk = chunk
                # Each chunk is a dict with node name as key and state update as value
                yield {"chunk": chunk, "type": "node_update"}
                # Allow other async tasks to run
                await asyncio.sleep(0)
            except StopIteration:
                break

        # Yield the final state from the last streamed chunk
        if last_chunk is not None:
            yield {"chunk": last_chunk, "type": "final"}

    async def astream_events(
        self,
        input_value: dict[str, Any] | str,
        config: RunnableConfig | None = None,
        **_kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async stream events in LangChain format for Langflow compatibility.

        This converts LangGraph's stream output to LangChain's astream_events format
        so it works with Langflow's process_agent_events().
        """
        # Extract the input message
        if isinstance(input_value, dict) and "input" in input_value:
            query = input_value["input"]
        elif isinstance(input_value, str):
            query = input_value
        else:
            query = str(input_value)

        # Generate a run_id for this execution
        run_id = str(uuid.uuid4())

        # Emit start event (include chat_history for UI input block consistency)
        yield {
            "event": "on_chain_start",
            "run_id": run_id,
            "name": "OpenDsStarAgent",
            "tags": [],
            "metadata": {},
            "data": {"input": {"input": query, "chat_history": []}},
        }

        # If the underlying agent/graph is unavailable, fall back to a simple invoke-based stream
        if not getattr(self, "agent", None):
            result = await self.ainvoke({"input": query}, config=config)
            output_text = result.get("output", "") if isinstance(result, dict) else str(result)
            yield {
                "event": "on_chain_stream",
                "run_id": run_id,
                "name": "OpenDsStarAgent",
                "tags": [],
                "metadata": {},
                "data": {"chunk": {"output": output_text}},
            }
            yield {
                "event": "on_chain_end",
                "run_id": run_id,
                "name": "OpenDsStarAgent",
                "tags": [],
                "metadata": {},
                "data": {"output": AgentFinish(return_values={"output": output_text}, log=output_text)},
            }
            return

        # Prepare config for the graph - merge with any provided config
        recursion_limit = max(100, self.agent.max_steps * 10)
        graph_config = {"recursion_limit": recursion_limit}
        if config:
            graph_config.update(config)

        # Stream from the underlying graph using "values" mode to get full state after each node
        def _stream_graph():
            """Synchronous generator that streams from the graph."""
            return self.agent._graph.graph.stream(  # noqa: SLF001
                self._build_graph_input(query),
                config=graph_config,
                stream_mode="values",  # Get full state after each node
            )

        # Process chunks from the synchronous stream
        last_state = None
        last_trajectory_len = 0

        async for chunk in self._async_generator_wrapper(_stream_graph()):
            last_state = chunk

            # Stream trajectory updates as they happen
            trajectory = chunk.get("trajectory", [])
            if len(trajectory) > last_trajectory_len:
                # New trajectory events - format them for streaming and tool events
                new_events = trajectory[last_trajectory_len:]
                last_trajectory_len = len(trajectory)

                for event in new_events:
                    node_name = self._normalize_node_name(
                        event.get("node_name") or event.get("node") or event.get("event_type", "step")
                    )
                    note = event.get("note") or event.get("planned_step") or event.get("code") or event.get("logs")
                    tool_run_id = str(uuid.uuid4())

                    # Start tool event
                    yield {
                        "event": "on_tool_start",
                        "run_id": tool_run_id,
                        "name": node_name,
                        "tags": [],
                        "metadata": {},
                        "data": {"input": {}},
                    }

                    # End tool event with output (prefer note/logs/code)
                    yield {
                        "event": "on_tool_end",
                        "run_id": tool_run_id,
                        "name": node_name,
                        "tags": [],
                        "metadata": {},
                        "data": {"output": note or ""},
                    }

                # Also emit a chain stream chunk summarizing notes for backwards compatibility
                trajectory_text = "\n".join(
                    [
                        f"[{self._normalize_node_name(event.get('event_type', 'unknown'))}]"
                        f" {self._normalize_node_name(event.get('note', ''))}"
                        for event in new_events
                    ]
                )

                formatted_chunk = {"output": trajectory_text}

                yield {
                    "event": "on_chain_stream",
                    "run_id": run_id,
                    "name": "OpenDsStarAgent",
                    "tags": [],
                    "metadata": {},
                    "data": {"chunk": formatted_chunk},
                }

        # Extract final answer from the last state
        final_output = ""
        if last_state:
            # Try final_answer first (set by finalizer), then answer (legacy)
            final_output = last_state.get("final_answer") or last_state.get("answer", "")

        # Emit end event with AgentFinish format that handle_on_chain_end expects
        yield {
            "event": "on_chain_end",
            "run_id": run_id,
            "name": "OpenDsStarAgent",
            "tags": [],
            "metadata": {},
            "data": {"output": AgentFinish(return_values={"output": final_output}, log=final_output)},
        }

    async def _async_generator_wrapper(self, sync_gen):
        """Wrap a synchronous generator to make it async."""
        import asyncio

        loop = asyncio.get_running_loop()

        while True:
            try:
                # Run next() in a thread pool to avoid blocking
                chunk = await loop.run_in_executor(None, next, sync_gen, StopIteration)
                if chunk is StopIteration:
                    break
                yield chunk
            except StopIteration:
                break


class OpenDsStarAgentComponent(ToolCallingAgentComponent):
    code_class_base_inheritance: ClassVar[str] = "Component"
    display_name: str = "OpenDsStar Agent"
    description: str = "A tool-based DS-Star agent using LangGraph for complex data science tasks."
    documentation: str = "https://github.com/IBM/OpenDsStar"
    icon = "bot"
    beta = True
    name = "OpenDsStarAgent"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="Message or query to send to the agent",
            tool_mode=True,
        ),
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
            info="Language model to use for the OpenDsStar agent",
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=False,
            info="These are the tools that the agent can use to help with tasks.",
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            value=10,
            advanced=True,
            range_spec=RangeSpec(min=1, max=100, step=1),
        ),
        DropdownInput(
            name="code_mode",
            display_name="Code Execution Mode",
            options=["stepwise", "full"],
            value="stepwise",
            advanced=True,
            info="Code execution mode: 'stepwise' executes each step separately, 'full' executes all steps together",
        ),
        MessageTextInput(
            name="system_prompt",
            display_name="System Message",
            info="System message to customize agent behavior",
            advanced=True,
        ),
        BoolInput(
            name="handle_parsing_errors",
            display_name="Handle Parse Errors",
            value=True,
            advanced=True,
            info="Should the Agent fix errors when reading user input for better processing?",
        ),
        IntInput(
            name="code_timeout",
            display_name="Code Timeout (seconds)",
            value=60,
            advanced=True,
            range_spec=RangeSpec(min=10, max=300, step=10),
            info="Maximum execution time in seconds for each code step.",
        ),
        BoolInput(name="verbose", display_name="Verbose", value=True, advanced=True),
        DataInput(
            name="chat_history",
            display_name="Chat Memory",
            is_list=True,
            advanced=True,
            info="This input stores the chat history, allowing the agent to remember previous conversations.",
        ),
        MultilineInput(
            name="agent_description",
            display_name="Agent Description",
            info="The description of the agent. This is only used when in Tool Mode.",
            advanced=True,
            value="A helpful assistant with access to the following tools:",
        ),
    ]

    async def message_response(self) -> Message:
        """Run the agent and return the response.

        Override parent to ensure tools are properly loaded before building the agent.
        This is critical because tools need to be available when build_agent() is called.
        """
        logger = logging.getLogger(__name__)

        # Ensure tools are initialized (convert None to empty list)
        if not hasattr(self, "tools") or self.tools is None:
            logger.warning("OpenDsStarAgent - tools attribute not set, initializing to empty list")
            self.tools = []

        # Clean up tools list - remove empty strings or None which Langflow
        # sometimes passes when the input is functionally empty
        if isinstance(self.tools, list):
            self.tools = [t for t in self.tools if t and not (isinstance(t, str) and not t.strip())]
        elif isinstance(self.tools, str) and not self.tools.strip():
            self.tools = []

        logger.info("OpenDsStarAgent.message_response - Tools available: %d", len(self.tools))
        if self.tools:
            for idx, tool in enumerate(self.tools):
                tool_name = getattr(tool, "name", "UNKNOWN")
                logger.info("  Tool %d: %s", idx + 1, tool_name)

        # Set shared callbacks for tracing the tools used by the agent
        if self.tools:
            self.set_tools_callbacks(self.tools, self._get_shared_callbacks())

        # Now call parent's message_response which calls build_agent() -> run_agent()
        agent = self.build_agent()
        message = await self.run_agent(agent=agent)

        self.status = message
        return message

    def build_agent(self) -> Runnable:  # type: ignore[override]
        """Build the OpenDsStar agent.

        Override parent's build_agent to return the OpenDsStar agent runnable directly.
        We return a Runnable (not AgentExecutor) because OpenDsStar has its own
        execution logic via LangGraph and doesn't need AgentExecutor's wrapping.

        The parent's run_agent() method can handle a Runnable directly.

        Returns:
            Runnable: The OpenDsStarAgentRunnable
        """
        # Use base validation, then wrap with our runnable that now emits events
        self.validate_tool_names()
        return self.create_agent_runnable()

    async def run_agent(self, agent: Runnable) -> Message:
        """Stream LangGraph trajectory directly. Bypasses process_agent_events."""
        import asyncio
        import uuid
        from typing import cast

        from lfx.base.agents.utils import get_chat_output_sender_name
        from lfx.schema.content_block import ContentBlock
        from lfx.schema.content_types import TextContent
        from lfx.schema.message import Message
        from lfx.utils.constants import MESSAGE_SENDER_AI

        logger = logging.getLogger(__name__)

        # Normalize input text
        if isinstance(self.input_value, Message):
            lc_message = self.input_value.to_lc_message()
            if hasattr(lc_message, "content") and isinstance(lc_message.content, str):
                input_text = lc_message.content
            else:
                input_text = str(lc_message.content) if getattr(lc_message, "content", None) else str(lc_message)
        else:
            input_text = str(self.input_value) if self.input_value else ""

        if not input_text:
            msg = "Input text is empty"
            raise ValueError(msg)

        sender_name = get_chat_output_sender_name(self) or self.display_name or "AI"
        session_id = getattr(getattr(self, "graph", None), "session_id", getattr(self, "_session_id", uuid.uuid4()))

        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=sender_name,
            text="",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=session_id,
        )

        # Send initial message
        agent_message = await self.send_message(message=agent_message)

        last_trajectory_len = 0
        final_answer = ""
        last_event_time = None

        try:
            logger.info("Starting direct trajectory streaming")

            # Get the actual OpenDsStarAgent from the runnable wrapper
            actual_agent = cast("Any", agent).agent if hasattr(agent, "agent") else agent
            exec_logger = logging.getLogger(__name__)

            try:
                from agents.ds_star.ds_star_execute_env import set_main_event_loop
            except ImportError:
                logger.debug("ds_star_execute_env not available")
            else:
                try:
                    set_main_event_loop(asyncio.get_running_loop())
                except Exception:  # noqa: BLE001
                    logger.warning("Failed to set main event loop", exc_info=True)

            # Stream from the graph directly
            recursion_limit = max(100, actual_agent.max_steps * 10)
            stream_gen = actual_agent._graph.graph.stream(  # noqa: SLF001
                agent._build_graph_input(input_text, actual_agent),  # noqa: SLF001
                config={"recursion_limit": recursion_limit},
                stream_mode="values",
            )

            while True:
                try:
                    chunk = await asyncio.to_thread(next, stream_gen, StopIteration)
                    if chunk is StopIteration:
                        break
                except StopIteration:
                    break

                trajectory = chunk.get("trajectory", [])
                if len(trajectory) > last_trajectory_len:
                    new_events = trajectory[last_trajectory_len:]
                    last_trajectory_len = len(trajectory)

                    for event in new_events:
                        import re

                        from lfx.schema.content_types import CodeContent, ToolContent

                        step_idx = event.get("step_idx", "?")
                        node_name = self._normalize_node_name(event.get("node_name", event.get("node", "")))
                        last_step = event.get("last_step", {})
                        current_time = event.get("time")

                        duration_ms = None
                        if current_time:
                            if last_event_time is not None:
                                delta = current_time - last_event_time
                                if delta >= 0:
                                    duration_ms = int(delta * 1000)
                            last_event_time = current_time

                        exec_logger.debug("trajectory event node=%s step=%s", node_name, step_idx)
                        raw_event_type = event.get("event_type", "")
                        event_type_raw = raw_event_type.strip() if isinstance(raw_event_type, str) else raw_event_type
                        event_type = self._normalize_node_name(event_type_raw)
                        event_note = event.get("note", "")
                        plan = event.get("planned_step", "")
                        code = event.get("code", "")
                        node_name_lower = node_name.lower() if isinstance(node_name, str) else ""
                        is_execute_node = "execute" in node_name_lower
                        logs = event.get("logs", last_step.get("logs", "")) if is_execute_node else ""
                        verification_result = event.get("verification_result")
                        verifier_sufficient = event.get("sufficient", False) if "n_verify" in node_name_lower else None
                        verifier_explanation = event.get("explanation", "") if "n_verify" in node_name_lower else ""
                        router_action = event.get("decision", "") if "n_route" in node_name_lower else ""
                        router_explanation = event.get("explanation", "") if "n_route" in node_name_lower else ""
                        fix_idx = event.get("fix_index") if "n_route" in node_name_lower else None
                        finalizer = event.get("finalizer", "") if "n_finalize" in node_name_lower else ""
                        execution_error = (
                            event.get("had_error", last_step.get("execution_error", "")) if is_execute_node else ""
                        )
                        fatal_error = event.get("fatal_error", "")

                        def clean_logs(logs_text: str) -> str:
                            if not logs_text:
                                return logs_text
                            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
                            logs_no_ansi = ansi_escape.sub("", logs_text)
                            lines = logs_no_ansi.split("\n")
                            cleaned_lines = []
                            for line in lines:
                                if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", line):
                                    continue
                                if line.strip() == "[STDERR]":
                                    continue
                                if not line.strip():
                                    continue
                                cleaned_lines.append(line)
                            return "\n".join(cleaned_lines).strip()

                        def truncate_text(text: str, max_length: int = 500) -> str:
                            if len(text) > max_length:
                                return text[:max_length] + "..."
                            return text

                        node_title = node_name or event_type or "unknown"
                        node_title = self._normalize_node_name(node_title)
                        summary_parts = []
                        if event_type:
                            summary_parts.append(f"Type: {event_type}")
                        if event_note:
                            summary_parts.append(f"Note: {event_note}")
                        if not summary_parts:
                            summary_parts.append("Node executed")

                        node_tool_input = {
                            "step_idx": step_idx,
                            "node": node_name,
                        }
                        if event_type:
                            node_tool_input["event_type"] = event_type
                        if event_note:
                            node_tool_input["note"] = truncate_text(str(event_note), 2000)
                        if plan and plan.strip():
                            node_tool_input["planned_step"] = truncate_text(plan.strip(), 4000)
                        if code and code.strip():
                            node_tool_input["code"] = truncate_text(code.strip(), 4000)
                        if is_execute_node and logs and logs.strip():
                            node_tool_input["logs"] = truncate_text(clean_logs(logs), 2000)
                        if verification_result is not None:
                            node_tool_input["verification_result"] = verification_result
                        if verifier_sufficient is not None:
                            node_tool_input["sufficient"] = verifier_sufficient
                        if verifier_explanation and verifier_explanation.strip():
                            node_tool_input["verifier_explanation"] = truncate_text(verifier_explanation.strip(), 2000)
                        if router_action and router_action.strip():
                            node_tool_input["router_action"] = router_action
                        if router_explanation and router_explanation.strip():
                            node_tool_input["router_explanation"] = truncate_text(router_explanation.strip(), 2000)
                        if fix_idx is not None:
                            node_tool_input["fix_index"] = fix_idx
                        if finalizer and finalizer.strip():
                            node_tool_input["finalizer"] = truncate_text(finalizer.strip(), 2000)
                        if fatal_error and fatal_error.strip():
                            node_tool_input["fatal_error"] = truncate_text(fatal_error.strip(), 2000)
                        agent_message.content_blocks[0].contents.append(
                            ToolContent(
                                type="tool_use",
                                name=node_title,
                                tool_input=node_tool_input,
                                output="\n".join(summary_parts),
                                error=None,
                                header={"title": f"Executed **{node_title}**", "icon": "GitBranch"},
                                duration=duration_ms,
                            )
                        )

                        if plan and plan.strip():
                            agent_message.content_blocks[0].contents.append(
                                TextContent(
                                    text=plan.strip(),
                                    header={"title": "Plan", "icon": "FileText"},
                                    duration=duration_ms,
                                )
                            )

                        if code and code.strip() and not is_execute_node:
                            agent_message.content_blocks[0].contents.append(
                                CodeContent(
                                    code=code.strip(),
                                    language="python",
                                    type="code",
                                    header={"title": "Code", "icon": "Code"},
                                    duration=duration_ms,
                                )
                            )

                        if is_execute_node:
                            execution_code = event.get("code", "") or last_step.get("code", "")
                            if execution_code and str(execution_code).strip():
                                agent_message.content_blocks[0].contents.append(
                                    CodeContent(
                                        code=str(execution_code).strip(),
                                        language="python",
                                        type="code",
                                        header={"title": "Executed Code", "icon": "Code"},
                                        duration=duration_ms,
                                    )
                                )

                            execution_output = ""
                            if logs and logs.strip():
                                execution_output = truncate_text(clean_logs(logs), 500)
                            elif execution_error:
                                execution_output = f"Execution error: {execution_error}"
                            else:
                                execution_output = "Code executed. No output was produced."

                            execution_tool_input = {
                                "step_idx": step_idx,
                                "node": node_name,
                                "code": truncate_text(str(execution_code), 4000) if execution_code else "",
                            }

                            agent_message.content_blocks[0].contents.append(
                                ToolContent(
                                    type="tool_use",
                                    name="Code Execution",
                                    tool_input=execution_tool_input,
                                    output=execution_output,
                                    error=None,
                                    header={"title": "Executed **Code Execution**", "icon": "Hammer"},
                                    duration=duration_ms,
                                )
                            )

                        if logs and logs.strip():
                            cleaned = clean_logs(logs)
                            if cleaned:
                                agent_message.content_blocks[0].contents.append(
                                    TextContent(
                                        text=truncate_text(cleaned, 500),
                                        type="text",
                                        header={"title": "Logs", "icon": "Terminal"},
                                        duration=duration_ms,
                                    )
                                )

                        if verification_result is not None:
                            agent_message.content_blocks[0].contents.append(
                                TextContent(
                                    text=f"Verification: {verification_result}",
                                    type="text",
                                    header={"title": "Verification", "icon": "CheckSquare"},
                                    duration=duration_ms,
                                )
                            )

                        if verifier_explanation and verifier_explanation.strip():
                            verifier_text_parts = []
                            verifier_text_parts.append(
                                f"Sufficient: {verifier_sufficient if verifier_sufficient is not None else False}"
                            )
                            if verifier_explanation:
                                verifier_text_parts.append(f"\nExplanation: {verifier_explanation}")

                            verifier_text = "\n".join(verifier_text_parts)
                            agent_message.content_blocks[0].contents.append(
                                TextContent(
                                    text=verifier_text,
                                    type="text",
                                    header={"title": "Verifier", "icon": "CheckCircle"},
                                    duration=duration_ms,
                                )
                            )

                        if router_action and router_action.strip():
                            router_text_parts = [f"Action: {router_action}"]
                            if router_explanation and router_explanation.strip():
                                router_text_parts.append(f"\nExplanation: {router_explanation}")

                            router_text = "\n".join(router_text_parts)
                            agent_message.content_blocks[0].contents.append(
                                TextContent(
                                    text=router_text,
                                    type="text",
                                    header={"title": "Router", "icon": "GitBranch"},
                                    duration=duration_ms,
                                )
                            )

                        if fix_idx is not None:
                            agent_message.content_blocks[0].contents.append(
                                TextContent(
                                    text=f"Fix Index: {fix_idx}",
                                    type="text",
                                    header={"title": "Fix Index", "icon": "Tool"},
                                    duration=duration_ms,
                                )
                            )

                        if finalizer and finalizer.strip():
                            agent_message.content_blocks[0].contents.append(
                                TextContent(
                                    text=finalizer,
                                    type="text",
                                    header={"title": "Finalizer", "icon": "Flag"},
                                    duration=duration_ms,
                                )
                            )

                        if fatal_error and fatal_error.strip():
                            agent_message.content_blocks[0].contents.append(
                                TextContent(
                                    text=f"Error: {fatal_error}",
                                    type="text",
                                    header={"title": "Error", "icon": "AlertTriangle"},
                                    duration=duration_ms,
                                )
                            )

                    agent_message = await self.send_message(message=agent_message, skip_db_update=False)

                if chunk.get("final_answer"):
                    final_answer = chunk["final_answer"]
                    final_answer = self._add_media_from_text(agent_message, final_answer)

            final_answer = self._add_media_from_text(agent_message, final_answer)
            agent_message.text = final_answer
            agent_message.properties.state = "complete"
            agent_message = await self.send_message(message=agent_message)

        except Exception as e:
            logger.exception("Error in run_agent")
            agent_message.text = f"Error: {e!s}"
            agent_message.properties.state = "complete"
            agent_message.error = True
            agent_message = await self.send_message(message=agent_message)
            raise

        self.status = agent_message
        return agent_message

    def _add_media_from_text(self, agent_message: Message, text: str) -> str:
        """Extract image URLs/data-URIs from text and add MediaContent blocks.

        This allows charts returned as plain URIs to appear as images in the
        chat UI rather than raw text.  The original text is returned with the
        URLs stripped to avoid duplication.
        """
        import re

        from lfx.schema.content_types import MediaContent

        # regex matches data:image/... or http(s) URL ending in image extension
        pattern = re.compile(r"(data:image/[^\s]+|https?://\S+?\.(?:png|jpg|jpeg|gif))")
        matches = pattern.findall(text)
        for url in matches:
            agent_message.content_blocks[0].contents.append(MediaContent(urls=[url], caption=None))
            # remove url from text
            text = text.replace(url, "").strip()
        return text

    @staticmethod
    def _normalize_node_name(node_name: Any) -> str:
        """Normalize node names for UI display by stripping OpenDsStar prefixes."""
        if not node_name:
            return ""
        node_name_str = str(node_name).strip()
        # Remove repeated/variant prefix patterns like "NODE N", "node n" and "NODE N NODE N".
        normalized = re.sub(r"(?i)^(?:NODE\s*N\s*)+", "", node_name_str).strip()

        # Also remove a standalone leading "N" that may remain, e.g. "N PLAN ONE".
        normalized = re.sub(r"(?i)^N[\s:-]+", "", normalized).strip()

        # Debug assistance: ensure this method is hit and normalization is applied.
        logging.getLogger(__name__).debug(
            "normalize_node_name: raw=%r normalized=%r",
            node_name_str,
            normalized,
        )

        return normalized

    def validate_tool_names(self) -> None:
        """Override parent's validate_tool_names to provide better error messages for OpenDsStar Agent."""
        pattern = re.compile(r"^[a-zA-Z0-9_-]+$")

        # Clean up tools list - remove empty strings or None which Langflow sometimes passes
        if hasattr(self, "tools"):
            if isinstance(self.tools, list):
                self.tools = [t for t in self.tools if t and not (isinstance(t, str) and not t.strip())]
            elif isinstance(self.tools, str) and not self.tools.strip():
                self.tools = []

        if hasattr(self, "tools") and self.tools:
            for idx, tool in enumerate(self.tools):
                # Check if tool is a string instead of Tool object
                if isinstance(tool, str):
                    error_msg = (
                        f"Tool at index {idx} is a string '{tool}', not a Tool object.\n"
                        "OpenDsStar Agent requires actual Tool components, not text strings.\n"
                        "Please connect Tool components (e.g., Calculator, Wikipedia, etc.) to the Tools input.\n"
                        f"All tools received: {self.tools}"
                    )
                    raise TypeError(error_msg)

                # Check if tool has name attribute
                if not hasattr(tool, "name"):
                    error_msg = (
                        f"Tool at index {idx} (type: {type(tool).__name__}) doesn't have a 'name' attribute.\n"
                        f"Tool object: {tool}\n"
                        "This suggests an invalid tool connection. Please use valid LangChain Tool components."
                    )
                    raise AttributeError(error_msg)

                # Validate tool name pattern
                if not pattern.match(tool.name):
                    msg = (
                        f"Invalid tool name '{tool.name}': must only contain letters, numbers, underscores, dashes,"
                        " and cannot contain spaces."
                    )
                    raise ValueError(msg)

    def create_agent_runnable(self) -> Runnable:
        """Create the OpenDsStar agent runnable.

        This method:
        1. Imports the OpenDsStarAgent class (from installed package)
        2. Uses the LLM provided via HandleInput
        3. Creates and configures the agent
        4. Wraps it in a Runnable interface

        Returns:
            OpenDsStarAgentRunnable: A runnable wrapper around the agent

        Raises:
            ImportError: If OpenDsStarAgent cannot be imported
            ValueError: If no language model is connected
        """
        try:
            from OpenDsStar.agents.ds_star.open_ds_star_agent import OpenDsStarAgent
        except ImportError as e:
            error_msg = (
                f"Cannot import OpenDsStarAgent. Please ensure OpenDsStar is properly installed.\n"
                f"Run: uv pip install OpenDsStar\n"
                f"Error: {e}"
            )
            raise ImportError(error_msg) from e

        # Validate that LLM is connected
        if not hasattr(self, "llm") or not self.llm:
            msg = "No language model connected. Please connect a Language Model component to the LLM input."
            raise ValueError(msg)

        # Using getattr might not work if tools haven't been set yet
        tools = None
        if hasattr(self, "_inputs") and "tools" in self._inputs:
            tools = self._inputs["tools"].value

        # Fallback to attribute access if _inputs not available
        if tools is None:
            tools = getattr(self, "tools", None)

        # Ensure tools is a list (not None)
        if tools is None:
            tools = []
        elif not isinstance(tools, list):
            # If a single tool was provided, wrap it in a list
            tools = [tools]

        logger = logging.getLogger(__name__)
        logger.debug("OPEN_DS_STAR_AGENT: RAW TOOLS RECEIVED = %r", tools)

        # Clean up empty strings or None which Langflow sometimes passes when the input is functionally empty
        tools = [t for t in tools if t and not (isinstance(t, str) and not t.strip())]

        logger.debug("OPEN_DS_STAR_AGENT: CLEANED TOOLS = %r", tools)
        logger.info("OpenDsStarAgent - Creating agent with %d tools", len(tools))
        logger.info("OpenDsStarAgent - Tools type: %s", type(tools))

        if not tools:
            logger.warning("=" * 80)
            logger.warning("WARNING: NO TOOLS PROVIDED TO DS STAR AGENT!")
            logger.warning("The agent will NOT be able to use external tools.")
            logger.warning("To use tools:")
            logger.warning("1. Add tool components (e.g., Calculator, Wikipedia) to your flow")
            logger.warning("2. Connect them to the 'Tools' input of this agent")
            logger.warning("=" * 80)
        else:
            logger.info("Tools received by OpenDsStarAgent:")
            for idx, tool in enumerate(tools):
                tool_name = getattr(tool, "name", "UNKNOWN")
                tool_desc = getattr(tool, "description", "No description")
                logger.info("  %d. %s: %s", idx + 1, tool_name, tool_desc[:100])

        # Validate tools format - must be Tool objects with .name and other attributes
        if tools:
            for idx, tool in enumerate(tools):
                if isinstance(tool, str):
                    error_msg = (
                        f"Tool at index {idx} is a string '{tool}', not a Tool object.\n"
                        "This usually means tools weren't properly connected in the flow.\n"
                        "Please ensure Tool components (not text/strings) are connected to the Tools input.\n"
                        f"All tools received: {tools}"
                    )
                    raise TypeError(error_msg)
                if not hasattr(tool, "name"):
                    error_msg = (
                        f"Tool at index {idx} (type: {type(tool).__name__}) is missing the 'name' attribute.\n"
                        f"Tool object: {tool}\n"
                        "Please ensure you're connecting valid LangChain Tool components."
                    )
                    raise TypeError(error_msg)

        # Get optional parameters with defaults
        max_iterations = getattr(self, "max_iterations", 10)
        system_prompt = getattr(self, "system_prompt", None)
        code_mode = getattr(self, "code_mode", "stepwise")
        code_timeout = getattr(self, "code_timeout", 60)

        logger.info(
            "OpenDsStarAgent - Creating agent with model=%s, max_steps=%s, code_mode=%s, system_prompt length=%d",
            self.llm,
            max_iterations,
            code_mode,
            len(system_prompt) if system_prompt else 0,
        )

        # Create the agent with all configured parameters
        agent = OpenDsStarAgent(
            model=self.llm,
            temperature=0.0,  # Fixed for now, could be made configurable
            tools=tools,
            system_prompt=system_prompt if system_prompt else "You are a helpful data science assistant.",
            max_steps=max_iterations,
            code_mode=code_mode,
            code_timeout=code_timeout,
        )

        logger.info("OpenDsStarAgent - Agent created successfully with %d tools", len(agent.tools))

        if not agent.tools:
            logger.warning(
                "Agent has NO tools after creation. It will only be able to solve"
                " problems using built-in Python libraries."
            )

        # Wrap in runnable interface for LangChain compatibility
        return OpenDsStarAgentRunnable(agent)
