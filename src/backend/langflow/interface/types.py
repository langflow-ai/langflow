import ast
import contextlib
from typing import Any, List
from langflow.api.utils import get_new_key
from langflow.interface.agents.base import agent_creator
from langflow.interface.chains.base import chain_creator
from langflow.interface.custom.constants import CUSTOM_COMPONENT_SUPPORTED_TYPES
from langflow.interface.custom.utils import extract_inner_type
from langflow.interface.document_loaders.base import documentloader_creator
from langflow.interface.embeddings.base import embedding_creator
from langflow.interface.importing.utils import get_function_custom
from langflow.interface.llms.base import llm_creator
from langflow.interface.memories.base import memory_creator
from langflow.interface.prompts.base import prompt_creator
from langflow.interface.text_splitters.base import textsplitter_creator
from langflow.interface.toolkits.base import toolkits_creator
from langflow.interface.tools.base import tool_creator
from langflow.interface.utilities.base import utility_creator
from langflow.interface.vector_store.base import vectorstore_creator
from langflow.interface.wrappers.base import wrapper_creator
from langflow.interface.output_parsers.base import output_parser_creator
from langflow.interface.custom.base import custom_component_creator
from langflow.interface.custom.custom_component import CustomComponent

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.constants import CLASSES_TO_REMOVE
from langflow.template.frontend_node.custom_components import (
    CustomComponentFrontendNode,
)
from langflow.interface.retrievers.base import retriever_creator

from langflow.interface.custom.directory_reader import DirectoryReader
from loguru import logger
from langflow.utils.util import get_base_classes

import re
import warnings
import traceback
from fastapi import HTTPException


# Used to get the base_classes list
def get_type_list():
    """Get a list of all langchain types"""
    all_types = build_langchain_types_dict()

    # all_types.pop("tools")

    for key, value in all_types.items():
        all_types[key] = [item["template"]["_type"] for item in value.values()]

    return all_types


def build_langchain_types_dict():  # sourcery skip: dict-assign-update-to-union
    """Build a dictionary of all langchain types"""
    all_types = {}

    creators = [
        chain_creator,
        agent_creator,
        prompt_creator,
        llm_creator,
        memory_creator,
        tool_creator,
        toolkits_creator,
        wrapper_creator,
        embedding_creator,
        vectorstore_creator,
        documentloader_creator,
        textsplitter_creator,
        utility_creator,
        output_parser_creator,
        retriever_creator,
        custom_component_creator,
    ]

    all_types = {}
    for creator in creators:
        created_types = creator.to_dict()
        if created_types[creator.type_name].values():
            all_types.update(created_types)

    return all_types


def process_type(field_type: str):
    if field_type.startswith("list") or field_type.startswith("List"):
        return extract_inner_type(field_type)
    return "prompt" if field_type == "Prompt" else field_type


# TODO: Move to correct place
def add_new_custom_field(
    template,
    field_name: str,
    field_type: str,
    field_value: Any,
    field_required: bool,
    field_config: dict,
):
    # Check field_config if any of the keys are in it
    # if it is, update the value
    display_name = field_config.pop("display_name", field_name)
    field_type = field_config.pop("field_type", field_type)
    field_contains_list = "list" in field_type.lower()
    field_type = process_type(field_type)
    field_value = field_config.pop("value", field_value)
    field_advanced = field_config.pop("advanced", False)

    if field_type == "bool" and field_value is None:
        field_value = False

    # If options is a list, then it's a dropdown
    # If options is None, then it's a list of strings
    is_list = isinstance(field_config.get("options"), list)
    field_config["is_list"] = (
        is_list or field_config.get("is_list", False) or field_contains_list
    )

    if "name" in field_config:
        warnings.warn(
            "The 'name' key in field_config is used to build the object and can't be changed."
        )
        field_config.pop("name", None)

    required = field_config.pop("required", field_required)
    placeholder = field_config.pop("placeholder", "")

    new_field = TemplateField(
        name=field_name,
        field_type=field_type,
        value=field_value,
        show=True,
        required=required,
        advanced=field_advanced,
        placeholder=placeholder,
        display_name=display_name,
        **field_config,
    )
    template.get("template")[field_name] = new_field.to_dict()
    template.get("custom_fields")[field_name] = None

    return template


# TODO: Move to correct place
def add_code_field(template, raw_code, field_config):
    # Field with the Python code to allow update

    code_field = {
        "code": {
            "dynamic": True,
            "required": True,
            "placeholder": "",
            "show": field_config.pop("show", True),
            "multiline": True,
            "value": raw_code,
            "password": False,
            "name": "code",
            "advanced": field_config.pop("advanced", False),
            "type": "code",
            "list": False,
        }
    }
    template.get("template")["code"] = code_field.get("code")

    return template


