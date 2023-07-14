from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type, Union
from langchain.chains.base import Chain
from langchain.agents import AgentExecutor
from pydantic import BaseModel, validator

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode
from langflow.template.template.base import Template
from langflow.utils import validate
from langflow.utils.logger import logger
from langflow.settings import settings


class Creator(BaseModel, ABC):
    type_name: str
    type_dict: Optional[Dict] = None
    name_docs_dict: Optional[Dict[str, str]] = None

    @property
    def frontend_node_class(self) -> Type[FrontendNode]:
        """The class type of the FrontendNode created in frontend_node."""
        return FrontendNode

    @property
    def docs_map(self) -> Dict[str, str]:
        """A dict with the name of the component as key and the documentation link as value."""
        if self.name_docs_dict is None:
            try:
                type_settings = getattr(settings, self.type_name)
                self.name_docs_dict = {
                    name: value_dict["documentation"]
                    for name, value_dict in type_settings.items()
                }
            except AttributeError as exc:
                logger.error(exc)

                self.name_docs_dict = {}
        return self.name_docs_dict

    @property
    @abstractmethod
    def get_signature(self, name: str) -> Optional[Union[Dict[Any, Any], FrontendNode]]:
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
                node_dict = node.to_dict()
                result[self.type_name].update(node_dict)

        return result

    def frontend_node(self, name) -> Optional[FrontendNode]:
        signature = self.get_signature(name)
        if signature is None:
            logger.error(f"Node {name} not loaded")
            return signature
        if isinstance(signature, dict):
            fields = [
                TemplateField(
                    name=key,
                    field_type=value.get("type", "str"),
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
                if key != "_type" and isinstance(value, dict)
            ]
            template = Template(type_name=name, fields=fields)
            frontend_node_instance = self.frontend_node_class(
                template=template,
                description=signature.get("description", ""),
                base_classes=signature["base_classes"],
                name=name,
            )
        else:
            frontend_node_instance = signature
        frontend_node_instance.add_extra_fields()
        frontend_node_instance.add_extra_base_classes()
        frontend_node_instance.set_documentation(self.docs_map.get(name, ""))
        return frontend_node_instance


class LangChainTypeCreator(Creator):
    @property
    @abstractmethod
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            raise NotImplementedError
        return self.type_dict


class BaseStrCode(BaseModel):
    code: str
    func: Optional[Callable] = None
    imports: Optional[str] = None

    # Eval code and store the function
    def __init__(self, **data):
        super().__init__(**data)

    # Validate the function
    @validator("code")
    def validate_func(cls, v):
        try:
            validate.eval_function(v)
        except Exception as e:
            raise e

        return v

    def get_function(self):
        """Get the function"""
        function_name = validate.extract_function_name(self.code)

        return validate.create_function(self.code, function_name)


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
