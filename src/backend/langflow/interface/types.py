import ast
import contextlib
import re
import traceback
import warnings
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from cachetools import LRUCache, cached
from fastapi import HTTPException
from loguru import logger

from langflow.field_typing.range_spec import RangeSpec
from langflow.interface.agents.base import agent_creator
from langflow.interface.chains.base import chain_creator
from langflow.interface.custom.custom_component import CustomComponent
from langflow.interface.custom.directory_reader import DirectoryReader
from langflow.interface.custom.utils import extract_inner_type
from langflow.interface.document_loaders.base import documentloader_creator
from langflow.interface.embeddings.base import embedding_creator
from langflow.interface.importing.utils import eval_custom_component_code
from langflow.interface.llms.base import llm_creator
from langflow.interface.memories.base import memory_creator
from langflow.interface.output_parsers.base import output_parser_creator
from langflow.interface.prompts.base import prompt_creator
from langflow.interface.retrievers.base import retriever_creator
from langflow.interface.text_splitters.base import textsplitter_creator
from langflow.interface.toolkits.base import toolkits_creator
from langflow.interface.tools.base import tool_creator
from langflow.interface.utilities.base import utility_creator
from langflow.interface.vector_store.base import vectorstore_creator
from langflow.interface.wrappers.base import wrapper_creator
from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.custom_components import CustomComponentFrontendNode
from langflow.utils.util import get_base_classes


# Used to get the base_classes list
def get_type_list():
    """Get a list of all langchain types"""
    all_types = build_langchain_types_dict()

    # all_types.pop("tools")

    for key, value in all_types.items():
        all_types[key] = [item["template"]["_type"] for item in value.values()]

    return all_types


@cached(LRUCache(maxsize=1))
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
    frontend_node: CustomComponentFrontendNode,
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
    field_config["is_list"] = is_list or field_config.get("is_list", False) or field_contains_list

    if "name" in field_config:
        warnings.warn("The 'name' key in field_config is used to build the object and can't be changed.")
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
        **sanitize_field_config(field_config),
    )
    frontend_node.template.upsert_field(field_name, new_field)
    if isinstance(frontend_node.custom_fields, dict):
        frontend_node.custom_fields[field_name] = None

    return frontend_node


def sanitize_field_config(field_config: Dict):
    # If any of the already existing keys are in field_config, remove them
    for key in ["name", "field_type", "value", "required", "placeholder", "display_name", "advanced", "show"]:
        field_config.pop(key, None)
    return field_config


# TODO: Move to correct place
def add_code_field(frontend_node: CustomComponentFrontendNode, raw_code, field_config):
    code_field = TemplateField(
        dynamic=True,
        required=True,
        placeholder="",
        multiline=True,
        value=raw_code,
        password=False,
        name="code",
        advanced=field_config.pop("advanced", False),
        field_type="code",
        is_list=False,
    )
    frontend_node.template.add_field(code_field)

    return frontend_node


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


def build_frontend_node(template_config):
    """Build a frontend node for a custom component"""
    try:
        sanitized_template_config = sanitize_template_config(template_config)
        return CustomComponentFrontendNode(**sanitized_template_config)
    except Exception as exc:
        logger.error(f"Error while building base frontend node: {exc}")
        raise exc


def sanitize_template_config(template_config):
    """Sanitize the template config"""
    attributes = {
        "display_name",
        "description",
        "beta",
        "documentation",
        "output_types",
    }
    for key in template_config.copy():
        if key not in attributes:
            template_config.pop(key, None)

    return template_config


def build_field_config(
    custom_component: CustomComponent, user_id: Optional[Union[str, UUID]] = None, update_field=None
):
    """Build the field configuration for a custom component"""

    try:
        if custom_component.code is None:
            return {}
        elif isinstance(custom_component.code, str):
            custom_class = eval_custom_component_code(custom_component.code)
        else:
            raise ValueError("Invalid code type")
    except Exception as exc:
        logger.error(f"Error while evaluating custom component code: {str(exc)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": ("Invalid type convertion. Please check your code and try again."),
                "traceback": traceback.format_exc(),
            },
        ) from exc

    try:
        build_config: Dict = custom_class(user_id=user_id).build_config()

        for field_name, field in build_config.items():
            # Allow user to build TemplateField as well
            # as a dict with the same keys as TemplateField
            field_dict = get_field_dict(field)
            if update_field is not None and field_name != update_field:
                continue
            try:
                update_field_dict(field_dict)
                build_config[field_name] = field_dict
            except Exception as exc:
                logger.error(f"Error while getting build_config: {str(exc)}")

        return build_config

    except Exception as exc:
        logger.error(f"Error while building field config: {str(exc)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": ("Invalid type convertion. Please check your code and try again."),
                "traceback": traceback.format_exc(),
            },
        ) from exc


