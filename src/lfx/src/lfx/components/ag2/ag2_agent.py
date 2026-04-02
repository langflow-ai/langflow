"""AG2 Agent component for Langflow."""

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, HandleInput, MultilineInput, Output


class AG2AgentComponent(Component):
    display_name = "AG2 Agent"
    description = "Create an AG2 agent with a configurable role and behavior."
    icon = "AG2"
    name = "AG2Agent"

    inputs = [
        MultilineInput(
            name="agent_name",
            display_name="Agent Name",
            info="Unique name for this agent (e.g., 'Researcher', 'Writer').",
            value="Assistant",
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="Instructions that define the agent's role and behavior.",
            value="You are a helpful AI assistant.",
        ),
        HandleInput(
            name="llm_config",
            display_name="LLM Config",
            input_types=["Data"],
            info="AG2 LLM configuration from the AG2 LLM Config component.",
        ),
        BoolInput(
            name="is_terminator",
            display_name="Can Terminate",
            info="If true, this agent's TERMINATE keyword ends the conversation.",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Agent", name="agent", method="build_agent", types=["Data"]),
    ]

    def build_agent(self):
        try:
            from autogen import AssistantAgent
        except ImportError as e:
            msg = 'AG2 is not installed. Run: pip install "ag2[openai]>=0.11.4,<1.0"'
            raise ImportError(msg) from e

        agent = AssistantAgent(
            name=self.agent_name,
            system_message=self.system_message,
            llm_config=self.llm_config,
        )

        self.status = f"Agent: {self.agent_name}"
        return agent
