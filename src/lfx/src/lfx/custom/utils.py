# mypy: ignore-errors
import ast
import asyncio
import contextlib
import hashlib
import inspect
import re
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langflow.field_typing.range_spec import RangeSpec
from langflow.schema.dotdict import dotdict
from langflow.template.field.base import Input
from langflow.template.frontend_node.custom_components import ComponentFrontendNode, CustomComponentFrontendNode
from langflow.type_extraction.type_extraction import extract_inner_type
from loguru import logger
from pydantic import BaseModel

from lfx.custom.custom_component.component import Component
from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.custom.directory_reader.utils import (
    abuild_custom_component_list_from_path,
    build_custom_component_list_from_path,
    merge_nested_dicts_with_renaming,
)
from lfx.custom.eval import eval_custom_component_code
from lfx.custom.schema import MissingDefault
from lfx.utils import format_type, get_base_classes, validate


def _generate_code_hash(source_code: str, modname: str, class_name: str) -> str:
    """Generate a hash of the component source code.

    Args:
        source_code: The source code string
        modname: The module name for context
        class_name: The class name for context

    Returns:
        SHA256 hash of the source code

    Raises:
        ValueError: If source_code is empty or None
        UnicodeEncodeError: If source_code cannot be encoded
        TypeError: If source_code is not a string
    """
    if not source_code:
        msg = f"Empty source code for {class_name} in {modname}"
        raise ValueError(msg)

    # Generate SHA256 hash of the source code
    return hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:12]  # First 12 chars for brevity


class UpdateBuildConfigError(Exception):
    pass


def add_output_types(frontend_node: CustomComponentFrontendNode, return_types: list[str]) -> None:
    """Add output types to the frontend node."""
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
            return_type_ = "Text"
        elif hasattr(return_type, "__name__"):
            return_type_ = return_type.__name__
        elif hasattr(return_type, "__class__"):
            return_type_ = return_type.__class__.__name__
        else:
            return_type_ = str(return_type)

        frontend_node.add_output_type(return_type_)


def reorder_fields(frontend_node: CustomComponentFrontendNode, field_order: list[str]) -> None:
    """Reorder fields in the frontend node based on the specified field_order."""
    if not field_order:
        return

    # Create a dictionary for O(1) lookup time.
    field_dict = {field.name: field for field in frontend_node.template.fields}
    reordered_fields = [field_dict[name] for name in field_order if name in field_dict]
    # Add any fields that are not in the field_order list
    reordered_fields.extend(field for field in frontend_node.template.fields if field.name not in field_order)
    frontend_node.template.fields = reordered_fields
    frontend_node.field_order = field_order