def get_field_dict(field):
    """Get the field dictionary from a TemplateField or a dict"""
    if isinstance(field, TemplateField):
        return field.model_dump(by_alias=True, exclude_none=True)
    return field


def update_field_dict(field_dict):
    """Update the field dictionary by calling options() or value() if they are callable"""
    if "options" in field_dict and callable(field_dict["options"]):
        field_dict["options"] = field_dict["options"]()
        # Also update the "refresh" key
        field_dict["refresh"] = True

    if "value" in field_dict and callable(field_dict["value"]):
        field_dict["value"] = field_dict["value"](field_dict.get("options", []))
        field_dict["refresh"] = True

    # Let's check if "range_spec" is a RangeSpec object
    if "rangeSpec" in field_dict and isinstance(field_dict["rangeSpec"], RangeSpec):
        field_dict["rangeSpec"] = field_dict["rangeSpec"].model_dump()


def add_extra_fields(frontend_node, field_config, function_args):
    """Add extra fields to the frontend node"""
    if not function_args:
        return

    # sort function_args which is a list of dicts
    function_args.sort(key=lambda x: x["name"])

    for extra_field in function_args:
        if "name" not in extra_field or extra_field["name"] == "self":
            continue

        field_name, field_type, field_value, field_required = get_field_properties(extra_field)
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
    if field_value is not None:
        with contextlib.suppress(Exception):
            field_value = ast.literal_eval(field_value)
    return field_name, field_type, field_value, field_required


def add_base_classes(frontend_node: CustomComponentFrontendNode, return_types: List[str]):
    """Add base classes to the frontend node"""
    for return_type_instance in return_types:
        if return_type_instance is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": ("Invalid return type. Please check your code and try again."),
                    "traceback": traceback.format_exc(),
                },
            )

        base_classes = get_base_classes(return_type_instance)

        for base_class in base_classes:
            frontend_node.add_base_class(base_class)


def add_output_types(frontend_node: CustomComponentFrontendNode, return_types: List[str]):
    """Add output types to the frontend node"""
    for return_type in return_types:
        if return_type is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": ("Invalid return type. Please check your code and try again."),
                    "traceback": traceback.format_exc(),
                },
            )
        if hasattr(return_type, "__name__"):
            return_type = return_type.__name__
        elif hasattr(return_type, "__class__"):
            return_type = return_type.__class__.__name__
        else:
            return_type = str(return_type)

        frontend_node.add_output_type(return_type)


