from typing import Dict, List, Optional, Type

from langflow.interface.base import LangChainTypeCreator
from langflow.template.frontend_node.documentloaders import DocumentLoaderFrontNode
from langflow.interface.custom_lists import documentloaders_type_to_cls_dict
from langflow.settings import settings
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_class


class DocumentLoaderCreator(LangChainTypeCreator):
    type_name: str = "documentloaders"

    @property
    def frontend_node_class(self) -> Type[DocumentLoaderFrontNode]:
        return DocumentLoaderFrontNode

    @property
    def type_to_loader_dict(self) -> Dict:
        return documentloaders_type_to_cls_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of a document loader."""
        try:
            return build_template_from_class(name, documentloaders_type_to_cls_dict)
        except ValueError as exc:
            raise ValueError(f"Documment Loader {name} not found") from exc
        except AttributeError as exc:
            logger.error(f"Documment Loader {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return [
            documentloader.__name__
            for documentloader in self.type_to_loader_dict.values()
            if documentloader.__name__ in settings.documentloaders or settings.dev
        ]


documentloader_creator = DocumentLoaderCreator()