def add_base_classes(frontend_node: CustomComponentFrontendNode, return_types: list[str]) -> None:
    """Add base classes to the frontend node."""
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
    """Extract the type from a string formatted as "Optional[<type>]".

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
    """Get the properties of an extra field."""
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
    if lowercase_type in {"prompt", "code"}:
        return lowercase_type
    return field_type


def add_new_custom_field(
    *,
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


def add_extra_fields(frontend_node, field_config, function_args) -> None:
    """Add extra fields to the frontend node."""
    if not function_args:
        return
    field_config_ = field_config.copy()
    function_args_names = [arg["name"] for arg in function_args]
    # If kwargs is in the function_args and not all field_config keys are in function_args
    # then we need to add the extra fields

    for extra_field in function_args:
        if "name" not in extra_field or extra_field["name"] in {
            "self",
            "kwargs",
            "args",
        }:
            continue

        field_name, field_type, field_value, field_required = get_field_properties(extra_field)
        config = field_config_.pop(field_name, {})
        frontend_node = add_new_custom_field(
            frontend_node=frontend_node,
            field_name=field_name,
            field_type=field_type,
            field_value=field_value,
            field_required=field_required,
            field_config=config,
        )
    if "kwargs" in function_args_names and not all(key in function_args_names for key in field_config):
        for field_name, config in field_config_.items():
            if "name" not in config or field_name == "code":
                continue
            config_ = config.model_dump() if isinstance(config, BaseModel) else config
            field_name_, field_type, field_value, field_required = get_field_properties(extra_field=config_)
            frontend_node = add_new_custom_field(
                frontend_node=frontend_node,
                field_name=field_name_,
                field_type=field_type,
                field_value=field_value,
                field_required=field_required,
                field_config=config_,
            )


def get_field_dict(field: Input | dict):
    """Get the field dictionary from a Input or a dict."""
    if isinstance(field, Input):
        return dotdict(field.model_dump(by_alias=True, exclude_none=True))
    return field


def run_build_inputs(
    custom_component: Component,
):
    """Run the build inputs of a custom component."""
    try:
        return custom_component.build_inputs()
        # add_extra_fields(frontend_node, field_config, field_config.values())
    except Exception as exc:
        logger.exception("Error running build inputs")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def get_component_instance(custom_component: CustomComponent | Component, user_id: str | UUID | None = None):
    """Returns an instance of a custom component, evaluating its code if necessary.

    If the input is already an instance of `Component` or `CustomComponent`, it is returned directly.
    Otherwise, the function evaluates the component's code to create and return an instance. Raises an
    HTTP 400 error if the code is missing, invalid, or instantiation fails.
    """
    # Fast path: avoid repeated str comparisons

    code = custom_component._code
    if not isinstance(code, str):
        # Only two failure cases: None, or other non-str
        error = "Code is None" if code is None else "Invalid code type"
        msg = f"Invalid type conversion: {error}. Please check your code and try again."
        logger.error(msg)
        raise HTTPException(status_code=400, detail={"error": msg})

    # Only now, try to process expensive exception/log traceback only *if needed*
    try:
        custom_class = eval_custom_component_code(code)
    except Exception as exc:
        # Only generate traceback if an error occurs (save time on success)
        tb = traceback.format_exc()
        logger.error("Error while evaluating custom component code\n%s", tb)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid type conversion. Please check your code and try again.",
                "traceback": tb,
            },
        ) from exc

    try:
        return custom_class(_user_id=user_id, _code=code)
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("Error while instantiating custom component\n%s", tb)
        # Only log inner traceback if present in 'detail'
        detail_tb = getattr(exc, "detail", {}).get("traceback", None)
        if detail_tb is not None:
            logger.error(detail_tb)
        raise


def is_a_preimported_component(custom_component: CustomComponent):
    """Check if the component is a preimported component."""
    klass = type(custom_component)
    # This avoids double type lookups, and may speed up the common-case short-circuit
    return issubclass(klass, Component) and klass is not Component


def run_build_config(
    custom_component: CustomComponent,
    user_id: str | UUID | None = None,
) -> tuple[dict, CustomComponent]:
    """Builds the field configuration dictionary for a custom component.

    If the input is an instance of a subclass of Component (excluding Component itself), returns its
    build configuration and the instance. Otherwise, evaluates the component's code to create an instance,
    calls its build_config method, and processes any RangeSpec objects in the configuration. Raises an
    HTTP 400 error if the code is missing or invalid, or if instantiation or configuration building fails.

    Returns:
        A tuple containing the field configuration dictionary and the component instance.
    """
    # Check if the instance's class is a subclass of Component (but not Component itself)
    # If we have a Component that is a subclass of Component, that means
    # we have imported it
    # If not, it means the component was loaded through LANGFLOW_COMPONENTS_PATH
    # and loaded from a file
    if is_a_preimported_component(custom_component):
        return custom_component.build_config(), custom_component

    if custom_component._code is None:
        error = "Code is None"
    elif not isinstance(custom_component._code, str):
        error = "Invalid code type"
    else:
        try:
            custom_class = eval_custom_component_code(custom_component._code)
        except Exception as exc:
            logger.exception("Error while evaluating custom component code")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": ("Invalid type conversion. Please check your code and try again."),
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

        except Exception as exc:
            logger.exception("Error while building field config")
            if hasattr(exc, "detail") and "traceback" in exc.detail:
                logger.error(exc.detail["traceback"])
            raise
        return build_config, custom_instance

    msg = f"Invalid type conversion: {error}. Please check your code and try again."
    logger.error(msg)
    raise HTTPException(
        status_code=400,
        detail={"error": msg},
    )


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


def add_code_field_to_build_config(build_config: dict, raw_code: str):
    build_config["code"] = Input(
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
    ).model_dump()
    return build_config


def build_custom_component_template_from_inputs(
    custom_component: Component | CustomComponent, user_id: str | UUID | None = None, module_name: str | None = None
):
    # The List of Inputs fills the role of the build_config and the entrypoint_args
    """Builds a frontend node template from a custom component using its input-based configuration.

    This function generates a frontend node template by extracting input fields from the component,
    adding the code field, determining output types from method return types, validating the component,
    setting base classes, and reordering fields. Returns the frontend node as a dictionary along with
    the component instance.

    Returns:
        A tuple containing the frontend node dictionary and the component instance.
    """
    ctype_name = custom_component.__class__.__name__
    if ctype_name in _COMPONENT_TYPE_NAMES:
        cc_instance = get_component_instance(custom_component, user_id=user_id)

        field_config = cc_instance.get_template_config(cc_instance)
        frontend_node = ComponentFrontendNode.from_inputs(**field_config)

    else:
        frontend_node = ComponentFrontendNode.from_inputs(**custom_component.template_config)
        cc_instance = custom_component
    frontend_node = add_code_field(frontend_node, custom_component._code)
    # But we now need to calculate the return_type of the methods in the outputs
    for output in frontend_node.outputs:
        if output.types:
            continue
        return_types = cc_instance.get_method_return_type(output.method)
        return_types = [format_type(return_type) for return_type in return_types]
        output.add_types(return_types)

    # Validate that there is not name overlap between inputs and outputs
    frontend_node.validate_component()
    # ! This should be removed when we have a better way to handle this
    frontend_node.set_base_classes_from_outputs()
    reorder_fields(frontend_node, cc_instance._get_field_order())
    if module_name:
        frontend_node.metadata["module"] = module_name

        # Generate code hash for cache invalidation and debugging
        code_hash = _generate_code_hash(custom_component._code, module_name, ctype_name)
        if code_hash:
            frontend_node.metadata["code_hash"] = code_hash

    return frontend_node.to_dict(keep_name=False), cc_instance


def build_custom_component_template(
    custom_component: CustomComponent,
    user_id: str | UUID | None = None,
    module_name: str | None = None,
) -> tuple[dict[str, Any], CustomComponent | Component]:
    """Builds a frontend node template and instance for a custom component.

    If the component uses input-based configuration, delegates to the appropriate builder. Otherwise,
    constructs a frontend node from the component's template configuration, adds extra fields, code,
    base classes, and output types, reorders fields, and returns the resulting template dictionary
    along with the component instance.

    Raises:
        HTTPException: If the component is missing required attributes or if any error occurs during
                      template construction.
    """
    try:
        has_template_config = hasattr(custom_component, "template_config")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": (f"Error building Component: {exc}"),
                "traceback": traceback.format_exc(),
            },
        ) from exc
    if not has_template_config:
        raise HTTPException(
            status_code=400,
            detail={
                "error": ("Error building Component. Please check if you are importing Component correctly."),
            },
        )
    try:
        if "inputs" in custom_component.template_config:
            return build_custom_component_template_from_inputs(
                custom_component, user_id=user_id, module_name=module_name
            )
        frontend_node = CustomComponentFrontendNode(**custom_component.template_config)

        field_config, custom_instance = run_build_config(
            custom_component,
            user_id=user_id,
        )

        entrypoint_args = custom_component.get_function_entrypoint_args

        add_extra_fields(frontend_node, field_config, entrypoint_args)

        frontend_node = add_code_field(frontend_node, custom_component._code)

        add_base_classes(frontend_node, custom_component._get_function_entrypoint_return_type)
        add_output_types(frontend_node, custom_component._get_function_entrypoint_return_type)

        reorder_fields(frontend_node, custom_instance._get_field_order())

        if module_name:
            frontend_node.metadata["module"] = module_name

            # Generate code hash for cache invalidation and debugging
            code_hash = _generate_code_hash(custom_component._code, module_name, custom_component.__class__.__name__)
            if code_hash:
                frontend_node.metadata["code_hash"] = code_hash

        return frontend_node.to_dict(keep_name=False), custom_instance
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=400,
            detail={
                "error": (f"Error building Component: {exc}"),
                "traceback": traceback.format_exc(),
            },
        ) from exc


def create_component_template(
    component: dict | None = None,
    component_extractor: Component | CustomComponent | None = None,
    module_name: str | None = None,
):
    """Creates a component template and instance from either a component dictionary or an existing component extractor.

    If a component dictionary is provided, a new Component instance is created from its code. If a component
    extractor is provided, it is used directly. The function returns the generated template and the component
    instance. Output types are set on the template if missing.
    """
    component_output_types = []
    if component_extractor is None and component is not None:
        component_code = component["code"]
        component_output_types = component["output_types"]

        component_extractor = Component(_code=component_code)

    component_template, component_instance = build_custom_component_template(
        component_extractor, module_name=module_name
    )
    if not component_template["output_types"] and component_output_types:
        component_template["output_types"] = component_output_types

    return component_template, component_instance


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
            logger.debug(f"Loading {len(custom_component_dict[category])} component(s) from category {category}")
            custom_components_from_file = merge_nested_dicts_with_renaming(
                custom_components_from_file, custom_component_dict
            )
        processed_paths.add(path_str)

    return custom_components_from_file


async def abuild_custom_components(components_paths: list[str]):
    """Build custom components from the specified paths."""
    if not components_paths:
        return {}

    logger.debug(f"Building custom components from {components_paths}")
    custom_components_from_file: dict = {}
    processed_paths = set()
    for path in components_paths:
        path_str = str(path)
        if path_str in processed_paths:
            continue

        custom_component_dict = await abuild_custom_component_list_from_path(path_str)
        if custom_component_dict:
            category = next(iter(custom_component_dict))
            logger.debug(f"Loading {len(custom_component_dict[category])} component(s) from category {category}")
            custom_components_from_file = merge_nested_dicts_with_renaming(
                custom_components_from_file, custom_component_dict
            )
        processed_paths.add(path_str)

    return custom_components_from_file


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
    """Get the function."""
    function_name = validate.extract_function_name(code)

    return validate.create_function(code, function_name)


def get_instance_name(instance):
    name = instance.__class__.__name__
    if hasattr(instance, "name") and instance.name:
        name = instance.name
    return name


async def update_component_build_config(
    component: CustomComponent,
    build_config: dotdict,
    field_value: Any,
    field_name: str | None = None,
):
    if inspect.iscoroutinefunction(component.update_build_config):
        return await component.update_build_config(build_config, field_value, field_name)
    return await asyncio.to_thread(component.update_build_config, build_config, field_value, field_name)


async def get_all_types_dict(components_paths: list[str]):
    """Get all types dictionary with full component loading."""
    # This is the async version of the existing function
    return await abuild_custom_components(components_paths=components_paths)


async def get_single_component_dict(component_type: str, component_name: str, components_paths: list[str]):
    """Get a single component dictionary."""
    # For example, if components are loaded by importing Python modules:
    for base_path in components_paths:
        module_path = Path(base_path) / component_type / f"{component_name}.py"
        if module_path.exists():
            # Try to import the module
            module_name = f"langflow.components.{component_type}.{component_name}"
            try:
                # This is a simplified example - actual implementation may vary
                import importlib.util

                spec = importlib.util.spec_from_file_location(module_name, module_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "template"):
                        return module.template
            except ImportError as e:
                logger.error(f"Import error loading component {module_path}: {e!s}")
            except AttributeError as e:
                logger.error(f"Attribute error loading component {module_path}: {e!s}")
            except ValueError as e:
                logger.error(f"Value error loading component {module_path}: {e!s}")
            except (KeyError, IndexError) as e:
                logger.error(f"Data structure error loading component {module_path}: {e!s}")
            except RuntimeError as e:
                logger.error(f"Runtime error loading component {module_path}: {e!s}")
                logger.debug("Full traceback for runtime error", exc_info=True)
            except OSError as e:
                logger.error(f"OS error loading component {module_path}: {e!s}")

    # If we get here, the component wasn't found or couldn't be loaded
    return None


async def load_custom_component(component_name: str, components_paths: list[str]):
    """Load a custom component by name.

    Args:
        component_name: Name of the component to load
        components_paths: List of paths to search for components
    """
    from langflow.interface.custom_component import get_custom_component_from_name

    try:
        # First try to get the component from the registered components
        component_class = get_custom_component_from_name(component_name)
        if component_class:
            # Define the function locally if it's not imported
            def get_custom_component_template(component_cls):
                """Get template for a custom component class."""
                # This is a simplified implementation - adjust as needed
                if hasattr(component_cls, "get_template"):
                    return component_cls.get_template()
                if hasattr(component_cls, "template"):
                    return component_cls.template
                return None

            return get_custom_component_template(component_class)

        # If not found in registered components, search in the provided paths
        for path in components_paths:
            # Try to find the component in different category directories
            base_path = Path(path)
            if base_path.exists() and base_path.is_dir():
                # Search for the component in all subdirectories
                for category_dir in base_path.iterdir():
                    if category_dir.is_dir():
                        component_file = category_dir / f"{component_name}.py"
                        if component_file.exists():
                            # Try to import the module
                            module_name = f"langflow.components.{category_dir.name}.{component_name}"
                            try:
                                import importlib.util

                                spec = importlib.util.spec_from_file_location(module_name, component_file)
                                if spec and spec.loader:
                                    module = importlib.util.module_from_spec(spec)
                                    spec.loader.exec_module(module)
                                    if hasattr(module, "template"):
                                        return module.template
                                    if hasattr(module, "get_template"):
                                        return module.get_template()
                            except ImportError as e:
                                logger.error(f"Import error loading component {component_file}: {e!s}")
                                logger.debug("Import error traceback", exc_info=True)
                            except AttributeError as e:
                                logger.error(f"Attribute error loading component {component_file}: {e!s}")
                                logger.debug("Attribute error traceback", exc_info=True)
                            except (ValueError, TypeError) as e:
                                logger.error(f"Value/Type error loading component {component_file}: {e!s}")
                                logger.debug("Value/Type error traceback", exc_info=True)
                            except (KeyError, IndexError) as e:
                                logger.error(f"Data structure error loading component {component_file}: {e!s}")
                                logger.debug("Data structure error traceback", exc_info=True)
                            except RuntimeError as e:
                                logger.error(f"Runtime error loading component {component_file}: {e!s}")
                                logger.debug("Runtime error traceback", exc_info=True)
                            except OSError as e:
                                logger.error(f"OS error loading component {component_file}: {e!s}")
                                logger.debug("OS error traceback", exc_info=True)

    except ImportError as e:
        logger.error(f"Import error loading custom component {component_name}: {e!s}")
        return None
    except AttributeError as e:
        logger.error(f"Attribute error loading custom component {component_name}: {e!s}")
        return None
    except ValueError as e:
        logger.error(f"Value error loading custom component {component_name}: {e!s}")
        return None
    except (KeyError, IndexError) as e:
        logger.error(f"Data structure error loading custom component {component_name}: {e!s}")
        return None
    except RuntimeError as e:
        logger.error(f"Runtime error loading custom component {component_name}: {e!s}")
        logger.debug("Full traceback for runtime error", exc_info=True)
        return None

    # If we get here, the component wasn't found in any of the paths
    logger.warning(f"Component {component_name} not found in any of the provided paths")
    return None


_COMPONENT_TYPE_NAMES = {"Component", "CustomComponent"}
