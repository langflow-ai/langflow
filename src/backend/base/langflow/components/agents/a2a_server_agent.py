from langflow.custom import Component
from langflow.inputs import StrInput
from langflow.schema import Message
from langflow.services.deps import get_a2a_service
from langflow.template import Output


class A2AServerAgent(Component):
    display_name = "A2A Server Agent"
    description = "Exposes this Langflow instance as an A2A-compliant server."
    icon = "bot"

    inputs = [
        StrInput(name="agent_name", display_name="Agent Name", value="Langflow A2A Agent"),
    ]

    outputs = [
        Output(name="response", display_name="Response", method="build"),
    ]

    def build_config(self):
        return {"agent_name": {"display_name": "Agent Name"}}

    async def build(self) -> Message:
        a2a_service = get_a2a_service()
        flow_id = str(self.graph.flow_id) if hasattr(self, "graph") and self.graph and self.graph.flow_id else "unknown_flow"
        component_id = getattr(self, "_id", "unknown_component")
        
        agent_card = {
            "agent_name": self.agent_name,
            "description": self.description,
            "rpc_url": f"/api/v1/a2a/{flow_id}/{component_id}/rpc"
        }
        
        a2a_service.register_agent(flow_id, component_id, agent_card)
        return Message(text=f"Server initialized: {self.agent_name}")
