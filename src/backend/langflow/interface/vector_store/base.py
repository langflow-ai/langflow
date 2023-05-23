from typing import Dict, List, Optional, Type

from langflow.interface.base import LangChainTypeCreator
from langflow.interface.custom_lists import vectorstores_type_to_cls_dict
from langflow.settings import settings
from langflow.template.nodes import VectorStoreFrontendNode
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_class, build_template_from_method


class VectorstoreCreator(LangChainTypeCreator):
    type_name: str = "vectorstores"

    @property
    def frontend_node_class(self) -> Type[VectorStoreFrontendNode]:
        return VectorStoreFrontendNode

    @property
    def type_to_loader_dict(self) -> Dict:
        return vectorstores_type_to_cls_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of an embedding."""
        try:
            signature = build_template_from_method(
                name,
                type_to_cls_dict=vectorstores_type_to_cls_dict,
                method_name="from_texts",
            )

            # TODO: Use FrontendendNode class to build the signature
            # signature["template"] = {
            #     "documents": {
            #         "type": "TextSplitter",
            #         "required": True,
            #         "show": True,
            #         "name": "documents",
            #         "display_name": "Text Splitter",
            #     },
            #     "embedding": {
            #         "type": "Embeddings",
            #         "required": True,
            #         "show": True,
            #         "name": "embedding",
            #         "display_name": "Embedding",
            #     },
            # }
            return signature

        except ValueError as exc:
            raise ValueError(f"Vector Store {name} not found") from exc
        except AttributeError as exc:
            logger.error(f"Vector Store {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return [
            vectorstore
            for vectorstore in self.type_to_loader_dict.keys()
            if vectorstore in settings.vectorstores or settings.dev
        ]


vectorstore_creator = VectorstoreCreator()
