from langchain.agents import loading
from langflow.interface.base import LangChainTypeCreator
from langflow.utils.util import build_template_from_class
from langflow.settings import settings
from typing import Dict, List


class AgentCreator(LangChainTypeCreator):
    type_name: str = "agents"

    @property
    def type_to_loader_dict(self) -> Dict:
        return loading.AGENT_TO_CLASS

    def get_signature(self, name: str) -> Dict | None:
        try:
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
