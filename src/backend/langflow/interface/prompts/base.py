from typing import Dict, List

from langchain.prompts import loading
from langchain import prompts
from langflow.custom.customs import get_custom_nodes
from langflow.interface.base import LangChainTypeCreator
from langflow.interface.importing.utils import import_class
from langflow.settings import settings
from langflow.template.nodes import PromptFrontendNode
from langflow.utils.util import build_template_from_class


class PromptCreator(LangChainTypeCreator):
    type_name: str = "prompts"

    @property
    def frontend_node_class(self) -> str:
        return PromptFrontendNode

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = {
                prompt_name: import_class(f"langchain.prompts.{prompt_name}")
                # if prompt_name is not lower case it is a class
                for prompt_name in prompts.__all__
                if not prompt_name.islower() and prompt_name in settings.prompts
            }
        return self.type_dict

    def get_signature(self, name: str) -> Dict | None:
        try:
            if name in get_custom_nodes(self.type_name).keys():
                return get_custom_nodes(self.type_name)[name]
            return build_template_from_class(name, self.type_to_loader_dict)
        except ValueError as exc:
            raise ValueError("Prompt not found") from exc

    def to_list(self) -> List[str]:
        custom_prompts = get_custom_nodes("prompts")
        # library_prompts = [
        #     prompt.__annotations__["return"].__name__
        #     for prompt in self.type_to_loader_dict.values()
        #     if prompt.__annotations__["return"].__name__ in settings.prompts
        #     or settings.dev
        # ]
        return list(self.type_to_loader_dict.keys()) + list(custom_prompts.keys())


prompt_creator = PromptCreator()
