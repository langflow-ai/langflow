from typing import Dict, List, Optional, Type

from langflow.interface.base import LangChainTypeCreator
from langflow.services.getters import get_settings_service
from langflow.template.frontend_node.textsplitters import TextSplittersFrontendNode
from langflow.interface.custom_lists import textsplitter_type_to_cls_dict

from loguru import logger
from langflow.utils.util import build_template_from_class


class TextSplitterCreator(LangChainTypeCreator):
    type_name: str = "textsplitters"

    @property
    def frontend_node_class(self) -> Type[TextSplittersFrontendNode]:
        return TextSplittersFrontendNode

    @property
    def type_to_loader_dict(self) -> Dict:
        return textsplitter_type_to_cls_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of a text splitter."""
        try:
            return build_template_from_class(name, textsplitter_type_to_cls_dict)
        except ValueError as exc:
            raise ValueError(f"Text Splitter {name} not found") from exc
        except AttributeError as exc:
            logger.error(f"Text Splitter {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        settings_service = get_settings_service()
        return [
            textsplitter.__name__
            for textsplitter in self.type_to_loader_dict.values()
            if textsplitter.__name__ in settings_service.settings.TEXTSPLITTERS
            or settings_service.settings.DEV
        ]


textsplitter_creator = TextSplitterCreator()
