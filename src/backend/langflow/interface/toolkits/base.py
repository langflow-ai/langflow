from langflow.interface.base import LangChainTypeCreator
from langflow.utils.util import build_template_from_class
from typing import Dict, List
from langchain.agents import agent_toolkits
from langflow.interface.importing.utils import import_class


class ToolkitCreator(LangChainTypeCreator):
    type_name: str = "toolkits"

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = {
                toolkit_name: import_class(
                    f"langchain.agents.agent_toolkits.{toolkit_name}"
                )
                # if toolkit_name is not lower case it is a class
                for toolkit_name in agent_toolkits.__all__
                if not toolkit_name.islower()
            }
        return self.type_dict

    def get_signature(self, name: str) -> Dict | None:
        try:
            return build_template_from_class(name, self.type_to_loader_dict)
        except ValueError as exc:
            raise ValueError("Prompt not found") from exc

    def to_list(self) -> List[str]:
        return list(self.type_to_loader_dict.keys())


toolkits_creator = ToolkitCreator()
