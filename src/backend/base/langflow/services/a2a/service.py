from langflow.services.base import Service


class A2AService(Service):
    name = "a2a_service"

    def __init__(self):
        super().__init__()
        self.registry: dict[str, dict] = {}

    def register_agent(self, flow_id: str, component_id: str, agent_card: dict):
        self.registry[f"{flow_id}_{component_id}"] = agent_card

    def get_agent_card(self, flow_id: str, component_id: str) -> dict | None:
        return self.registry.get(f"{flow_id}_{component_id}")
