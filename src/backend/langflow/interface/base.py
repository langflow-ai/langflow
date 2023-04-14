from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel

from langflow.template.base import FrontendNode, Template, TemplateField
from langflow.utils.logger import logger

# Assuming necessary imports for Field, Template, and FrontendNode classes


class LangChainTypeCreator(BaseModel, ABC):
    type_name: str
    type_dict: Optional[Dict] = None

    @property
    def frontend_node_class(self) -> Type[FrontendNode]:
        """The class type of the FrontendNode created in frontend_node."""
        return FrontendNode

    @property
    @abstractmethod
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            raise NotImplementedError
        return self.type_dict

    @abstractmethod
    def get_signature(self, name: str) -> Union[Optional[Dict[Any, Any]], FrontendNode]:
        pass

    @abstractmethod
    def to_list(self) -> List[str]:
        pass

    def to_dict(self) -> Dict:
        result: Dict = {self.type_name: {}}

        for name in self.to_list():
            # frontend_node.to_dict() returns a dict with the following structure:
            # {name: {template: {fields}, description: str}}
            # so we should update the result dict
            node = self.frontend_node(name)
            if node is not None:
                node = node.to_dict()
                result[self.type_name].update(node)

        return result

    def frontend_node(self, name) -> Union[FrontendNode, None]:
        signature = self.get_signature(name)
        if signature is None:
            logger.error(f"Node {name} not loaded")
            return None
        if isinstance(signature, FrontendNode):
            return signature
        fields = [
            TemplateField(
                name=key,
                field_type=value["type"],
                required=value.get("required", False),
                placeholder=value.get("placeholder", ""),
                is_list=value.get("list", False),
                show=value.get("show", True),
                multiline=value.get("multiline", False),
                value=value.get("value", None),
                suffixes=value.get("suffixes", []),
                file_types=value.get("fileTypes", []),
                content=value.get("content", None),
            )
            for key, value in signature["template"].items()
            if key != "_type"
        ]
        template = Template(type_name=name, fields=fields)
        return self.frontend_node_class(
            template=template,
            description=signature.get("description", ""),
            base_classes=signature["base_classes"],
            name=name,
        )
