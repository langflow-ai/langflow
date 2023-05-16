from typing import Dict, List, Optional, Type

from langchain import llms, chat_models
from langflow.interface.base import LangChainTypeCreator
from langflow.settings import settings
from langflow.template.nodes import LLMFrontendNode
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_class
from langflow.interface.importing.utils import import_class


class LLMCreator(LangChainTypeCreator):
    type_name: str = "llms"

    @property
    def frontend_node_class(self) -> Type[LLMFrontendNode]:
        return LLMFrontendNode

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            llms_dict = {
                name: import_class(f"langchain.llms.{name}")
                # if prompt_name is not lower case it is a class
                for name in llms.__all__
            }
            chat_models_dict = {
                name: import_class(f"langchain.chat_models.{name}")
                # if prompt_name is not lower case it is a class
                for name in chat_models.__all__
            }

            self.type_dict = {**llms_dict, **chat_models_dict}

        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of an llm."""
        try:
            return build_template_from_class(name, self.type_to_loader_dict)
        except ValueError as exc:
            raise ValueError("LLM not found") from exc

        except AttributeError as exc:
            logger.error(f"LLM {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return [
            llm.__name__
            for llm in self.type_to_loader_dict.values()
            if llm.__name__ in settings.llms or settings.dev
        ]


llm_creator = LLMCreator()
