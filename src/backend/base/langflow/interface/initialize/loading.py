import inspect
import os
import warnings
from typing import TYPE_CHECKING, Any, Type

import orjson
from loguru import logger
from pydantic import PydanticDeprecatedSince20

from langflow.custom import Component, CustomComponent
from langflow.custom.eval import eval_custom_component_code
from langflow.schema import Data
from langflow.schema.artifact import get_artifact_type, post_process_raw
from langflow.services.deps import get_tracing_service

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex
    from langflow.services.tracing.service import TracingService


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

    custom_component, build_results, artifacts = await build_component_and_get_results(
        params=params,
        vertex=vertex,
        user_id=user_id,
        tracing_service=get_tracing_service(),
        fallback_to_env_vars=fallback_to_env_vars,
        base_type=base_type,
    )
    return custom_component, build_results, artifacts


async def build_component_and_get_results(
    params: dict,
    vertex: "Vertex",
    user_id: str,
    tracing_service: "TracingService",
    fallback_to_env_vars: bool = False,
    base_type: str = "component",
):
    params_copy = params.copy()
    # Remove code from params
    class_object: Type["CustomComponent" | "Component"] = eval_custom_component_code(params_copy.pop("code"))
    custom_component: "CustomComponent" | "Component" = class_object.initialize(
        user_id=user_id,
        parameters=params_copy,
        vertex=vertex,
        tracing_service=tracing_service,
    )
    params_copy = update_params_with_load_from_db_fields(
        custom_component, params_copy, vertex.load_from_db_fields, fallback_to_env_vars
    )
    custom_component.set_parameters(params_copy)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)
        if base_type == "custom_components" and isinstance(custom_component, CustomComponent):
            return await build_custom_component(params=params_copy, custom_component=custom_component)
        elif base_type == "component" and isinstance(custom_component, Component):
            return await build_component(custom_component=custom_component)
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
    # Loop through items to avoid repeated lookups
    items_to_remove = []
    for key, value in params.items():
        if "kwargs" in key or "config" in key:
            if isinstance(value, str):
                try:
                    params[key] = orjson.loads(value)
                except orjson.JSONDecodeError:
                    items_to_remove.append(key)

    # Remove invalid keys outside the loop to avoid modifying dict during iteration
    for key in items_to_remove:
        params.pop(key, None)

    return params


def update_params_with_load_from_db_fields(
    custom_component: "CustomComponent",
    params,
    load_from_db_fields,
    fallback_to_env_vars=False,
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


async def build_component(
    custom_component: "Component",
):
    # Now set the params as attributes of the custom_component
    build_results, artifacts = await custom_component.build_results()

    return custom_component, build_results, artifacts


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
    if custom_repr is None and isinstance(build_result, (dict, Data, str)):
        custom_repr = build_result
    if not isinstance(custom_repr, str):
        custom_repr = str(custom_repr)
    raw = custom_component.repr_value
    if hasattr(raw, "data") and raw is not None:
        raw = raw.data

    elif hasattr(raw, "model_dump") and raw is not None:
        raw = raw.model_dump()
    if raw is None and isinstance(build_result, (dict, Data, str)):
        raw = build_result.data if isinstance(build_result, Data) else build_result

    artifact_type = get_artifact_type(custom_component.repr_value or raw, build_result)
    raw = post_process_raw(raw, artifact_type)
    artifact = {"repr": custom_repr, "raw": raw, "type": artifact_type}

    if custom_component.vertex is not None:
        custom_component._artifacts = {custom_component.vertex.outputs[0].get("name"): artifact}
        custom_component._results = {custom_component.vertex.outputs[0].get("name"): build_result}
        return custom_component, build_result, artifact

    raise ValueError("Custom component does not have a vertex")
