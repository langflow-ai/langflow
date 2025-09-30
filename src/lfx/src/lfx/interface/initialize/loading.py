from __future__ import annotations

import inspect
import os
import warnings
from typing import TYPE_CHECKING, Any

import orjson
from pydantic import PydanticDeprecatedSince20

from lfx.custom.eval import eval_custom_component_code
from lfx.log.logger import logger
from lfx.schema.artifact import get_artifact_type, post_process_raw
from lfx.schema.data import Data
from lfx.services.deps import get_settings_service, session_scope
from lfx.services.session import NoopSession

if TYPE_CHECKING:
    from lfx.custom.custom_component.component import Component
    from lfx.custom.custom_component.custom_component import CustomComponent
    from lfx.graph.vertex.base import Vertex

    # This is forward declared to avoid circular import
    class EventManager:
        pass


def instantiate_class(
    vertex: Vertex,
    user_id=None,
    event_manager: EventManager | None = None,
) -> Any:
    """Instantiate class from module type and key, and params."""
    vertex_type = vertex.vertex_type
    base_type = vertex.base_type
    logger.debug(f"Instantiating {vertex_type} of type {base_type}")

    if not base_type:
        msg = "No base type provided for vertex"
        raise ValueError(msg)

    custom_params = get_params(vertex.params)
    code = custom_params.pop("code")
    class_object: type[CustomComponent | Component] = eval_custom_component_code(code)
    custom_component: CustomComponent | Component = class_object(
        _user_id=user_id,
        _parameters=custom_params,
        _vertex=vertex,
        _tracing_service=None,
        _id=vertex.id,
    )
    if hasattr(custom_component, "set_event_manager"):
        custom_component.set_event_manager(event_manager)
    return custom_component, custom_params


async def get_instance_results(
    custom_component,
    custom_params: dict,
    vertex: Vertex,
    *,
    fallback_to_env_vars: bool = False,
    base_type: str = "component",
):
    custom_params = await update_params_with_load_from_db_fields(
        custom_component,
        custom_params,
        vertex.load_from_db_fields,
        fallback_to_env_vars=fallback_to_env_vars,
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)
        if base_type == "custom_components":
            return await build_custom_component(params=custom_params, custom_component=custom_component)
        if base_type == "component":
            return await build_component(params=custom_params, custom_component=custom_component)
        msg = f"Base type {base_type} not found."
        raise ValueError(msg)


def get_params(vertex_params):
    params = vertex_params
    params = convert_params_to_sets(params)
    params = convert_kwargs(params)
    return params.copy()


def convert_params_to_sets(params):
    """Convert certain params to sets."""
    if "allowed_special" in params:
        params["allowed_special"] = set(params["allowed_special"])
    if "disallowed_special" in params:
        params["disallowed_special"] = set(params["disallowed_special"])
    return params


def convert_kwargs(params):
    # Loop through items to avoid repeated lookups
    items_to_remove = []
    for key, value in params.items():
        if ("kwargs" in key or "config" in key) and isinstance(value, str):
            try:
                params[key] = orjson.loads(value)
            except orjson.JSONDecodeError:
                items_to_remove.append(key)

    # Remove invalid keys outside the loop to avoid modifying dict during iteration
    for key in items_to_remove:
        params.pop(key, None)

    return params


def load_from_env_vars(params, load_from_db_fields):
    for field in load_from_db_fields:
        if field not in params or not params[field]:
            continue
        key = os.getenv(params[field])
        if key:
            logger.info(f"Using environment variable {params[field]} for {field}")
        else:
            logger.error(f"Environment variable {params[field]} is not set.")
        params[field] = key if key is not None else None
        if key is None:
            logger.warning(f"Could not get value for {field}. Setting it to None.")
    return params


