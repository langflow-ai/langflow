from typing import Dict, List, Optional

from langflow.interface.base import LangChainTypeCreator
from langflow.interface.custom_lists import chain_type_to_cls_dict
from langflow.settings import settings
from langflow.utils.util import build_template_from_class

# Assuming necessary imports for Field, Template, and FrontendNode classes


class ChainCreator(LangChainTypeCreator):
    type_name: str = "chains"

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict = chain_type_to_cls_dict
        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        try:
            return build_template_from_class(name, chain_type_to_cls_dict)
        except ValueError as exc:
            raise ValueError("Memory not found") from exc

    def to_list(self) -> List[str]:
        return [
            chain.__name__
            for chain in self.type_to_loader_dict.values()
            if chain.__name__ in settings.chains or settings.dev
        ]


chain_creator = ChainCreator()