def build_custom_component_template(
    custom_component: CustomComponent,
    user_id: Optional[Union[str, UUID]] = None,
    update_field: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build a custom component template for the langchain"""
    try:
        logger.debug("Building custom component template")
        frontend_node = build_frontend_node(custom_component.template_config)

        logger.debug("Built base frontend node")

        logger.debug("Updated attributes")
        field_config = build_field_config(custom_component, user_id=user_id, update_field=update_field)
        logger.debug("Built field config")
        entrypoint_args = custom_component.get_function_entrypoint_args

        add_extra_fields(frontend_node, field_config, entrypoint_args)
        logger.debug("Added extra fields")
        frontend_node = add_code_field(frontend_node, custom_component.code, field_config.get("code", {}))
        logger.debug("Added code field")
        add_base_classes(frontend_node, custom_component.get_function_entrypoint_return_type)
        add_output_types(frontend_node, custom_component.get_function_entrypoint_return_type)
        logger.debug("Added base classes")
        return frontend_node.to_dict(add_name=False)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=400,
            detail={
                "error": ("Invalid type convertion. Please check your code and try again."),
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
    """Build the valid menu."""
    valid_menu = {}
    logger.debug("------------------- VALID COMPONENTS -------------------")
    for menu_item in valid_components["menu"]:
        menu_name = menu_item["name"]
        valid_menu[menu_name] = build_menu_items(menu_item)
    return valid_menu


def build_menu_items(menu_item):
    """Build menu items for a given menu."""
    menu_items = {}
    for component in menu_item["components"]:
        try:
            component_name, component_template = build_component(component)
            menu_items[component_name] = component_template
            logger.debug(f"Added {component_name} to valid menu.")
        except Exception as exc:
            logger.error(f"Error loading Component: {component['output_types']}")
            logger.exception(f"Error while building custom component {component['output_types']}: {exc}")
    return menu_items


def build_component(component):
    """Build a single component."""
    logger.debug(f"Building component: {component.get('name'), component.get('output_types')}")
    component_name = determine_component_name(component)
    component_template = create_component_template(component)
    return component_name, component_template


def determine_component_name(component):
    """Determine the name of the component."""
    component_output_types = component["output_types"]
    if len(component_output_types) == 1:
        return component_output_types[0]
    else:
        file_name = component.get("file").split(".")[0]
        return "".join(word.capitalize() for word in file_name.split("_")) if "_" in file_name else file_name


def create_component_template(component):
    """Create a template for a component."""
    component_code = component["code"]
    component_output_types = component["output_types"]

    component_extractor = CustomComponent(code=component_code)
    component_extractor.validate()

    component_template = build_custom_component_template(component_extractor)
    component_template["output_types"] = component_output_types
    return component_template


def build_invalid_menu(invalid_components):
    """Build the invalid menu."""
    if not invalid_components.get("menu"):
        return {}

    logger.debug("------------------- INVALID COMPONENTS -------------------")
    invalid_menu = {}
    for menu_item in invalid_components["menu"]:
        menu_name = menu_item["name"]
        invalid_menu[menu_name] = build_invalid_menu_items(menu_item)
    return invalid_menu


def build_invalid_menu_items(menu_item):
    """Build invalid menu items for a given menu."""
    menu_items = {}
    for component in menu_item["components"]:
        try:
            component_name, component_template = build_invalid_component(component)
            menu_items[component_name] = component_template
            logger.debug(f"Added {component_name} to invalid menu.")
        except Exception as exc:
            logger.exception(f"Error while creating custom component [{component_name}]: {str(exc)}")
    return menu_items


def build_invalid_component(component):
    """Build a single invalid component."""
    component_name = component["name"]
    component_template = create_invalid_component_template(component, component_name)
    log_invalid_component_details(component)
    return component_name, component_template


def create_invalid_component_template(component, component_name):
    """Create a template for an invalid component."""
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
    component_template.get("template").get("code")["value"] = component_code
    return component_template


def log_invalid_component_details(component):
    """Log details of an invalid component."""
    logger.debug(component)
    logger.debug(f"Component Path: {component.get('path', None)}")
    logger.debug(f"Component Error: {component.get('error', None)}")


def get_new_key(dictionary, original_key):
    counter = 1
    new_key = original_key + " (" + str(counter) + ")"
    while new_key in dictionary:
        counter += 1
        new_key = original_key + " (" + str(counter) + ")"
    return new_key


def merge_nested_dicts_with_renaming(dict1, dict2):
    for key, value in dict2.items():
        if key in dict1 and isinstance(value, dict) and isinstance(dict1.get(key), dict):
            for sub_key, sub_value in value.items():
                # if sub_key in dict1[key]:
                #     new_key = get_new_key(dict1[key], sub_key)
                #     dict1[key][new_key] = sub_value
                # else:
                dict1[key][sub_key] = sub_value
        else:
            dict1[key] = value
    return dict1


def build_custom_component_list_from_path(path: str):
    """Build a list of custom components for the langchain from a given path"""
    file_list = load_files_from_path(path)
    reader = DirectoryReader(path, False)

    valid_components, invalid_components = build_and_validate_all_files(reader, file_list)

    valid_menu = build_valid_menu(valid_components)
    invalid_menu = build_invalid_menu(invalid_components)

    return merge_nested_dicts_with_renaming(valid_menu, invalid_menu)


def get_all_types_dict(settings_service):
    """Get all types dictionary combining native and custom components."""
    native_components = build_langchain_types_dict()
    custom_components_from_file = build_custom_components(settings_service)
    return merge_nested_dicts_with_renaming(native_components, custom_components_from_file)


def build_custom_components(settings_service):
    """Build custom components from the specified paths."""
    if not settings_service.settings.COMPONENTS_PATH:
        return {}

    logger.info(f"Building custom components from {settings_service.settings.COMPONENTS_PATH}")
    custom_components_from_file = {}
    processed_paths = set()
    for path in settings_service.settings.COMPONENTS_PATH:
        path_str = str(path)
        if path_str in processed_paths:
            continue

        custom_component_dict = build_custom_component_list_from_path(path_str)
        if custom_component_dict:
            category = next(iter(custom_component_dict))
            logger.info(f"Loading {len(custom_component_dict[category])} component(s) from category {category}")
            custom_components_from_file = merge_nested_dicts_with_renaming(
                custom_components_from_file, custom_component_dict
            )
        processed_paths.add(path_str)

    return custom_components_from_file


def merge_nested_dicts(dict1, dict2):
    for key, value in dict2.items():
        if isinstance(value, dict) and isinstance(dict1.get(key), dict):
            dict1[key] = merge_nested_dicts(dict1[key], value)
        else:
            dict1[key] = value
    return dict1


def create_and_validate_component(code: str) -> CustomComponent:
    component = CustomComponent(code=code)
    component.validate()
    return component
