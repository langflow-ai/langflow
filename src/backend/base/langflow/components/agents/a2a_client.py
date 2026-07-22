import httpx

from langflow.custom import Component
from langflow.inputs import MessageInput, StrInput
from langflow.schema import Message
from langflow.template import Output


class A2AClientConnector(Component):
    display_name = "A2A Agent Connector"
    description = "Connects to a remote A2A-compliant agent."
    icon = "network"

    inputs = [
        StrInput(
            name="agent_card_url", display_name="Agent Card URL", value="https://example.com/.well-known/agent.json"
        ),
        MessageInput(name="message", display_name="Message"),
    ]

    outputs = [
        Output(name="response", display_name="Response", method="build"),
    ]

    async def build(self) -> Message:
        async with httpx.AsyncClient() as client:
            card_res = await client.get(self.agent_card_url)
            card_res.raise_for_status()
            agent_card = card_res.json()

            rpc_url = agent_card.get("rpc_url")
            if not rpc_url:
                raise ValueError("Agent card does not contain an rpc_url.")

            payload = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": self.message.text}]}},
                "id": 1,
            }
            rpc_res = await client.post(rpc_url, json=payload)
            rpc_res.raise_for_status()
            
            result = rpc_res.json().get("result", {})
            msg_data = result.get("message", {})
            parts = msg_data.get("parts", [])
            text = " ".join(p.get("text", "") for p in parts if p.get("kind") == "text")
            
            return Message(text=text or "No response text")
