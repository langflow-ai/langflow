from smolagents import CodeAgent, ManagedAgent, ToolCallingAgent

from langflow.base.huggingface.model_bridge import LangChainHFModel
from langflow.custom import Component
from langflow.field_typing import (
    LanguageModel,  # noqa: F401
    Tool,  # noqa: F401
)
from langflow.io import BoolInput, HandleInput, MessageTextInput, Output


class SmolAgentManagerComponent(Component):
    """A component for creating managed SMOL agents."""

    display_name: str = "SMOL Agent Manager"
    description: str = "Create a managed SMOL agent that can use tools to accomplish tasks"
    icon = "HuggingFace"
    beta = True

    inputs = [
        # ManagedAgent parameters
        HandleInput(
            name="smol_agent",
            display_name="SMOL Agent",
            input_types=["ToolCallingAgent", "CodeAgent"],
            required=True,
            info="The SMOL agent to manage",
        ),
        MessageTextInput(
            name="agent_name",
            display_name="Agent Name",
            info="The name of the managed agent",
            required=True,
        ),
        MessageTextInput(
            name="agent_description",
            display_name="Agent Description",
            info="A description of what the managed agent does",
            required=True,
        ),
        MessageTextInput(
            name="additional_prompting",
            display_name="Additional Prompting",
            info="Additional prompting for the managed agent",
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="provide_run_summary",
            display_name="Provide Run Summary",
            info="Whether to provide a run summary after the agent completes its task",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [Output(name="agent", display_name="Managed Agent", method="build_agent")]

    def build_agent(self) -> ManagedAgent:
        # Convert LangChain model to HuggingFace model interface
        hf_model = LangChainHFModel(chat_model=self.language_model)
        try:
            from smolagents import Tool as SmolTool
        except ImportError as e:
            msg = "smolagents is not installed. Please install it using `pip install smolagents`."
            raise ImportError(msg) from e

        # Convert LangChain tools to HuggingFace tools
        hf_tools = [SmolTool.from_langchain(_tool) for _tool in self.tools]

        # Create base tool calling agent
        base_agent = ToolCallingAgent(
            model=hf_model,
            tools=hf_tools,
            system_prompt=self.system_message if self.system_message else None,
        )

        # Create managed agent
        managed_agent_kwargs = {
            "agent": base_agent,
            "name": self.agent_name,
            "description": self.agent_description,
            "additional_prompting": self.additional_prompting if hasattr(self, "additional_prompting") else None,
            "provide_run_summary": self.provide_run_summary if hasattr(self, "provide_run_summary") else False,
        }

        return ManagedAgent(**{k: v for k, v in managed_agent_kwargs.items() if v is not None})
