from smolagents import CodeAgent, ToolCallingAgent

from langflow.base.huggingface.model_bridge import LangChainHFModel
from langflow.custom import Component
from langflow.field_typing import (
    LanguageModel,  # noqa: F401
    Tool,  # noqa: F401
)
from langflow.inputs.inputs import InputTypes
from langflow.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, Output
from langflow.schema.message import Message


class SmolAgentComponent(Component):
    """A component for creating SMOL agents with different types and configurations."""

    display_name: str = "SMOL Agent"
    description: str = "Create a SMOL agent that can use tools to accomplish tasks"
    icon = "HuggingFace"
    beta = True

    inputs: list[InputTypes] = [
        HandleInput(
            name="language_model",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
            info="The language model to use for the agent",
        ),
        HandleInput(
            name="smol_agent",
            display_name="SMOL Agent",
            input_types=["ManagedAgent"],
            info="The SMOL agent to manage",
            is_list=True,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=True,
            info="The tools the agent can use",
        ),
        MessageTextInput(
            name="system_message",
            display_name="System Message",
            required=False,
            info="Optional system message to guide the agent's behavior",
            advanced=True,
        ),
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="The input provided by the user for the agent to process.",
            tool_mode=True,
        ),
        DropdownInput(
            name="agent_type",
            display_name="Agent Type",
            options=["Code Agent", "Tool Calling Agent"],
            info="Type of SMOL agent to create",
            value="Code Agent",
        ),
        MessageTextInput(
            name="grammar",
            display_name="Grammar",
            info="Grammar used to parse the LLM output",
            advanced=True,
        ),
        MessageTextInput(
            name="additional_authorized_imports",
            display_name="Additional Imports",
            info="Additional authorized imports for the agent (comma-separated)",
            advanced=True,
        ),
        IntInput(
            name="planning_interval",
            display_name="Planning Interval",
            info="Interval at which the agent will run a planning step",
            advanced=True,
        ),
        BoolInput(
            name="use_e2b_executor",
            display_name="Use E2B Executor",
            info="Whether to use the E2B executor for remote code execution",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="max_print_outputs_length",
            display_name="Max Print Length",
            info="Maximum length of the print outputs",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="response", display_name="Response", method="run_agent"),
        Output(
            name="agent",
            display_name="SMOL Agent",
            method="build_agent",
            output_types=["CodeAgent", "ToolCallingAgent"],
        ),
    ]

    def build_agent(self) -> CodeAgent | ToolCallingAgent:
        # Convert LangChain model to HuggingFace model interface
        hf_model = LangChainHFModel(chat_model=self.language_model)
        try:
            from smolagents import Tool as SmolTool
        except ImportError as e:
            msg = "smolagents is not installed. Please install it using `pip install smolagents`."
            raise ImportError(msg) from e

        # Convert LangChain tools to HuggingFace tools
        hf_tools = [SmolTool.from_langchain(_tool) for _tool in self.tools] if self.tools else []
        # Process additional imports if provided
        additional_imports = None
        if hasattr(self, "additional_authorized_imports") and self.additional_authorized_imports:
            additional_imports = [imp.strip() for imp in self.additional_authorized_imports.split(",")]

        # Create agent based on type
        if self.agent_type == "Code Agent":
            agent_kwargs = {
                "model": hf_model,
                "tools": hf_tools,
                "system_prompt": self.system_message if self.system_message else None,
                "grammar": self.grammar if self.grammar else None,
                "additional_authorized_imports": additional_imports,
                "planning_interval": self.planning_interval if self.planning_interval else None,
                "use_e2b_executor": self.use_e2b_executor if self.use_e2b_executor else False,
                "max_print_outputs_length": self.max_print_outputs_length if self.max_print_outputs_length else None,
                "managed_agent": [self.smol_agent]
                if self.smol_agent and not isinstance(self.smol_agent, list)
                else self.smol_agent,
            }
            self.agent = CodeAgent(**{k: v for k, v in agent_kwargs.items() if v is not None})
        else:  # tool calling agent
            agent_kwargs = {
                "model": hf_model,
                "tools": hf_tools,
                "system_prompt": self.system_message if self.system_message else None,
                "planning_interval": self.planning_interval if self.planning_interval else None,
            }
            self.agent = ToolCallingAgent(**{k: v for k, v in agent_kwargs.items() if v is not None})

        return self.agent

    def run_agent(self) -> Message:
        """Run the agent and return its response as a Message."""
        agent = self.build_agent()
        response = agent.run(self.input_value)

        # Convert response to string if it's not already
        if not isinstance(response, str):
            response = str(response)

        # Create a Message with proper content blocks
        return Message(text=response)
