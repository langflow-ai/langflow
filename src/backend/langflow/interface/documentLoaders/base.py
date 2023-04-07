from typing import Dict, List, Optional

from langflow.interface.base import LangChainTypeCreator
from langflow.interface.custom_lists import documentloaders_type_to_cls_dict
from langflow.interface.documentLoaders.custom import CUSTOM_DOCUMENTLOADERS
from langflow.settings import settings
from langflow.utils.util import build_template_from_class


class DocumentLoaderCreator(LangChainTypeCreator):
    type_name: str = "documentloaders"

    @property
    def type_to_loader_dict(self) -> Dict:
        types = documentloaders_type_to_cls_dict

        # Drop some types that are reimplemented with the same name
        types.pop("TextLoader")
        types.pop("WebBaseLoader")

        for name, documentloader in CUSTOM_DOCUMENTLOADERS.items():
            types[name] = documentloader

        return types

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of a document loader."""
        try:
            signature = build_template_from_class(
                name, documentloaders_type_to_cls_dict
            )

            if name == "TextLoader":
                signature["template"]["file"] = {
                    "type": "file",
                    "required": True,
                    "show": True,
                    "name": "path",
                    "value": "",
                    "suffixes": [".txt"],
                    "fileTypes": ["txt"],
                }
            elif name == "WebBaseLoader":
                signature["template"]["web_path"] = {
                    "type": "str",
                    "required": True,
                    "show": True,
                    "name": "web_path",
                    "value": "",
                    "display_name": "Web Path",
                }

            return signature
        except ValueError as exc:
            raise ValueError(f"Documment Loader {name} not found") from exc

    def to_list(self) -> List[str]:
        return [
            documentloader.__name__
            for documentloader in self.type_to_loader_dict.values()
            if documentloader.__name__ in settings.documentloaders or settings.dev
        ]


documentloader_creator = DocumentLoaderCreator()
