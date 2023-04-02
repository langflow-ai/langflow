import contextlib
from typing import Dict, Iterable

from langchain.agents import loading

from langflow.custom.customs import get_custom_nodes
from langflow.interface.agents.custom import CUSTOM_AGENTS
from langflow.interface.base import LangChainTypeCreator
from langflow.settings import settings
from langflow.utils.util import build_template_from_class


class AgentCreator(LangChainTypeCreator):
    type_name: str = "agents"

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = loading.AGENT_TO_CLASS
            # Add JsonAgent to the list of agents
            for name, agent in CUSTOM_AGENTS.items():
                self.type_dict[name] = agent
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

    # Now this is a generator
    def to_list(self) -> Iterable:
        for name, agent in self.type_to_loader_dict.items():
            agent_name = (
                agent.function_name()
                if hasattr(agent, "function_name")
                else agent.__name__
            )
            if agent_name in settings.agents or settings.dev:
                yield agent_name


agent_creator = AgentCreator()
