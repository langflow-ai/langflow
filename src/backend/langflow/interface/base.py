from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Union
from langchain.chains.base import Chain
from langchain.agents import AgentExecutor
from pydantic import BaseModel

from langflow.components.field.base import TemplateField
from langflow.components.component.base import Component
from langflow.components.template.base import Template
from langflow.utils.logger import logger

# Assuming necessary imports for Field, Template, and Component classes


class LangChainTypeCreator(BaseModel, ABC):
    type_name: str
    type_dict: Optional[Dict] = None

    @property
    def component_class(self) -> Type[Component]:
        """The class type of the Component created in component."""
        return Component

    @property
    @abstractmethod
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            raise NotImplementedError
        return self.type_dict

    @abstractmethod
    def get_signature(self, name: str) -> Union[Optional[Dict[Any, Any]], Component]:
        pass

    @abstractmethod
    def to_list(self) -> List[str]:
        pass

    def to_dict(self) -> Dict:
        result: Dict = {self.type_name: {}}

        for name in self.to_list():
            # component.to_dict() returns a dict with the following structure:
            # {name: {template: {fields}, description: str}}
            # so we should update the result dict
            node = self.component(name)
            if node is not None:
                node = node.to_dict()  # type: ignore
                result[self.type_name].update(node)

        return result

    def component(self, name) -> Union[Component, None]:
        signature = self.get_signature(name)
        if signature is None:
            logger.error(f"Node {name} not loaded")
            return signature
        if not isinstance(signature, Component):
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
                    file_path=value.get("file_path", None),
                )
                for key, value in signature["template"].items()
                if key != "_type"
            ]
            template = Template(type_name=name, fields=fields)
            signature = self.component_class(
                template=template,
                description=signature.get("description", ""),
                base_classes=signature["base_classes"],
                name=name,
            )

        signature.add_extra_fields()
        signature.add_extra_base_classes()

        return signature


class CustomChain(Chain, ABC):
    """Custom chain"""

    @staticmethod
    def function_name():
        return "CustomChain"

    @classmethod
    def initialize(cls, *args, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


class CustomAgentExecutor(AgentExecutor, ABC):
    """Custom chain"""

    @staticmethod
    def function_name():
        return "CustomChain"

    @classmethod
    def initialize(cls, *args, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)
