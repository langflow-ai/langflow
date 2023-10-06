from typing import Dict, List, Optional

from langchain.agents import types

from langflow.custom.customs import get_custom_nodes
from langflow.interface.agents.custom import CUSTOM_AGENTS
from langflow.interface.base import LangChainTypeCreator
from langflow.services.getters import get_settings_service

from langflow.template.frontend_node.agents import AgentFrontendNode
from loguru import logger
from langflow.utils.util import build_template_from_class, build_template_from_method


class AgentCreator(LangChainTypeCreator):
    type_name: str = "agents"

    from_method_nodes = {"ZeroShotAgent": "from_llm_and_tools"}

    @property
    def frontend_node_class(self) -> type[AgentFrontendNode]:
        return AgentFrontendNode

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
            elif name in self.from_method_nodes:
                return build_template_from_method(
                    name,
                    type_to_cls_dict=self.type_to_loader_dict,
                    add_function=True,
                    method_name=self.from_method_nodes[name],
                )
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
        settings_service = get_settings_service()
        for _, agent in self.type_to_loader_dict.items():
            agent_name = (
                agent.function_name()
                if hasattr(agent, "function_name")
                else agent.__name__
            )
            if (
                agent_name in settings_service.settings.AGENTS
                or settings_service.settings.DEV
            ):
                names.append(agent_name)
        return names


agent_creator = AgentCreator()