def extract_type_from_optional(field_type):
    """
    Extract the type from a string formatted as "Optional[<type>]".

    Parameters:
    field_type (str): The string from which to extract the type.

    Returns:
    str: The extracted type, or an empty string if no type was found.
    """
    match = re.search(r"\[(.*?)\]$", field_type)
    return match[1] if match else None


def build_frontend_node(custom_component: CustomComponent):
    """Build a frontend node for a custom component"""
    try:
        return (
            CustomComponentFrontendNode().to_dict().get(type(custom_component).__name__)
        )

    except Exception as exc:
        logger.error(f"Error while building base frontend node: {exc}")
        return None


def update_attributes(frontend_node, template_config):
    """Update the display name and description of a frontend node"""
    attributes = [
        "display_name",
        "description",
        "beta",
        "documentation",
        "output_types",
    ]
    for attribute in attributes:
        if attribute in template_config:
            frontend_node[attribute] = template_config[attribute]


def build_field_config(custom_component: CustomComponent):
    """Build the field configuration for a custom component"""

    try:
        custom_class = get_function_custom(custom_component.code)
    except Exception as exc:
        logger.error(f"Error while getting custom function: {str(exc)}")
        return {}

    try:
        return custom_class().build_config()
    except Exception as exc:
        logger.error(f"Error while building field config: {str(exc)}")
        return {}


def add_extra_fields(frontend_node, field_config, function_args):
    """Add extra fields to the frontend node"""
    if function_args is None or function_args == "":
        return

    # sort function_args which is a list of dicts
    function_args.sort(key=lambda x: x["name"])

    for extra_field in function_args:
        if "name" not in extra_field or extra_field["name"] == "self":
            continue

        field_name, field_type, field_value, field_required = get_field_properties(
            extra_field
        )
        config = field_config.get(field_name, {})
        frontend_node = add_new_custom_field(
            frontend_node,
            field_name,
            field_type,
            field_value,
            field_required,
            config,
        )


def get_field_properties(extra_field):
    """Get the properties of an extra field"""
    field_name = extra_field["name"]
    field_type = extra_field.get("type", "str")
    field_value = extra_field.get("default", "")
    field_required = "optional" not in field_type.lower()

    if not field_required:
        field_type = extract_type_from_optional(field_type)

    with contextlib.suppress(Exception):
        field_value = ast.literal_eval(field_value)
    return field_name, field_type, field_value, field_required


def add_base_classes(frontend_node, return_types: List[str]):
    """Add base classes to the frontend node"""
    for return_type in return_types:
        if return_type not in CUSTOM_COMPONENT_SUPPORTED_TYPES or return_type is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": (
                        "Invalid return type should be one of: "
                        f"{list(CUSTOM_COMPONENT_SUPPORTED_TYPES.keys())}"
                    ),
                    "traceback": traceback.format_exc(),
                },
            )

        return_type_instance = CUSTOM_COMPONENT_SUPPORTED_TYPES.get(return_type)
        base_classes = get_base_classes(return_type_instance)

        for base_class in base_classes:
            if base_class not in CLASSES_TO_REMOVE:
                frontend_node.get("base_classes").append(base_class)


def build_langchain_template_custom_component(custom_component: CustomComponent):
    """Build a custom component template for the langchain"""
    try:
        logger.debug("Building custom component template")
        frontend_node = build_frontend_node(custom_component)

        if frontend_node is None:
            return None
        logger.debug("Built base frontend node")
        template_config = custom_component.build_template_config

        update_attributes(frontend_node, template_config)
        logger.debug("Updated attributes")
        field_config = build_field_config(custom_component)
        logger.debug("Built field config")
        entrypoint_args = custom_component.get_function_entrypoint_args

        add_extra_fields(frontend_node, field_config, entrypoint_args)
        logger.debug("Added extra fields")
        frontend_node = add_code_field(
            frontend_node, custom_component.code, field_config.get("code", {})
        )
        logger.debug("Added code field")
        add_base_classes(
            frontend_node, custom_component.get_function_entrypoint_return_type
        )
        logger.debug("Added base classes")
        return frontend_node
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=400,
            detail={
                "error": (
                    "Invalid type convertion. Please check your code and try again."
                ),
                "traceback": traceback.format_exc(),
            },
        ) from exc


def load_files_from_path(path: str):
    """Load all files from a given path"""
    reader = DirectoryReader(path, False)

    return reader.get_files()


def build_and_validate_all_files(reader: DirectoryReader, file_list):
    """Build and validate all files"""
    data = reader.build_component_menu_list(file_list)

    valid_components = reader.filter_loaded_components(data=data, with_errors=False)
    invalid_components = reader.filter_loaded_components(data=data, with_errors=True)

    return valid_components, invalid_components


