from typing import Dict, List, Optional

from langflow.interface.base import LangChainTypeCreator
from langflow.interface.custom_lists import textsplitter_type_to_cls_dict
from langflow.settings import settings
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_class


class TextSplitterCreator(LangChainTypeCreator):
    type_name: str = "textsplitters"

    @property
    def type_to_loader_dict(self) -> Dict:
        return textsplitter_type_to_cls_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of a text splitter."""
        try:
            signature = build_template_from_class(name, textsplitter_type_to_cls_dict)

            signature["template"]["documents"] = {
                "type": "BaseLoader",
                "required": True,
                "show": True,
                "name": "documents",
            }

            signature["template"]["separator"] = {
                "type": "str",
                "required": True,
                "show": True,
                "value": ".",
                "name": "separator",
                "display_name": "Separator",
            }

            signature["template"]["chunk_size"] = {
                "type": "int",
                "required": True,
                "show": True,
                "value": 1000,
                "name": "chunk_size",
                "display_name": "Chunk Size",
            }

            signature["template"]["chunk_overlap"] = {
                "type": "int",
                "required": True,
                "show": True,
                "value": 200,
                "name": "chunk_overlap",
                "display_name": "Chunk Overlap",
            }

            return signature
        except ValueError as exc:
            raise ValueError(f"Text Splitter {name} not found") from exc
        except AttributeError as exc:
            logger.error(f"Text Splitter {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return [
            textsplitter.__name__
            for textsplitter in self.type_to_loader_dict.values()
            if textsplitter.__name__ in settings.textsplitters or settings.dev
        ]


textsplitter_creator = TextSplitterCreator()
