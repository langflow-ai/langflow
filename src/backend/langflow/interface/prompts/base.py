from langchain.prompts import loading
from langflow.interface.base import LangChainTypeCreator
from langflow.utils.util import build_template_from_function
from langflow.settings import settings
from langflow.custom.customs import get_custom_nodes
from typing import Dict, List


class PromptCreator(LangChainTypeCreator):
    type_name: str = "prompts"

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = loading.type_to_loader_dict
        return self.type_dict

    def get_signature(self, name: str) -> Dict | None:
        try:
            if name in get_custom_nodes("prompts").keys():
                return get_custom_nodes("prompts")[name]
            return build_template_from_function(name, self.type_to_loader_dict)
        except ValueError as exc:
            raise ValueError("Prompt not found") from exc

    def to_list(self) -> List[str]:
        custom_prompts = get_custom_nodes("prompts")
        library_prompts = [
            prompt.__annotations__["return"].__name__
            for prompt in self.type_to_loader_dict.values()
            if prompt.__annotations__["return"].__name__ in settings.prompts
            or settings.dev
        ]
        return library_prompts + list(custom_prompts.keys())


prompt_creator = PromptCreator()
