from langflow.custom import Component
from langflow.inputs import StrInput, MessageInput
from langflow.schema import Message

class A2AClientConnector(Component):
    display_name = "A2A Agent Connector"
    description = "Connects to a remote A2A-compliant agent."

    inputs = [
        StrInput(
            name="agent_card_url",
            display_name="Agent Card URL",
            value="https://example.com/.well-known/agent.json"
        ),
        MessageInput(name="message", display_name="Message"),
    ]

    async def build(self) -> Message:
        # Mock logic
        return Message(text=f"A2A response from {self.agent_card_url}: {self.message.text}")
