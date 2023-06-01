from typing import Dict, List, Optional, Type

from langflow.custom.customs import get_custom_nodes
from langflow.interface.base import LangChainTypeCreator
from langflow.interface.custom_lists import chain_type_to_cls_dict
from langflow.settings import settings
from langflow.template.frontend_node.chains import ChainFrontendNode
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_class

# Assuming necessary imports for Field, Template, and FrontendNode classes


class ChainCreator(LangChainTypeCreator):
    type_name: str = "chains"

    @property
    def frontend_node_class(self) -> Type[ChainFrontendNode]:
        return ChainFrontendNode

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = chain_type_to_cls_dict
            from langflow.interface.chains.custom import CUSTOM_CHAINS

            self.type_dict.update(CUSTOM_CHAINS)
            # Filter according to settings.chains
            self.type_dict = {
                name: chain
                for name, chain in self.type_dict.items()
                if name in settings.chains or settings.dev
            }
        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        try:
            if name in get_custom_nodes(self.type_name).keys():
                return get_custom_nodes(self.type_name)[name]
            return build_template_from_class(
                name, self.type_to_loader_dict, add_function=True
            )
        except ValueError as exc:
            raise ValueError("Chain not found") from exc
        except AttributeError as exc:
            logger.error(f"Chain {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        custom_chains = list(get_custom_nodes("chains").keys())
        default_chains = list(self.type_to_loader_dict.keys())

        return default_chains + custom_chains


chain_creator = ChainCreator()
