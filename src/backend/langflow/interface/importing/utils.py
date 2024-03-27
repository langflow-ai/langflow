# This module is used to import any langchain class by name.

import importlib
import os
from typing import Any, Type

import yaml
from langchain.agents import Agent
from langchain.base_language import BaseLanguageModel
from langchain.chains.base import Chain
from langchain.prompts import PromptTemplate
from langchain.tools import BaseTool
from langchain_core.language_models.chat_models import BaseChatModel
from langflow.interface.custom.custom_component import CustomComponent
from langflow.interface.wrappers.base import wrapper_creator
from langflow.settings import settings
from langflow.utils import validate

COMPONENT_CONFIG = {}


def import_module(module_path: str) -> Any:
    """Import module from module path"""
    if "from" not in module_path:
        # Import the module using the module path
        return importlib.import_module(module_path)

    # Split the module path into its components
    _, module_path, _, object_name = module_path.split()

    # Import the module using the module path
    module = importlib.import_module(module_path)

    return getattr(module, object_name)


def import_class(class_path: str) -> Any:
    """Import class from class path"""
    module_path, class_name = class_path.rsplit(".", 1)
    module = import_module(module_path)
    return getattr(module, class_name)


def import_by_type(_type: str, name: str) -> Any:
    """Import class by type and name"""
    if _type is None:
        raise ValueError(f"Type cannot be None. Check if {name} is in the config file.")

    valid_classes = settings.get_component_setting(name)
    if valid_classes is None:
        raise ValueError(f"Invalid component name: {name}")

    return import_module(valid_classes.module_import)


def get_function(code):
    """Get the function"""
    function_name = validate.extract_function_name(code)

    return validate.create_function(code, function_name)


def eval_custom_component_code(code: str) -> Type[CustomComponent]:
    """Evaluate custom component code"""
    class_name = validate.extract_class_name(code)
    return validate.create_class(code, class_name)
