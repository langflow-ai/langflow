from typing import Dict, List, Optional, Type

from loguru import logger

from langflow_base.interface.base import LangChainTypeCreator
from langflow_base.interface.custom_lists import documentloaders_type_to_cls_dict
from langflow_base.services.deps import get_settings_service
from langflow_base.template.frontend_node.documentloaders import DocumentLoaderFrontNode
from langflow_base.utils.util import build_template_from_class


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
        settings_service = get_settings_service()
        return [
            documentloader.__name__
            for documentloader in self.type_to_loader_dict.values()
            if documentloader.__name__ in settings_service.settings.DOCUMENTLOADERS or settings_service.settings.DEV
        ]


documentloader_creator = DocumentLoaderCreator()
