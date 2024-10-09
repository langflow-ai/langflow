import ast
import contextlib
import pkgutil
import re
import traceback
from typing import Any, Dict
from uuid import UUID
import importlib
import inspect
from typing import List

from astra_assistants.tools.tool_interface import ToolInterface
from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel

from langflow.components.astra_assistants.tools.util import tool_interface_to_component
from langflow.custom import CustomComponent
from langflow.custom.custom_component.component import Component
from langflow.custom.directory_reader.utils import (
    abuild_custom_component_list_from_path,
    build_custom_component_list_from_path,
    build_menu_items,
    merge_nested_dicts_with_renaming,
)
from langflow.custom.eval import eval_custom_component_code
from langflow.custom.schema import MissingDefault
from langflow.field_typing.range_spec import RangeSpec
from langflow.helpers.custom import format_type
from langflow.schema import dotdict
from langflow.template.field.base import Input
from langflow.template.frontend_node.custom_components import ComponentFrontendNode, CustomComponentFrontendNode
from langflow.type_extraction.type_extraction import extract_inner_type
from langflow.utils import validate
from langflow.utils.util import get_base_classes


class UpdateBuildConfigError(Exception):
    pass


def add_output_types(frontend_node: CustomComponentFrontendNode, return_types: list[str]):
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
        if return_type is str:
            return_type = "Text"
        elif hasattr(return_type, "__name__"):
            return_type = return_type.__name__
        elif hasattr(return_type, "__class__"):
            return_type = return_type.__class__.__name__
        else:
            return_type = str(return_type)

        frontend_node.add_output_type(return_type)


def reorder_fields(frontend_node: CustomComponentFrontendNode, field_order: list[str]):
    """Reorder fields in the frontend node based on the specified field_order."""
    if not field_order:
        return

    # Create a dictionary for O(1) lookup time.
    field_dict = {field.name: field for field in frontend_node.template.fields}
    reordered_fields = [field_dict[name] for name in field_order if name in field_dict]
    # Add any fields that are not in the field_order list
    for field in frontend_node.template.fields:
        if field.name not in field_order:
            reordered_fields.append(field)
    frontend_node.template.fields = reordered_fields
    frontend_node.field_order = field_order


def add_base_classes(frontend_node: CustomComponentFrontendNode, return_types: list[str]):
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
        if return_type_instance is str:
            base_classes.append("Text")

        for base_class in base_classes:
            frontend_node.add_base_class(base_class)


def extract_type_from_optional(field_type):
    """
    Extract the type from a string formatted as "Optional[<type>]".

    Parameters:
    field_type (str): The string from which to extract the type.

    Returns:
    str: The extracted type, or an empty string if no type was found.
    """
    if "optional" not in field_type.lower():
        return field_type
    match = re.search(r"\[(.*?)\]$", field_type)
    return match[1] if match else field_type


def get_field_properties(extra_field):
    """Get the properties of an extra field"""
    field_name = extra_field["name"]
    field_type = extra_field.get("type", "str")
    field_value = extra_field.get("default", "")
    # a required field is a field that does not contain
    # optional in field_type
    # and a field that does not have a default value
    field_required = "optional" not in field_type.lower() and isinstance(field_value, MissingDefault)
    field_value = field_value if not isinstance(field_value, MissingDefault) else None

    if not field_required:
        field_type = extract_type_from_optional(field_type)
    if field_value is not None:
        with contextlib.suppress(Exception):
            field_value = ast.literal_eval(field_value)
    return field_name, field_type, field_value, field_required


