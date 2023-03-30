from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from abc import ABC, abstractmethod
from langflow.template.template import Template, Field, FrontendNode


# Assuming necessary imports for Field, Template, and FrontendNode classes


class LangChainTypeCreator(BaseModel, ABC):
    type_name: str

    @property
    @abstractmethod
    def type_to_loader_dict(self) -> Dict:
        pass

    @abstractmethod
    def get_signature(self, name: str) -> Optional[Dict[Any, Any]]:
        pass

    @abstractmethod
    def to_list(self) -> List[str]:
        pass

    def to_dict(self) -> Dict:
        result: Dict = {self.type_name: {}}

        for name in self.to_list():
            result[self.type_name][name] = self.frontend_node(name).to_dict()

        return result

    def frontend_node(self, name) -> FrontendNode:
        signature = self.get_signature(name)
        if signature is None:
            raise ValueError(f"{name} not found")
        fields = [
            Field(
                name=key,
                field_type=value["type"],
                required=value.get("required", False),
                placeholder=value.get("placeholder", ""),
                is_list=value.get("list", False),
                show=value.get("show", True),
                multiline=value.get("multiline", False),
                value=value.get("value", None),
            )
            for key, value in signature["template"].items()
            if key != "_type"
        ]
        template = Template(type_name=name, fields=fields)
        return FrontendNode(
            template=template,
            description=signature["description"],
            base_classes=signature["base_classes"],
            name=name,
        )
