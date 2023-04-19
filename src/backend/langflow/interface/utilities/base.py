from typing import Dict, List, Optional

from langflow.custom.customs import get_custom_nodes
from langflow.interface.base import LangChainTypeCreator
from langflow.interface.custom_lists import utility_type_to_cls_dict
from langflow.settings import settings
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_class


class UtilityCreator(LangChainTypeCreator):
    type_name: str = "utilities"

    @property
    def type_to_loader_dict(self) -> Dict:
        return utility_type_to_cls_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of a utility."""
        try:
            if name in get_custom_nodes(self.type_name).keys():
                return get_custom_nodes(self.type_name)[name]
            return build_template_from_class(name, utility_type_to_cls_dict)
        except ValueError as exc:
            raise ValueError(f"Utility {name} not found") from exc

        except AttributeError as exc:
            logger.error(f"Utility {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return [
            utility.__name__
            for utility in self.type_to_loader_dict.values()
            if utility.__name__ in settings.utilities or settings.dev
        ]


utility_creator = UtilityCreator()
