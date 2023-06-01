from typing import Dict, List, Optional

from langchain.agents import types

from langflow.custom.customs import get_custom_nodes
from langflow.interface.agents.custom import CUSTOM_AGENTS
from langflow.interface.base import LangChainTypeCreator
from langflow.settings import settings
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_class


class AgentCreator(LangChainTypeCreator):
    type_name: str = "agents"

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = types.AGENT_TO_CLASS
            # Add JsonAgent to the list of agents
            for name, agent in CUSTOM_AGENTS.items():
                # TODO: validate AgentType
                self.type_dict[name] = agent  # type: ignore
        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        try:
            if name in get_custom_nodes(self.type_name).keys():
                return get_custom_nodes(self.type_name)[name]
            return build_template_from_class(
                name, self.type_to_loader_dict, add_function=True
            )
        except ValueError as exc:
            raise ValueError("Agent not found") from exc
        except AttributeError as exc:
            logger.error(f"Agent {name} not loaded: {exc}")
            return None

    # Now this is a generator
    def to_list(self) -> List[str]:
        names = []
        for _, agent in self.type_to_loader_dict.items():
            agent_name = (
                agent.function_name()
                if hasattr(agent, "function_name")
                else agent.__name__
            )
            if agent_name in settings.agents or settings.dev:
                names.append(agent_name)
        return names


agent_creator = AgentCreator()
