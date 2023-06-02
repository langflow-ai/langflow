from typing import Any, Dict, List, Optional, Type

from langchain import vectorstores

from langflow.interface.base import LangChainTypeCreator
from langflow.interface.importing.utils import import_class
from langflow.settings import settings
from langflow.template.frontend_node.vectorstores import VectorStoreFrontendNode
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_method


class VectorstoreCreator(LangChainTypeCreator):
    type_name: str = "vectorstores"

    @property
    def frontend_node_class(self) -> Type[VectorStoreFrontendNode]:
        return VectorStoreFrontendNode

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            self.type_dict: dict[str, Any] = {
                vectorstore_name: import_class(
                    f"langchain.vectorstores.{vectorstore_name}"
                )
                for vectorstore_name in vectorstores.__all__
            }
        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of an embedding."""
        try:
            return build_template_from_method(
                name,
                type_to_cls_dict=self.type_to_loader_dict,
                method_name="from_texts",
            )
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
