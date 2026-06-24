from langflow.custom import Component
from langflow.inputs import StrInput
from langflow.schema import Message


class A2AServerAgent(Component):
    display_name = "A2A Server Agent"
    description = "Exposes this Langflow instance as an A2A-compliant server."

    inputs = [
        StrInput(name="agent_name", display_name="Agent Name", value="Langflow A2A Agent"),
    ]

    def build_config(self):
        return {"agent_name": {"display_name": "Agent Name"}}

    async def build(self) -> Message:
        return Message(text=f"Server initialized: {self.agent_name}")
