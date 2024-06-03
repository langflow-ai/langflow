import inspect
import json
import os
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Type

import orjson
import yaml
from loguru import logger
from pydantic import BaseModel

from langflow.custom.eval import eval_custom_component_code
from langflow.schema.schema import Record

if TYPE_CHECKING:
    from langflow.custom import Component, CustomComponent
    from langflow.graph.vertex.base import Vertex


async def instantiate_class(
    vertex: "Vertex",
    fallback_to_env_vars,
    user_id=None,
) -> Any:
    """Instantiate class from module type and key, and params"""

    vertex_type = vertex.vertex_type
    base_type = vertex.base_type
    params = vertex.params
    params = convert_params_to_sets(params)
    params = convert_kwargs(params)
    logger.debug(f"Instantiating {vertex_type} of type {base_type}")

    if not base_type:
        raise ValueError("No base type provided for vertex")

    params_copy = params.copy()
    # Remove code from params
    class_object: Type["CustomComponent"] = eval_custom_component_code(params_copy.pop("code"))
    custom_component: "CustomComponent" = class_object(
        user_id=user_id,
        parameters=params_copy,
        vertex=vertex,
        selected_output_type=vertex.selected_output_type,
    )
    params_copy = update_params_with_load_from_db_fields(
        custom_component, params_copy, vertex.load_from_db_fields, fallback_to_env_vars
    )
    if base_type == "custom_components":
        return await build_custom_component(params=params_copy, custom_component=custom_component)
    elif base_type == "component":
        return await build_component(params=params_copy, custom_component=custom_component, vertex=vertex)
    else:
        raise ValueError(f"Base type {base_type} not found.")


def convert_params_to_sets(params):
    """Convert certain params to sets"""
    if "allowed_special" in params:
        params["allowed_special"] = set(params["allowed_special"])
    if "disallowed_special" in params:
        params["disallowed_special"] = set(params["disallowed_special"])
    return params


def convert_kwargs(params):
    # if *kwargs are passed as a string, convert to dict
    # first find any key that has kwargs or config in it
    kwargs_keys = [key for key in params.keys() if "kwargs" in key or "config" in key]
    for key in kwargs_keys:
        if isinstance(params[key], str):
            try:
                params[key] = orjson.loads(params[key])
            except json.JSONDecodeError:
                # if the string is not a valid json string, we will
                # remove the key from the params
                params.pop(key, None)
    return params


def update_params_with_load_from_db_fields(
    custom_component: "CustomComponent", params, load_from_db_fields, fallback_to_env_vars=False
):
    # For each field in load_from_db_fields, we will check if it's in the params
    # and if it is, we will get the value from the custom_component.keys(name)
    # and update the params with the value
    for field in load_from_db_fields:
        if field in params:
            try:
                key = None
                try:
                    key = custom_component.variables(params[field])
                except ValueError as e:
                    # check if "User id is not set" is in the error message
                    if "User id is not set" in str(e) and not fallback_to_env_vars:
                        raise e
                    logger.debug(str(e))
                if fallback_to_env_vars and key is None:
                    var = os.getenv(params[field])
                    if var is None:
                        raise ValueError(f"Environment variable {params[field]} is not set.")
                    key = var
                    logger.info(f"Using environment variable {params[field]} for {field}")
                if key is None:
                    logger.warning(f"Could not get value for {field}. Setting it to None.")
                params[field] = key

            except Exception as exc:
                logger.error(f"Failed to get value for {field} from custom component. Setting it to None. Error: {exc}")

                params[field] = None

    return params


async def build_component(
    params: dict,
    custom_component: "Component",
    vertex: "Vertex",
):
    # Now set the params as attributes of the custom_component
    custom_component.set_attributes(params)

    build_result = {}
    if hasattr(custom_component, "outputs"):
        for output in custom_component.outputs:
            # Build the output if it's connected to some other vertex
            # or if it's not connected to any vertex
            if not vertex.outgoing_edges or output.name in vertex.edges_source_names:
                method: Callable | Awaitable = getattr(custom_component, output.method)
                result = method()
                # If the method is asynchronous, we need to await it
                if inspect.iscoroutinefunction(method):
                    result = await result
                build_result[output.name] = result
    custom_repr = custom_component.custom_repr()

    # ! Temporary REPR
    # Since all are dict, yaml.dump them
    if isinstance(build_result, dict):
        _build_result = {
            key: value.model_dump() if isinstance(value, BaseModel) else value for key, value in build_result.items()
        }
        custom_repr = yaml.dump(_build_result)

    if custom_repr is None and isinstance(build_result, (dict, Record, str)):
        custom_repr = build_result
    if not isinstance(custom_repr, str):
        custom_repr = str(custom_repr)
    return custom_component, build_result, {"repr": custom_repr}


async def build_custom_component(params: dict, custom_component: "CustomComponent"):
    if "retriever" in params and hasattr(params["retriever"], "as_retriever"):
        params["retriever"] = params["retriever"].as_retriever()

    # Determine if the build method is asynchronous
    is_async = inspect.iscoroutinefunction(custom_component.build)

    # New feature: the component has a list of outputs and we have
    # to check the vertex.edges to see which is connected (coulb be multiple)
    # and then we'll get the output which has the name of the method we should call.
    # the methods don't require any params because they are already set in the custom_component
    # so we can just call them

    if is_async:
        # Await the build method directly if it's async
        build_result = await custom_component.build(**params)
    else:
        # Call the build method directly if it's sync
        build_result = custom_component.build(**params)
    custom_repr = custom_component.custom_repr()
    if custom_repr is None and isinstance(build_result, (dict, Record, str)):
        custom_repr = build_result
    if not isinstance(custom_repr, str):
        custom_repr = str(custom_repr)
    return custom_component, build_result, {"repr": custom_repr}