def process_type(field_type: str):
    if field_type.startswith(("list", "List")):
        return extract_inner_type(field_type)

    # field_type is a string can be Prompt or Code too
    # so we just need to lower if it is the case
    lowercase_type = field_type.lower()
    if lowercase_type in ["prompt", "code"]:
        return lowercase_type
    return field_type


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
    display_name = field_config.pop("display_name", None)
    if not field_type:
        if "type" in field_config and field_config["type"] is not None:
            field_type = field_config.pop("type")
        elif "field_type" in field_config and field_config["field_type"] is not None:
            field_type = field_config.pop("field_type")
    field_contains_list = "list" in field_type.lower()
    field_type = process_type(field_type)
    field_value = field_config.pop("value", field_value)
    field_advanced = field_config.pop("advanced", False)

    if field_type == "Dict":
        field_type = "dict"

    if field_type == "bool" and field_value is None:
        field_value = False

    if field_type == "SecretStr":
        field_config["password"] = True
        field_config["load_from_db"] = True
        field_config["input_types"] = ["Text"]

    # If options is a list, then it's a dropdown or multiselect
    # If options is None, then it's a list of strings
    is_list = isinstance(field_config.get("options"), list)
    field_config["is_list"] = is_list or field_config.get("list", False) or field_contains_list

    if "name" in field_config:
        logger.warning("The 'name' key in field_config is used to build the object and can't be changed.")
    required = field_config.pop("required", field_required)
    placeholder = field_config.pop("placeholder", "")

    new_field = Input(
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


def add_extra_fields(frontend_node, field_config, function_args):
    """Add extra fields to the frontend node"""
    if not function_args:
        return
    _field_config = field_config.copy()
    function_args_names = [arg["name"] for arg in function_args]
    # If kwargs is in the function_args and not all field_config keys are in function_args
    # then we need to add the extra fields

    for extra_field in function_args:
        if "name" not in extra_field or extra_field["name"] in [
            "self",
            "kwargs",
            "args",
        ]:
            continue

        field_name, field_type, field_value, field_required = get_field_properties(extra_field)
        config = _field_config.pop(field_name, {})
        frontend_node = add_new_custom_field(
            frontend_node,
            field_name,
            field_type,
            field_value,
            field_required,
            config,
        )
    if "kwargs" in function_args_names and not all(key in function_args_names for key in field_config):
        for field_name, field_config in _field_config.copy().items():
            if "name" not in field_config or field_name == "code":
                continue
            config = _field_config.get(field_name, {})
            config = config.model_dump() if isinstance(config, BaseModel) else config
            field_name, field_type, field_value, field_required = get_field_properties(extra_field=config)
            frontend_node = add_new_custom_field(
                frontend_node,
                field_name,
                field_type,
                field_value,
                field_required,
                config,
            )


def get_field_dict(field: Input | dict):
    """Get the field dictionary from a Input or a dict"""
    if isinstance(field, Input):
        return dotdict(field.model_dump(by_alias=True, exclude_none=True))
    return field


def run_build_inputs(
    custom_component: Component,
    user_id: str | UUID | None = None,
):
    """Run the build inputs of a custom component."""
    try:
        return custom_component.build_inputs(user_id=user_id)
        # add_extra_fields(frontend_node, field_config, field_config.values())
    except Exception as exc:
        logger.error(f"Error running build inputs: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def get_component_instance(custom_component: CustomComponent, user_id: str | UUID | None = None):
    try:
        if custom_component._code is None:
            msg = "Code is None"
            raise ValueError(msg)
        if isinstance(custom_component._code, str):
            custom_class = eval_custom_component_code(custom_component._code)
        else:
            msg = "Invalid code type"
            raise ValueError(msg)
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
        return custom_class(_user_id=user_id, _code=custom_component._code)
    except Exception as exc:
        logger.error(f"Error while instantiating custom component: {str(exc)}")
        if hasattr(exc, "detail") and "traceback" in exc.detail:
            logger.error(exc.detail["traceback"])

        raise exc


def run_build_config(
    custom_component: CustomComponent,
    user_id: str | UUID | None = None,
) -> tuple[dict, CustomComponent]:
    """Build the field configuration for a custom component"""

    try:
        if custom_component._code is None:
            msg = "Code is None"
            raise ValueError(msg)
        if isinstance(custom_component._code, str):
            custom_class = eval_custom_component_code(custom_component._code)
        else:
            msg = "Invalid code type"
            raise ValueError(msg)
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
        custom_instance = custom_class(_user_id=user_id)
        build_config: dict = custom_instance.build_config()

        for field_name, field in build_config.copy().items():
            # Allow user to build Input as well
            # as a dict with the same keys as Input
            field_dict = get_field_dict(field)
            # Let's check if "rangeSpec" is a RangeSpec object
            if "rangeSpec" in field_dict and isinstance(field_dict["rangeSpec"], RangeSpec):
                field_dict["rangeSpec"] = field_dict["rangeSpec"].model_dump()
            build_config[field_name] = field_dict

        return build_config, custom_instance

    except Exception as exc:
        logger.error(f"Error while building field config: {str(exc)}")
        if hasattr(exc, "detail") and "traceback" in exc.detail:
            logger.error(exc.detail["traceback"])

        raise exc


def add_code_field(frontend_node: CustomComponentFrontendNode, raw_code):
    code_field = Input(
        dynamic=True,
        required=True,
        placeholder="",
        multiline=True,
        value=raw_code,
        password=False,
        name="code",
        advanced=True,
        field_type="code",
        is_list=False,
    )
    frontend_node.template.add_field(code_field)

    return frontend_node


def build_custom_component_template_from_inputs(
    custom_component: Component | CustomComponent, user_id: str | UUID | None = None
):
    # The List of Inputs fills the role of the build_config and the entrypoint_args
    cc_instance = get_component_instance(custom_component, user_id=user_id)
    field_config = cc_instance.get_template_config(cc_instance)
    frontend_node = ComponentFrontendNode.from_inputs(**field_config)
    frontend_node = add_code_field(frontend_node, custom_component._code)
    # But we now need to calculate the return_type of the methods in the outputs
    for output in frontend_node.outputs:
        if output.types:
            continue
        return_types = cc_instance.get_method_return_type(output.method)
        return_types = [format_type(return_type) for return_type in return_types]
        output.add_types(return_types)
        output.set_selected()
    # Validate that there is not name overlap between inputs and outputs
    frontend_node.validate_component()
    # ! This should be removed when we have a better way to handle this
    frontend_node.set_base_classes_from_outputs()
    reorder_fields(frontend_node, cc_instance._get_field_order())

    return frontend_node.to_dict(keep_name=False), cc_instance


def build_custom_component_template(
    custom_component: CustomComponent,
    user_id: str | UUID | None = None,
) -> tuple[dict[str, Any], CustomComponent | Component]:
    """Build a custom component template"""
    try:
        if not hasattr(custom_component, "template_config"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": ("Please check if you are importing Component correctly."),
                },
            )
        if "inputs" in custom_component.template_config:
            return build_custom_component_template_from_inputs(custom_component, user_id=user_id)
        frontend_node = CustomComponentFrontendNode(**custom_component.template_config)

        field_config, custom_instance = run_build_config(
            custom_component,
            user_id=user_id,
        )

        entrypoint_args = custom_component.get_function_entrypoint_args

        add_extra_fields(frontend_node, field_config, entrypoint_args)

        frontend_node = add_code_field(frontend_node, custom_component._code)

        add_base_classes(frontend_node, custom_component.get_function_entrypoint_return_type)
        add_output_types(frontend_node, custom_component.get_function_entrypoint_return_type)

        reorder_fields(frontend_node, custom_instance._get_field_order())

        return frontend_node.to_dict(keep_name=False), custom_instance
    except Exception as exc:
        if custom_component.ERROR_CODE_NULL:
            logger.error(f"Error building Component: {custom_component.template_config} \n {custom_component.ERROR_CODE_NULL}")
        try:
            logger.error(f"Error building Component: {custom_component.template_config['display_name']} \n {str(exc)}")
        except Exception as e:
            logger.error(f"Error getting display_name: {e}")
        finally:
            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(
                status_code=400,
                detail={
                    "error": (f"Error building Component: {str(exc)}"),
                    "traceback": traceback.format_exc(),
                },
            ) from exc


def create_component_template(component):
    """Create a template for a component."""
    component_code = component["code"]
    component_output_types = component["output_types"]

    component_extractor = Component(_code=component_code)

    component_template, component_instance = build_custom_component_template(component_extractor)
    if not component_template["output_types"] and component_output_types:
        component_template["output_types"] = component_output_types

    return component_template, component_instance


# TODO: add tool_packages?
def build_custom_components(components_paths: list[str]):
    """Build custom components from the specified paths."""
    if not components_paths:
        return {}

    logger.info(f"Building custom components from {components_paths}")
    custom_components_from_file: dict = {}
    processed_paths = set()
    for path in components_paths:
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


async def abuild_custom_components(components_paths: List[str], tool_packages: List[object] = None):
    """Build custom components from the specified paths and tool packages."""
    if not components_paths and not tool_packages:
        return {}

    logger.info(f"Building custom components from {components_paths}")
    custom_components_from_file: dict = {}
    processed_paths = set()

    # Process components from paths
    for path in components_paths:
        path_str = str(path)
        if path_str in processed_paths:
            continue

        custom_component_dict = await abuild_custom_component_list_from_path(path_str)
        if custom_component_dict:
            category = next(iter(custom_component_dict))
            logger.info(f"Loading {len(custom_component_dict[category])} component(s) from category {category}")
            custom_components_from_file = merge_nested_dicts_with_renaming(
                custom_components_from_file, custom_component_dict
            )
        processed_paths.add(path_str)

    # Process components from tool packages (which are now module objects)
    if tool_packages:
        tool_components = build_tool_components(tool_packages)  # Now correctly handling module objects
        custom_components_from_file = merge_nested_dicts_with_renaming(
            custom_components_from_file, tool_components
        )

    return custom_components_from_file


def build_tool_components(tool_packages: List[object]) -> Dict:
    """Build components from classes extending ToolInterface in the specified modules."""
    tool_components = {}
    processed_modules = set()

    # Iterate over the provided packages (which are module objects)
    for package in tool_packages:
        try:
            logger.info(f"Processing package {package.__name__}")
            # Recursively inspect the package and its submodules
            for submodule in _iter_submodules(package, processed_modules):
                _process_module(submodule, tool_components, processed_modules)
        except Exception as e:
            logger.error(f"Error processing package {package.__name__}: {e}")
            trace = traceback.format_exc()
            logger.error(trace)

    components_list = []
    category = 'converted_tools'

    for name, cls in tool_components[category].items():
        # Extract the tool class details for the imports
        #tool_cls = cls.tool_cls
        #tool_module = tool_cls.__module__
        #tool_class_name = tool_cls.__name__

        # Generate the import statements
        #imports = (
        #    "import inspect\n"
        #    "import asyncio\n"
        #    "from typing import Type, Dict, Any, Union\n"
        #    "from pydantic import BaseModel, Field as PydanticField, Undefined as PydanticUndefined\n"
        #    "from langflow.inputs import (\n"
        #    "    StrInput, IntInput, FloatInput, BoolInput, DictInput, DataInput,\n"
        #    "    DefaultPromptField, DropdownInput, MultiselectInput, FileInput,\n"
        #    "    HandleInput, MultilineInput, MultilineSecretInput, NestedDictInput,\n"
        #    "    PromptInput, CodeInput, SecretStrInput, MessageTextInput, MessageInput,\n"
        #    "    TableInput, LinkInput\n"
        #    ")\n"
        #    "from langflow.outputs import Output\n"
        #    "from langflow.component import Component\n"
        #    f"from {tool_module} import {tool_class_name}\n"
        #)

        # Define the component class name
        #component_class_name = f"{tool_cls.__name__}Component"

        # Begin constructing the class definition
        #class_code = f"{imports}\n\nclass {component_class_name}(Component):\n"

        #members = inspect.getmembers(cls)
        # Iterate through the members of cls and generate attributes and methods
        #for member_name, member_value in members:
        #    # Skip private members and properties
        #    if not member_name.startswith('_') and not isinstance(member_value, property):
        #        if not callable(member_value):
        #            # Add an attribute definition
        #            class_code += f"    {member_name} = {repr(member_value)}\n"
        #        else:
        #            # Add a method definition
        #            class_code += f"\n    def {member_name}(self, *args, **kwargs):\n"
        #            if isinstance(member_value, type(lambda: None)):
        #                # Use the original code of the function if available
        #                func_code = inspect.getsource(member_value).splitlines()
        #                func_body = "\n".join([f"        {line.strip()}" for line in func_code[1:]])
        #                class_code += f"{func_body}\n"
        #            else:
        #                class_code += f"        return cls.{member_name}(*args, **kwargs)\n"

        #members.index("outputs")

        ## Ensure the class has some content, otherwise add a `pass`
        #if class_code.strip().endswith(f"class {component_class_name}(Component):"):
        #    class_code += "    pass\n"

        component_info = {
            "name": f"{name}Component",
            # TODO: fix this? Looks like it's almost always [] sometimes [Data] or [str]
            "output_types": [],
            "file": "",
            "code": cls,
            "error": "",
        }
        # Iterate over the provided packages (which are module objects)
        try:
            component_tuple = (*build_component(component_info), component_info)
            components_list.append(component_tuple)
        except Exception as e:
            logger.error(f"Error while building component {name}Component: {e}")
            trace = traceback.format_exc()
            logger.error(trace)
            continue
    components_dict = {
        "name": category,
        "components": components_list,
    }
    built_menu_items = build_menu_items(components_dict)
    menu = { category: built_menu_items }
    return menu

def _process_module(module, tool_components, processed_modules):
    """Process an individual module for ToolInterface subclasses."""
    if module in processed_modules:
        return
    processed_modules.add(module)

    logger.info(f"Inspecting module {module.__name__}")

    # Inspect the members of the module
    for name, obj in inspect.getmembers(module):
        if inspect.ismodule(obj):
            # Recursively inspect submodules
            _process_module(obj, tool_components, processed_modules)
        elif inspect.isclass(obj) and issubclass(obj, ToolInterface) and obj != ToolInterface:
            logger.info(f"Found ToolInterface class: {obj.__name__}")

            component = tool_interface_to_component(obj)
            category = getattr(obj, 'category', 'converted_tools')

            # Organize components by category
            if category not in tool_components:
                tool_components[category] = {}
            tool_components[category][obj.__name__] = component

def _iter_submodules(package, processed_modules=None):
    """Recursively iterate over all submodules in a package."""
    if processed_modules is None:
        processed_modules = set()
    if package in processed_modules:
        return
    yield package  # Start with the root package
    processed_modules.add(package)
    if hasattr(package, '__path__'):  # If the package has submodules
        for _, submodule_name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
            try:
                submodule = importlib.import_module(submodule_name)
                if submodule not in processed_modules:
                    yield submodule
                    yield from _iter_submodules(submodule, processed_modules)
            except Exception as e:
                logger.error(f"Error importing submodule {submodule_name}: {e}")


def update_field_dict(
    custom_component_instance: "CustomComponent",
    field_dict: dict,
    build_config: dict,
    update_field: str | None = None,
    update_field_value: Any | None = None,
    call: bool = False,
):
    """Update the field dictionary by calling options() or value() if they are callable"""
    if (
        ("real_time_refresh" in field_dict or "refresh_button" in field_dict)
        and any(
            (
                field_dict.get("real_time_refresh", False),
                field_dict.get("refresh_button", False),
            )
        )
        and call
    ):
        try:
            dd_build_config = dotdict(build_config)
            custom_component_instance.update_build_config(
                build_config=dd_build_config,
                field_value=update_field,
                field_name=update_field_value,
            )
            build_config = dd_build_config
        except Exception as exc:
            logger.error(f"Error while running update_build_config: {str(exc)}")
            msg = f"Error while running update_build_config: {str(exc)}"
            raise UpdateBuildConfigError(msg) from exc

    return build_config


def sanitize_field_config(field_config: dict | Input):
    # If any of the already existing keys are in field_config, remove them
    field_dict = field_config.to_dict() if isinstance(field_config, Input) else field_config
    for key in [
        "name",
        "field_type",
        "value",
        "required",
        "placeholder",
        "display_name",
        "advanced",
        "show",
    ]:
        field_dict.pop(key, None)

    # Remove field_type and type because they were extracted already
    field_dict.pop("field_type", None)
    field_dict.pop("type", None)

    return field_dict


def build_component(component):
    """Build a single component."""
    component_template, component_instance = create_component_template(component)
    component_name = get_instance_name(component_instance)
    return component_name, component_template


def get_function(code):
    """Get the function"""
    function_name = validate.extract_function_name(code)

    return validate.create_function(code, function_name)


def get_instance_name(instance):
    name = instance.__class__.__name__
    if hasattr(instance, "name") and instance.name:
        name = instance.name
    return name
