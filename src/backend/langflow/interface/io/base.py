from typing import Any, Dict, List, Optional, Type

from langflow.custom.customs import get_custom_nodes
from langflow.interface.base import LangChainTypeCreator
from langflow.components.component.io import IoComponent
from langflow.utils.logger import logger
from langflow.interface.io import custom

# Assuming necessary imports for Field, Template, and Component classes


class IoCreator(LangChainTypeCreator):
    type_name: str = "io"

    @property
    def component_class(self) -> Type[IoComponent]:
        return IoComponent

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict: dict[str, Any] = {"Chat": custom.Chat, "Form": custom.Form}
        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        try:
            if name in get_custom_nodes(self.type_name).keys():
                return get_custom_nodes(self.type_name)[name]
        except ValueError as exc:
            raise ValueError(f"I/O {name} not found: {exc}") from exc
        except AttributeError as exc:
            logger.error(f"I/O {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return list(self.type_to_loader_dict.keys())


io_creator = IoCreator()