def build_valid_menu(valid_components):
    """Build the valid menu"""
    valid_menu = {}
    logger.debug("------------------- VALID COMPONENTS -------------------")
    for menu_item in valid_components["menu"]:
        menu_name = menu_item["name"]
        valid_menu[menu_name] = {}

        for component in menu_item["components"]:
            logger.debug(
                f"Building component: {component.get('name'), component.get('output_types')}"
            )
            try:
                component_name = component["name"]
                component_code = component["code"]
                component_output_types = component["output_types"]

                component_extractor = CustomComponent(code=component_code)
                component_extractor.is_check_valid()

                component_template = build_langchain_template_custom_component(
                    component_extractor
                )
                component_template["output_types"] = component_output_types
                if len(component_output_types) == 1:
                    component_name = component_output_types[0]
                else:
                    file_name = component.get("file").split(".")[0]
                    if "_" in file_name:
                        # turn .py file into camelcase
                        component_name = "".join(
                            [word.capitalize() for word in file_name.split("_")]
                        )
                    else:
                        component_name = file_name

                valid_menu[menu_name][component_name] = component_template
                logger.debug(f"Added {component_name} to valid menu to {menu_name}")

            except Exception as exc:
                logger.error(f"Error loading Component: {component['output_types']}")
                logger.exception(
                    f"Error while building custom component {component_output_types}: {exc}"
                )

    return valid_menu


def build_invalid_menu(invalid_components):
    """Build the invalid menu"""
    if invalid_components.get("menu"):
        logger.debug("------------------- INVALID COMPONENTS -------------------")
    invalid_menu = {}
    for menu_item in invalid_components["menu"]:
        menu_name = menu_item["name"]
        invalid_menu[menu_name] = {}

        for component in menu_item["components"]:
            try:
                component_name = component["name"]
                component_code = component["code"]

                component_template = (
                    CustomComponentFrontendNode(
                        description="ERROR - Check your Python Code",
                        display_name=f"ERROR - {component_name}",
                    )
                    .to_dict()
                    .get(type(CustomComponent()).__name__)
                )

                component_template["error"] = component.get("error", None)
                logger.debug(component)
                logger.debug(f"Component Path: {component.get('path', None)}")
                logger.debug(f"Component Error: {component.get('error', None)}")
                component_template.get("template").get("code")["value"] = component_code

                invalid_menu[menu_name][component_name] = component_template
                logger.debug(f"Added {component_name} to invalid menu to {menu_name}")

            except Exception as exc:
                logger.exception(
                    f"Error while creating custom component [{component_name}]: {str(exc)}"
                )

    return invalid_menu


def merge_nested_dicts_with_renaming(dict1, dict2):
    for key, value in dict2.items():
        if (
            key in dict1
            and isinstance(value, dict)
            and isinstance(dict1.get(key), dict)
        ):
            for sub_key, sub_value in value.items():
                if sub_key in dict1[key]:
                    new_key = get_new_key(dict1[key], sub_key)
                    dict1[key][new_key] = sub_value
                else:
                    dict1[key][sub_key] = sub_value
        else:
            dict1[key] = value
    return dict1


def build_langchain_custom_component_list_from_path(path: str):
    """Build a list of custom components for the langchain from a given path"""
    file_list = load_files_from_path(path)
    reader = DirectoryReader(path, False)

    valid_components, invalid_components = build_and_validate_all_files(
        reader, file_list
    )

    valid_menu = build_valid_menu(valid_components)
    invalid_menu = build_invalid_menu(invalid_components)

    return merge_nested_dicts_with_renaming(valid_menu, invalid_menu)


def get_all_types_dict(settings_service):
    native_components = build_langchain_types_dict()
    # custom_components is a list of dicts
    # need to merge all the keys into one dict
    custom_components_from_file: dict[str, Any] = {}
    if settings_service.settings.COMPONENTS_PATH:
        logger.info(
            f"Building custom components from {settings_service.settings.COMPONENTS_PATH}"
        )

        custom_component_dicts = []
        processed_paths = []
        for path in settings_service.settings.COMPONENTS_PATH:
            if str(path) in processed_paths:
                continue
            custom_component_dict = build_langchain_custom_component_list_from_path(
                str(path)
            )
            custom_component_dicts.append(custom_component_dict)
            processed_paths.append(str(path))

        logger.info(f"Loading {len(custom_component_dicts)} category(ies)")
        for custom_component_dict in custom_component_dicts:
            # custom_component_dict is a dict of dicts
            if not custom_component_dict:
                continue
            category = list(custom_component_dict.keys())[0]
            logger.info(
                f"Loading {len(custom_component_dict[category])} component(s) from category {category}"
            )
            custom_components_from_file = merge_nested_dicts_with_renaming(
                custom_components_from_file, custom_component_dict
            )

    return merge_nested_dicts_with_renaming(
        native_components, custom_components_from_file
    )


def merge_nested_dicts(dict1, dict2):
    for key, value in dict2.items():
        if isinstance(value, dict) and isinstance(dict1.get(key), dict):
            dict1[key] = merge_nested_dicts(dict1[key], value)
        else:
            dict1[key] = value
    return dict1
