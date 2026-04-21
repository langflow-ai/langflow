import logging
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any, ClassVar

from langchain_core.runnables import Runnable, RunnableConfig

from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.inputs.inputs import BoolInput, DataInput, DropdownInput, MessageTextInput, MultilineInput
from lfx.io import HandleInput, IntInput
from lfx.schema.message import Message
from lfx.template.field.base import RangeSpec

logger = logging.getLogger(__name__)

_MAX_LOG_DISPLAY_LENGTH = 500


class CodeActAgentSmolagentsRunnable(Runnable):
    """Runnable wrapper for CodeActAgentSmolagents.

    This wrapper makes CodeActAgentSmolagents compatible with LangChain's Runnable interface,
    allowing it to be used in AgentExecutor and other LangChain workflows.
    """

    def __init__(self, agent):
        """Initialize the runnable wrapper.

        Args:
            agent: An instance of CodeActAgentSmolagents
        """
        super().__init__()
        self.agent = agent
        self.start_time = None

    def invoke(self, input_value: dict[str, Any] | str, config: RunnableConfig | None = None) -> dict[str, Any]:
        """Invoke the CodeActAgentSmolagents synchronously.

        Args:
            input_value: Either a dict with "input" key or a string query
            config: Optional LangChain runnable configuration

        Returns:
            Dict with "output" key containing the agent's answer
        """
        # Extract the input message
        if isinstance(input_value, dict) and "input" in input_value:
            query = input_value["input"]
        elif isinstance(input_value, str):
            query = input_value
        else:
            query = str(input_value)

        # Invoke the agent (config is passed through if provided)
        result = self.agent.invoke(query, config=config)

        # Return in the expected format for LangChain
        # The agent returns a dict with 'answer', 'trajectory', etc.
        # We return only the final answer in the output, trajectory goes to content blocks
        output_text = result.get("answer", "")

        return {"output": output_text, "_result": result}

    async def ainvoke(
        self,
        input_value: dict[str, Any] | str,
        config: RunnableConfig | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """Async invoke - currently just calls sync version.

        Note: CodeActAgentSmolagents doesn't have native async support yet,
        so this is a synchronous implementation wrapped as async.
        """
        return self.invoke(input_value, config)

    def stream(
        self,
        input_value: dict[str, Any] | str,
        config: RunnableConfig | None = None,
        **_kwargs: Any,
    ) -> Iterator[dict[str, Any]]:
        """Stream the agent output step-by-step.

        Uses CodeActAgentSmolagents' stream_invoke to yield intermediate steps.
        """
        # Extract the input message
        if isinstance(input_value, dict) and "input" in input_value:
            query = input_value["input"]
        elif isinstance(input_value, str):
            query = input_value
        else:
            query = str(input_value)

        # Stream from the agent
        yield from self.agent.stream_invoke(query, config=config)

    async def astream(
        self,
        input_value: dict[str, Any] | str,
        config: RunnableConfig | None = None,
        **_kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async stream the agent output step-by-step.

        Currently wraps the sync stream in async context.
        """
        # Extract the input message
        if isinstance(input_value, dict) and "input" in input_value:
            query = input_value["input"]
        elif isinstance(input_value, str):
            query = input_value
        else:
            query = str(input_value)

        # Stream from the agent (wrapped in async)
        import asyncio

        for event in self.agent.stream_invoke(query, config=config):
            yield event
            # Allow other async tasks to run
            await asyncio.sleep(0)


class CodeActAgentSmolagentsComponent(ToolCallingAgentComponent):
    code_class_base_inheritance: ClassVar[str] = "Component"
    display_name: str = "CodeAct Agent (Smolagents)"
    description: str = "A code-based agent using smolagents CodeAgent for complex tasks."
    documentation: str = "https://github.com/IBM/OpenDsStar"
    icon = "bot"
    beta = True
    name = "CodeActAgentSmolagents"

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
            info="Language model to use for the CodeAct agent",
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
            value=5,
            advanced=True,
            range_spec=RangeSpec(min=1, max=50, step=1),
        ),
        MessageTextInput(
            name="system_prompt",
            display_name="System Message",
            info="System message to customize agent behavior",
            advanced=True,
        ),
        IntInput(
            name="code_timeout",
            display_name="Code Timeout (seconds)",
            value=30,
            advanced=True,
            range_spec=RangeSpec(min=5, max=300, step=5),
            info="Maximum time in seconds for each code execution step. If code takes longer, it will be terminated.",
        ),
        DropdownInput(
            name="show_code_steps",
            display_name="Show Code Steps",
            options=["All Steps", "Final Code Only", "None"],
            value="All Steps",
            info=(
                "Display coding steps: 'All Steps' shows each code generation and execution,"
                " 'Final Code Only' shows only the last successful code, 'None' hides all code steps"
            ),
        ),
        BoolInput(
            name="handle_parsing_errors",
            display_name="Handle Parse Errors",
            value=True,
            advanced=True,
            info="Should the Agent fix errors when reading user input for better processing?",
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_time = None

    async def message_response(self) -> Message:
        """Run the agent and return the response.

        Override parent to ensure tools are properly loaded before building the agent.
        This is critical because tools need to be available when build_agent() is called.
        """
        # Ensure tools are initialized (convert None to empty list)
        if not hasattr(self, "tools") or self.tools is None:
            self.tools = []

        # Set shared callbacks for tracing the tools used by the agent
        if self.tools:
            self.set_tools_callbacks(self.tools, self._get_shared_callbacks())

        # Call build_agent() which returns the agent runnable
        agent = self.build_agent()

        # Run the agent and return the message
        message = await self.run_agent(agent=agent)

        self.status = message
        return message

    def build_agent(self) -> Runnable:  # type: ignore[override]
        """Build the CodeActAgentSmolagents.

        Override parent's build_agent to return the CodeActAgentSmolagents runnable directly.
        We return a Runnable (not AgentExecutor) because CodeActAgentSmolagents has its own
        execution logic via smolagents and doesn't need AgentExecutor's wrapping.

        The parent's run_agent() method can handle a Runnable directly.

        Returns:
            Runnable: The CodeActAgentSmolagentsRunnable
        """
        # Validate tool names first
        self.validate_tool_names()

        # Create and return the CodeActAgentSmolagents runnable directly
        return self.create_agent_runnable()

    async def run_agent(self, agent: Runnable) -> Message:
        """Override parent's run_agent to stream trajectory updates directly.

        Similar to OpenDsStarAgent, we stream code generation and execution steps
        as they happen, providing real-time feedback to the user.
        """
        import asyncio
        import uuid

        from lfx.base.agents.utils import get_chat_output_sender_name
        from lfx.schema.content_block import ContentBlock
        from lfx.schema.content_types import CodeContent, TextContent
        from lfx.schema.message import Message
        from lfx.utils.constants import MESSAGE_SENDER_AI

        logger.info("=" * 80)
        logger.info("run_agent called for CodeActAgentSmolagents with streaming")
        logger.info("=" * 80)

        # Get input value
        if isinstance(self.input_value, Message):
            lc_message = self.input_value.to_lc_message()
            if hasattr(lc_message, "content"):
                input_text = lc_message.content if isinstance(lc_message.content, str) else str(lc_message.content)
            else:
                input_text = str(lc_message)
        else:
            input_text = str(self.input_value)

        if not input_text:
            msg = "Input text is empty"
            raise ValueError(msg)

        logger.info("Input text: %s...", input_text[:100])

        # Create initial message
        sender_name = get_chat_output_sender_name(self) or self.display_name or "AI"
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = uuid.uuid4()

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

        # Get show_code_steps setting
        show_code_steps = getattr(self, "show_code_steps", "All Steps")

        # Track code contents for "Final Code Only" mode as plain code strings
        code_contents = []
        final_answer = ""

        try:
            logger.info("Starting streaming from CodeActAgentSmolagents")

            # Record start time and last-event time for per-step delta duration
            self.start_time = time.time()
            last_event_time = self.start_time

            # Get the actual agent from the runnable wrapper
            actual_agent = agent.agent if hasattr(agent, "agent") else agent

            # Create the stream generator
            stream_gen = actual_agent.stream_invoke(input_text)

            # Process events using asyncio.to_thread to avoid blocking
            # This is critical for real-time updates in Langflow
            while True:
                try:
                    # Get next event in a non-blocking way
                    event_data = await asyncio.to_thread(next, stream_gen, StopIteration)
                    if event_data is StopIteration:
                        break
                except StopIteration:
                    break

                event = event_data.get("event", {})
                node_name_raw = event.get("node_name") or event.get("node") or event.get("event_type") or ""
                node_name = self._normalize_node_name(node_name_raw)
                step_idx = event.get("step_idx")

                # Calculate per-event delta so that the UI sum equals total elapsed time
                # (not cumulative from start, which would inflate the total when summed)
                current_event_time = time.time()
                dur = round((current_event_time - last_event_time) * 1000)
                last_event_time = current_event_time

                # Build a node summary block, always present
                from lfx.schema.content_types import ToolContent

                summary_output = []
                if node_name:
                    summary_output.append(f"Node: {node_name}")
                if step_idx is not None:
                    summary_output.append(f"Step: {step_idx}")

                if event.get("code"):
                    code_label = "Code generated" if node_name.lower().startswith("code_generation") else "Code present"
                    summary_output.append(code_label)
                if event.get("logs"):
                    summary_output.append("Execution logs")
                if event.get("error"):
                    summary_output.append("Error encountered")

                agent_message.content_blocks[0].contents.append(
                    ToolContent(
                        type="tool_use",
                        name=node_name or "CodeAct Step",
                        tool_input={
                            "step_idx": step_idx,
                            "node_name": node_name,
                            **({"code": str(event.get("code", "")).strip()} if event.get("code") else {}),
                            **({"logs": str(event.get("logs", "")).strip()} if event.get("logs") else {}),
                            **({"error": str(event.get("error", "")).strip()} if event.get("error") else {}),
                        },
                        output="; ".join(summary_output) or "Step event",
                        error=str(event.get("error", "")) if event.get("error") else None,
                        header={"title": f"Executed **{node_name or 'Step'}**", "icon": "GitBranch"},
                        duration=dur,
                    )
                )

                # Append code block when requested
                if "code" in event and str(event.get("code", "")).strip():
                    code_text = str(event.get("code", "")).strip()
                    code_contents.append(code_text)

                    if show_code_steps in ("All Steps",):
                        code_content = CodeContent(
                            code=code_text,
                            language="python",
                            type="code",
                            header={"title": "Code", "icon": "Code"},
                            duration=dur,
                        )
                        agent_message.content_blocks[0].contents.append(code_content)

                # Append logs block when requested
                if "logs" in event and str(event.get("logs", "")).strip():
                    logs_text = str(event.get("logs", "")).strip()
                    display_logs = (
                        logs_text
                        if len(logs_text) <= _MAX_LOG_DISPLAY_LENGTH
                        else logs_text[:_MAX_LOG_DISPLAY_LENGTH] + "..."
                    )
                    if show_code_steps in ("All Steps",):
                        agent_message.content_blocks[0].contents.append(
                            TextContent(
                                text=display_logs,
                                type="text",
                                header={"title": "Execution Output", "icon": "Terminal"},
                                duration=dur,
                            )
                        )

                # Append error block (always show) even in Final Code only mode
                if "error" in event and str(event.get("error", "")).strip():
                    error_text = str(event.get("error", "")).strip()
                    agent_message.content_blocks[0].contents.append(
                        TextContent(
                            text=error_text,
                            type="text",
                            header={"title": "Error", "icon": "AlertTriangle"},
                            duration=dur,
                        )
                    )

                # Update final answer
                if node_name.lower() == "final_answer" and "answer" in event:
                    final_answer = str(event.get("answer", "")).strip()

                # Send partial updates for stream feedback
                await self.send_message(message=agent_message, skip_db_update=True)

            # Add final code only if that mode is selected
            if show_code_steps == "Final Code Only" and code_contents:
                last_code = code_contents[-1]
                agent_message.content_blocks[0].contents.append(
                    CodeContent(
                        code=last_code,
                        language="python",
                        type="code",
                        header={"title": "Final Code", "icon": "Code"},
                    )
                )

            # Set final answer
            agent_message.text = final_answer if final_answer else ""
            agent_message.properties.state = "complete"
            agent_message = await self.send_message(message=agent_message)

            logger.info("run_agent completed successfully")

        except Exception as e:
            error_msg = str(e)
            # Suppress timeout errors from smolagents' LocalPythonInterpreter only when
            # the agent already produced a valid answer before the timeout fired.
            if "exceeded the maximum execution time" in error_msg.lower() and final_answer:
                logger.warning("Ignoring timeout error — agent already produced output")
                agent_message.text = final_answer
                agent_message.properties.state = "complete"
                agent_message = await self.send_message(message=agent_message)
            else:
                # Real error - display it
                logger.exception("Error in run_agent")
                agent_message.text = f"Error: {error_msg}"
                agent_message.properties.state = "complete"
                agent_message.error = True
                agent_message = await self.send_message(message=agent_message)
                raise

        self.status = agent_message
        return agent_message

    @staticmethod
    def _normalize_node_name(node_name: Any) -> str:
        """Normalize node names for UI display by stripping common prefixes."""
        import re

        if not node_name:
            return ""
        node_name_str = str(node_name).strip()
        normalized = node_name_str

        # Use same normalization strategy as OpenDsStar for consistency
        normalized = re.sub(r"(?i)^(?:NODE\s*N\s*)+", "", normalized).strip()
        normalized = re.sub(r"(?i)^N[\s:-]+", "", normalized).strip()

        logger.debug(
            "normalize_node_name: raw=%r normalized=%r",
            node_name_str,
            normalized,
        )
        return normalized

    def validate_tool_names(self) -> None:
        """Override parent's validate_tool_names to provide better error messages for CodeActAgentSmolagents."""
        import re

        pattern = re.compile(r"^[a-zA-Z0-9_-]+$")

        if hasattr(self, "tools") and self.tools:
            for idx, tool in enumerate(self.tools):
                # Check if tool is a string instead of Tool object
                if isinstance(tool, str):
                    error_msg = (
                        f"Tool at index {idx} is a string '{tool}', not a Tool object.\n"
                        "CodeActAgentSmolagents requires actual Tool components, not text strings.\n"
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

    @staticmethod
    def _normalize_llm_model(llm_model):
        """Normalize incoming LangFlow LLMs to a format acceptable by CodeActAgentSmolagents."""
        from langchain_core.language_models import BaseChatModel, BaseLanguageModel

        # Accept all LangFlow model forms directly.
        if llm_model is None:
            msg = "No language model connected. Please connect a Language Model component to the LLM input."
            raise ValueError(msg)

        # Preserve string IDs so OpenDsStar wrapper can accept them.
        if isinstance(llm_model, str):
            return llm_model

        # Direct LangChain model support (BaseChatModel/BaseLanguageModel).
        if isinstance(llm_model, (BaseChatModel, BaseLanguageModel)):
            return llm_model

        # smolagents built model support
        try:
            from smolagents import LiteLLMModel

            if isinstance(llm_model, LiteLLMModel):
                return llm_model
        except ImportError:
            pass

        # If a wrapper object holds an LLM instance, extract it.
        for attr in ("llm", "model", "base_model"):
            if hasattr(llm_model, attr):
                candidate = getattr(llm_model, attr)
                if candidate and candidate is not llm_model:
                    return CodeActAgentSmolagentsComponent._normalize_llm_model(candidate)

        # Fall back to pass through, they may still be valid if CodeAct understands it.
        return llm_model

    def create_agent_runnable(self) -> Runnable:
        """Create the CodeActAgentSmolagents runnable.

        This method:
        1. Imports the CodeActAgentSmolagents class (from installed package)
        2. Uses the LLM provided via HandleInput
        3. Creates and configures the agent
        4. Wraps it in a Runnable interface

        Returns:
            CodeActAgentSmolagentsRunnable: A runnable wrapper around the agent

        Raises:
            ImportError: If CodeActAgentSmolagents cannot be imported
            ValueError: If no language model is connected
        """
        try:
            from OpenDsStar.agents.codeact_smolagents.codeact_agent_smolagents import CodeActAgentSmolagents
        except ImportError as e:
            error_msg = (
                f"Cannot import CodeActAgentSmolagents. Please ensure OpenDsStar is properly installed.\n"
                f"Run: uv pip install -e /path/to/OpenDsStar\n"
                f"Error: {e}"
            )
            raise ImportError(error_msg) from e

        # Validate that LLM is connected
        if not hasattr(self, "llm") or not self.llm:
            msg = "No language model connected. Please connect a Language Model component to the LLM input."
            raise ValueError(msg)

        # Get tools - CRITICAL: Access via _inputs to get the actual value
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

        # Filter out invalid tools (empty strings, None, whitespace) that Langflow might pass
        # when no tools are connected. This prevents errors when tools input is left empty.
        if tools:
            tools = [t for t in tools if t and not (isinstance(t, str) and not t.strip())]

        # Validate remaining tools format - must be Tool objects with .name and other attributes
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
        max_iterations = getattr(self, "max_iterations", 5)
        system_prompt = getattr(self, "system_prompt", None)
        code_timeout = getattr(self, "code_timeout", 30)

        # Get the LLM model
        llm_model = self._normalize_llm_model(getattr(self, "llm", None))

        # Create the agent with all configured parameters
        # Pass the LangChain model directly - CodeActAgentSmolagents can handle it
        agent = CodeActAgentSmolagents(
            model=llm_model,
            temperature=0.0,  # Fixed for now, could be made configurable
            tools=tools,
            system_prompt=(
                system_prompt if system_prompt else "You are a helpful assistant that can execute code to solve tasks."
            ),
            max_steps=max_iterations,
            code_timeout=code_timeout,
        )

        # Wrap in runnable interface for LangChain compatibility
        return CodeActAgentSmolagentsRunnable(agent)