async def update_table_params_with_load_from_db_fields(
    custom_component: CustomComponent,
    params: dict,
    table_field_name: str,
    *,
    fallback_to_env_vars: bool = False,
) -> dict:
    """Update table parameters with load_from_db column values."""
    # Get the table data and column metadata
    table_data = params.get(table_field_name, [])
    metadata_key = f"{table_field_name}_load_from_db_columns"
    load_from_db_columns = params.pop(metadata_key, [])

    if not table_data or not load_from_db_columns:
        return params

    async with session_scope() as session:
        settings_service = get_settings_service()
        is_noop_session = isinstance(session, NoopSession) or (
            settings_service and settings_service.settings.use_noop_database
        )

        # Process each row in the table
        updated_table_data = []
        for row in table_data:
            if not isinstance(row, dict):
                updated_table_data.append(row)
                continue

            updated_row = row.copy()

            # Process each column that needs database loading
            for column_name in load_from_db_columns:
                if column_name not in updated_row:
                    continue

                # The column value should be the name of the global variable to lookup
                variable_name = updated_row[column_name]
                if not variable_name:
                    continue

                try:
                    if is_noop_session:
                        # Fallback to environment variables
                        key = os.getenv(variable_name)
                        if key:
                            logger.info(f"Using environment variable {variable_name} for table column {column_name}")
                        else:
                            logger.error(f"Environment variable {variable_name} is not set.")
                    else:
                        # Load from database
                        key = await custom_component.get_variable(
                            name=variable_name, field=f"{table_field_name}.{column_name}", session=session
                        )

                except ValueError as e:
                    if "User id is not set" in str(e):
                        raise
                    logger.debug(str(e))
                    key = None

                # If we couldn't get from database and fallback is enabled, try environment
                if fallback_to_env_vars and key is None:
                    key = os.getenv(variable_name)
                    if key:
                        logger.info(f"Using environment variable {variable_name} for table column {column_name}")
                    else:
                        logger.error(f"Environment variable {variable_name} is not set.")

                # Update the column value with the resolved value
                updated_row[column_name] = key if key is not None else None
                if key is None:
                    logger.warning(
                        f"Could not get value for {variable_name} in table column {column_name}. Setting it to None."
                    )

            updated_table_data.append(updated_row)

        params[table_field_name] = updated_table_data
        return params


async def update_params_with_load_from_db_fields(
    custom_component: CustomComponent,
    params,
    load_from_db_fields,
    *,
    fallback_to_env_vars=False,
):
    async with session_scope() as session:
        settings_service = get_settings_service()
        is_noop_session = isinstance(session, NoopSession) or (
            settings_service and settings_service.settings.use_noop_database
        )
        if is_noop_session:
            logger.debug("Loading variables from environment variables because database is not available.")
            return load_from_env_vars(params, load_from_db_fields)
        for field in load_from_db_fields:
            # Check if this is a table field (using our naming convention)
            if field.startswith("table:"):
                table_field_name = field[6:]  # Remove "table:" prefix
                params = await update_table_params_with_load_from_db_fields(
                    custom_component,
                    params,
                    table_field_name,
                    fallback_to_env_vars=fallback_to_env_vars,
                )
            else:
                # Handle regular field-level load_from_db
                if field not in params or not params[field]:
                    continue

                try:
                    key = await custom_component.get_variable(name=params[field], field=field, session=session)
                except ValueError as e:
                    if any(reason in str(e) for reason in ["User id is not set", "variable not found."]):
                        raise
                    logger.debug(str(e))
                    key = None

                if fallback_to_env_vars and key is None:
                    key = os.getenv(params[field])
                    if key:
                        logger.info(f"Using environment variable {params[field]} for {field}")
                    else:
                        logger.error(f"Environment variable {params[field]} is not set.")

                params[field] = key if key is not None else None
                if key is None:
                    logger.warning(f"Could not get value for {field}. Setting it to None.")

        return params


async def build_component(
    params: dict,
    custom_component: Component,
):
    # Now set the params as attributes of the custom_component
    custom_component.set_attributes(params)
    build_results, artifacts = await custom_component.build_results()

    return custom_component, build_results, artifacts


async def build_custom_component(params: dict, custom_component: CustomComponent):
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
    if custom_repr is None and isinstance(build_result, dict | Data | str):
        custom_repr = build_result
    if not isinstance(custom_repr, str):
        custom_repr = str(custom_repr)
    raw = custom_component.repr_value
    if hasattr(raw, "data") and raw is not None:
        raw = raw.data

    elif hasattr(raw, "model_dump") and raw is not None:
        raw = raw.model_dump()
    if raw is None and isinstance(build_result, dict | Data | str):
        raw = build_result.data if isinstance(build_result, Data) else build_result

    artifact_type = get_artifact_type(custom_component.repr_value or raw, build_result)
    raw = post_process_raw(raw, artifact_type)
    artifact = {"repr": custom_repr, "raw": raw, "type": artifact_type}

    if custom_component.get_vertex() is not None:
        custom_component.set_artifacts({custom_component.get_vertex().outputs[0].get("name"): artifact})
        custom_component.set_results({custom_component.get_vertex().outputs[0].get("name"): build_result})
        return custom_component, build_result, artifact

    msg = "Custom component does not have a vertex"
    raise ValueError(msg)
