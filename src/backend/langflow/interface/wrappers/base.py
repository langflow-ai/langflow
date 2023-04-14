from typing import Dict, List, Optional

from langchain import requests

from langflow.interface.base import LangChainTypeCreator
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_class


class WrapperCreator(LangChainTypeCreator):
    type_name: str = "wrappers"

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = {
                wrapper.__name__: wrapper for wrapper in [requests.TextRequestsWrapper]
            }
        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        try:
            return build_template_from_class(name, self.type_to_loader_dict)
        except ValueError as exc:
            raise ValueError("Wrapper not found") from exc
        except AttributeError as exc:
            logger.error(f"Wrapper {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return list(self.type_to_loader_dict.keys())


wrapper_creator = WrapperCreator()
