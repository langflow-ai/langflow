from typing import Dict, List, Optional

from langchain.utilities import requests, sql_database

from langflow.interface.base import LangChainTypeCreator
from loguru import logger
from langflow.utils.util import build_template_from_class, build_template_from_method


class WrapperCreator(LangChainTypeCreator):
    type_name: str = "wrappers"

    from_method_nodes = {"SQLDatabase": "from_uri"}

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = {
                wrapper.__name__: wrapper
                for wrapper in [requests.TextRequestsWrapper, sql_database.SQLDatabase]
            }
        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        try:
            if name in self.from_method_nodes:
                return build_template_from_method(
                    name,
                    type_to_cls_dict=self.type_to_loader_dict,
                    add_function=True,
                    method_name=self.from_method_nodes[name],
                )

            return build_template_from_class(name, self.type_to_loader_dict)
        except ValueError as exc:
            raise ValueError("Wrapper not found") from exc
        except AttributeError as exc:
            logger.error(f"Wrapper {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return list(self.type_to_loader_dict.keys())


wrapper_creator = WrapperCreator()
