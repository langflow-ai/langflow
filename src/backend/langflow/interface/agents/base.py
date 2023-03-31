from langchain.agents import loading
from langflow.custom.customs import get_custom_nodes
from langflow.interface.base import LangChainTypeCreator
from langflow.utils.util import build_template_from_class
from langflow.settings import settings
from typing import Dict, List
from langflow.interface.agents.custom import JsonAgent


class AgentCreator(LangChainTypeCreator):
    type_name: str = "agents"

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = loading.AGENT_TO_CLASS
            # Add JsonAgent to the list of agents
            self.type_dict["JsonAgent"] = JsonAgent
        return self.type_dict

    def get_signature(self, name: str) -> Dict | None:
        try:
            if name in get_custom_nodes(self.type_name).keys():
                return get_custom_nodes(self.type_name)[name]
            return build_template_from_class(
                name, self.type_to_loader_dict, add_function=True
            )
        except ValueError as exc:
            raise ValueError("Agent not found") from exc

    def to_list(self) -> List[str]:
        return [
            agent.__name__
            for agent in self.type_to_loader_dict.values()
            if agent.__name__ in settings.agents or settings.dev
        ]


agent_creator = AgentCreator()
