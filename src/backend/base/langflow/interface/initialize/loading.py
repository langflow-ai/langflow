import inspect
import json
import os
from typing import TYPE_CHECKING, Any, Type

import orjson
from loguru import logger

from langflow.custom.eval import eval_custom_component_code
from langflow.graph.utils import get_artifact_type, post_process_raw
from langflow.schema import Record

if TYPE_CHECKING:
    from langflow.custom import CustomComponent
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
    if base_type == "custom_components":
        return await instantiate_custom_component(params, user_id, vertex, fallback_to_env_vars=fallback_to_env_vars)
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
                    key = custom_component.variables(params[field], field)
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

            except TypeError as exc:
                raise exc

            except Exception as exc:
                logger.error(f"Failed to get value for {field} from custom component. Setting it to None. Error: {exc}")

                params[field] = None

    return params


async def instantiate_custom_component(params, user_id, vertex, fallback_to_env_vars: bool = False):
    params_copy = params.copy()
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

    if "retriever" in params_copy and hasattr(params_copy["retriever"], "as_retriever"):
        params_copy["retriever"] = params_copy["retriever"].as_retriever()

    # Determine if the build method is asynchronous
    is_async = inspect.iscoroutinefunction(custom_component.build)

    if is_async:
        # Await the build method directly if it's async
        build_result = await custom_component.build(**params_copy)
    else:
        # Call the build method directly if it's sync
        build_result = custom_component.build(**params_copy)
    custom_repr = custom_component.custom_repr()
    if custom_repr is None and isinstance(build_result, (dict, Record, str)):
        custom_repr = build_result
    if not isinstance(custom_repr, str):
        custom_repr = str(custom_repr)
    raw = custom_component.repr_value
    if hasattr(raw, "data") and raw is not None:
        raw = raw.data

    elif hasattr(raw, "model_dump") and raw is not None:
        raw = raw.model_dump()

    artifact_type = get_artifact_type(custom_component, build_result)
    raw = post_process_raw(raw, artifact_type)
    artifact = {"repr": custom_repr, "raw": raw, "type": artifact_type}
    return custom_component, build_result, artifact
