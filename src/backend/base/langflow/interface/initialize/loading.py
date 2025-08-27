from __future__ import annotations

import inspect
import os
import warnings
from typing import TYPE_CHECKING, Any

import orjson
from loguru import logger
from pydantic import PydanticDeprecatedSince20

from langflow.custom.eval import eval_custom_component_code
from langflow.schema.artifact import get_artifact_type, post_process_raw
from langflow.schema.data import Data
from langflow.services.deps import get_tracing_service, session_scope

from langflow.exceptions.component import ComponentLockError

if TYPE_CHECKING:
    from langflow.custom.custom_component.component import Component
    from langflow.custom.custom_component.custom_component import CustomComponent
    from langflow.events.event_manager import EventManager
    from langflow.graph.vertex.base import Vertex


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
        _tracing_service=get_tracing_service(),
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
    # Check if sandbox system is enabled
    from langflow.sandbox.sandbox_context import ComponentTrustLevel
    from langflow.services.sandbox.service import is_sandbox_enabled
    import uuid

    # Check if sandboxing is enabled
    sandbox_enabled = is_sandbox_enabled()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)
        
        # If sandbox is enabled, verify component and determine trust level
        if sandbox_enabled:
            # Get component code and path for verification
            vertex = getattr(custom_component, "_vertex", None)
            component_class = custom_component.__class__
            component_class_name = component_class.__name__
            
            if base_type == "custom_components":
                component_path = f"custom.{getattr(vertex, 'id', component_class_name)}"
            else:
                # For built-in components, use the name property if available, otherwise class name
                # This matches how components are stored in the signature database
                if hasattr(custom_component, 'name') and custom_component.name:
                    component_path = custom_component.name
                else:
                    component_path = component_class_name
            
            component_code = vertex.params.get("code") if (vertex and getattr(vertex, "params", None)) else None
            
            trust_level = ComponentTrustLevel.UNTRUSTED
            modified = True

            from langflow.services.deps import get_sandbox_service
            sandbox_service = get_sandbox_service()
            verifier = sandbox_service.manager.verifier
            try:
                verified_ok = verifier.verify_component_signature(component_path, component_code)
                if verified_ok:
                    modified = False
                    trust_level = ComponentTrustLevel.VERIFIED
            except Exception as e:
                logger.warning(f"Verification problem for {component_class_name}: {e}")

            # Check lock mode
            locked = verifier.security_policy.is_lock_mode_enabled()
            if modified and locked:
                raise ComponentLockError(component_path)

            logger.info(
                f"Component {component_class_name} execution: "
                f"modified={'YES' if modified else 'NO'}, "
                f"locked={'YES' if locked else 'NO'}, "
                f"trust={trust_level.value}"
            )

            # Route based on trust level and sandbox support
            if trust_level == ComponentTrustLevel.VERIFIED and verifier.is_force_sandbox(component_path) is not True:
                # VERIFIED components get access to decrypted secrets and run without sandbox
                custom_params = await update_params_with_load_from_db_fields(
                    custom_component,
                    custom_params,
                    vertex.load_from_db_fields,
                    fallback_to_env_vars=fallback_to_env_vars,
                )
                
                if base_type == "custom_components":
                    return await build_custom_component(params=custom_params, custom_component=custom_component)
                else:
                    return await build_component(params=custom_params, custom_component=custom_component)
            else:
                # UNTRUSTED components - check if they support sandboxing
                sandbox_supported = verifier.supports_sandboxing(component_path)
                if not sandbox_supported:
                    # Component doesn't support sandboxing and is untrusted - cannot run
                    raise ComponentLockError(component_path)
                
                # Component supports sandboxing - run in sandbox WITHOUT decrypted secrets
                # Secrets will be handled by the sandbox manager via environment variables
                from langflow.sandbox.sandbox_context import SandboxExecutionContext
                
                context = SandboxExecutionContext(
                    execution_id=str(uuid.uuid4()),
                    execution_type="component",
                    component_path=component_path,
                )
                
                if base_type == "custom_components":
                    return await build_custom_component_sandboxed(
                        params=custom_params, 
                        custom_component=custom_component,
                        code=component_code,
                        context=context
                    )
                else:
                    # Set the params as attributes before sandboxing (WITHOUT decrypted secrets)
                    custom_component.set_attributes(custom_params)
                    return await build_component_sandboxed(
                        params=custom_params,
                        custom_component=custom_component,
                        code=component_code,
                        context=context
                    )
        else:
            # Sandbox disabled - decrypt secrets and run all components normally
            custom_params = await update_params_with_load_from_db_fields(
                custom_component,
                custom_params,
                vertex.load_from_db_fields,
                fallback_to_env_vars=fallback_to_env_vars,
            )
            
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


async def update_params_with_load_from_db_fields(
    custom_component: CustomComponent,
    params,
    load_from_db_fields,
    *,
    fallback_to_env_vars=False,
):
    async with session_scope() as session:
        for field in load_from_db_fields:
            if field not in params or not params[field]:
                continue

            try:
                key = await custom_component.get_variable(name=params[field], field=field, session=session)
            except ValueError as e:
                if "User id is not set" in str(e):
                    raise
                if "variable not found." in str(e) and not fallback_to_env_vars:
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


async def build_component_sandboxed(
    params: dict, 
    custom_component: Component,
    code: str,
    context
):
    """
    Execute component in sandbox (for UNTRUSTED components only).
    """
    from langflow.sandbox import get_sandbox_manager
    from langflow.schema import Data

    component_class_name = custom_component.__class__.__name__
    component_path = context.component_path
    
    logger.info(f"Executing {component_class_name} in sandbox")

    # Execute in sandbox
    result = await get_sandbox_manager().execute_component(
        code=code,
        component_path=component_path,
        component_instance=custom_component,
        context=context,
    )

    # Handle execution result
    if not result.success:
        error_parts = []
        if hasattr(result, "error") and result.error:
            error_parts.append(f"Error: {result.error}")
        if hasattr(result, "error_category") and result.error_category:
            error_parts.append(f"Category: {result.error_category}")
        if hasattr(result, "exit_code") and result.exit_code is not None:
            error_parts.append(f"Exit code: {result.exit_code}")
        if hasattr(result, "stderr") and result.stderr:
            error_parts.append(f"Stderr: {result.stderr}")
        if hasattr(result, "stdout") and result.stdout:
            error_parts.append(f"Stdout: {result.stdout}")
        
        error_message = "\n".join(error_parts) if error_parts else "Unknown sandbox error"
        raise RuntimeError(f"Sandbox execution failed:\n{error_message}")

    # Normalize output into (component, build_results, artifacts)
    def finalize(value):
        build_results, artifacts = {}, {}
        
        # Check if value contains output metadata
        output_name = None
        method_called = None
        if isinstance(value, dict) and '_result' in value:
            output_name = value.get('_output_name')
            method_called = value.get('_method_called')
            value = value['_result']
            logger.debug(f"Sandbox provided output_name: {output_name}, method_called: {method_called}")
        
        # If no output name was provided but we have method_called, try to find it
        if not output_name and method_called:
            # First, check if the method exists in the current outputs
            if hasattr(custom_component, 'outputs'):
                for output in custom_component.outputs:
                    output_method = output.method if hasattr(output, 'method') else output.get('method')
                    if output_method == method_called:
                        output_name = output.name if hasattr(output, 'name') else output.get('name', 'result')
                        logger.debug(f"Found output name {output_name} for method {method_called}")
                        break
            
            # If not found, try to infer from method name using common patterns
            if not output_name:
                # Common pattern: convert_to_X -> X_output
                if method_called.startswith('convert_to_'):
                    # Extract the type being converted to
                    output_type = method_called.replace('convert_to_', '')
                    output_name = f"{output_type}_output"
                    logger.debug(f"Inferred output name {output_name} from method {method_called}")
                # Another pattern: build_X -> X
                elif method_called.startswith('build_'):
                    output_name = method_called.replace('build_', '')
                    logger.debug(f"Inferred output name {output_name} from method {method_called}")
                # Default pattern: method_name -> method_name_output
                else:
                    output_name = f"{method_called}_output"
                    logger.debug(f"Using default output name {output_name} for method {method_called}")
        
        # If still no output name, use default
        if not output_name:
            output_name = custom_component.outputs[0].name if getattr(custom_component, "outputs", None) else "result"

        if isinstance(value, dict) and "_type" in value and value["_type"] == "Data":
            # Remove the _type marker and create Data object with the rest
            data_dict = {k: v for k, v in value.items() if k != "_type"}
            logger.debug(f"Sandbox result - creating Data object with data dict: {data_dict}")
            # If data_dict has a 'value' key, use Data(value=...), otherwise use Data(**data_dict)
            if len(data_dict) == 1 and "value" in data_dict:
                data_obj = Data(value=data_dict["value"])
            else:
                data_obj = Data(**data_dict)
            build_results[output_name] = data_obj
            custom_component._results = {output_name: data_obj}
            s = str(data_dict)
            artifacts[output_name] = {
                "repr": (s[:1000] + "... [truncated]") if len(s) > 1000 else s,
                "raw": data_dict,
                "type": "Data",
            }
        elif isinstance(value, dict) and "_type" in value and value["_type"] == "DataFrame":
            # Handle DataFrame results from sandbox
            from langflow.schema import DataFrame
            data_dict = {k: v for k, v in value.items() if k != "_type"}
            logger.debug(f"Sandbox result - creating DataFrame object with data dict: {data_dict}")
            
            if "data" in data_dict:
                # Create DataFrame from records
                df_obj = DataFrame(data_dict["data"])
            else:
                # Fallback
                df_obj = DataFrame([data_dict])
            
            build_results[output_name] = df_obj
            custom_component._results = {output_name: df_obj}
            s = str(data_dict)
            artifacts[output_name] = {
                "repr": (s[:1000] + "... [truncated]") if len(s) > 1000 else s,
                "raw": data_dict,
                "type": "DataFrame",
            }
        else:
            build_results[output_name] = value
            custom_component._results = {output_name: value}
            s = str(value)
            artifacts[output_name] = {
                "repr": s[:100] if len(s) > 100 else s,
                "raw": value,
                "type": "Any",
            }
        
        return custom_component, build_results, artifacts

    return finalize(result.result)


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

    if custom_component._vertex is not None:
        custom_component._artifacts = {custom_component._vertex.outputs[0].get("name"): artifact}
        custom_component._results = {custom_component._vertex.outputs[0].get("name"): build_result}
        return custom_component, build_result, artifact

    msg = "Custom component does not have a vertex"
    raise ValueError(msg)


async def build_custom_component_sandboxed(
    params: dict,
    custom_component: CustomComponent,
    code: str,
    context
):
    """
    Execute custom component in sandbox (for UNTRUSTED components only).
    """
    from langflow.sandbox import get_sandbox_manager
    from langflow.schema import Data

    # Normalize retriever param (kept from original)
    if "retriever" in params and hasattr(params["retriever"], "as_retriever"):
        params["retriever"] = params["retriever"].as_retriever()

    component_class_name = custom_component.__class__.__name__
    component_path = context.component_path
    
    logger.info(f"Executing custom component {component_class_name} in sandbox")

    # Execute in sandbox
    result = await get_sandbox_manager().execute_component(
        code=code,
        component_path=component_path,
        component_instance=custom_component,
        context=context,
    )

    # Handle execution result
    if not result.success:
        error_parts = []
        if hasattr(result, "error") and result.error:
            error_parts.append(f"Error: {result.error}")
        if hasattr(result, "error_category") and result.error_category:
            error_parts.append(f"Category: {result.error_category}")
        if hasattr(result, "exit_code") and result.exit_code is not None:
            error_parts.append(f"Exit code: {result.exit_code}")
        if hasattr(result, "stderr") and result.stderr:
            error_parts.append(f"Stderr: {result.stderr}")
        if hasattr(result, "stdout") and result.stdout:
            error_parts.append(f"Stdout: {result.stdout}")
        
        error_message = "\n".join(error_parts) if error_parts else "Unknown sandbox error"
        raise RuntimeError(f"Sandbox execution failed:\n{error_message}")

    # Normalize output into (component, build_results, artifact)
    def finalize(value):
        build_results, artifact = {}, None
        output_name = custom_component._vertex.outputs[0].get("name") if custom_component._vertex else "result"

        if isinstance(value, dict) and ("_type" in value or "value" in value):
            data_value = value.get("value", value)
            data_obj = Data(value=data_value)
            build_results[output_name] = data_obj
            custom_component._results = {output_name: data_obj}
            s = str(data_value)
            artifact = {
                "repr": (s[:1000] + "... [truncated]") if len(s) > 1000 else s,
                "raw": data_value,
                "type": "Data",
            }
        else:
            build_results[output_name] = value
            custom_component._results = {output_name: value}
            s = str(value)
            artifact = {
                "repr": s[:100] if len(s) > 100 else s,
                "raw": value,
                "type": "Any",
            }

        # Keep parity with original: store both artifacts and results on the instance
        if custom_component._vertex is not None:
            custom_component._artifacts = {output_name: artifact}
            return custom_component, build_results[output_name], artifact

        raise ValueError("Custom component does not have a vertex")

    return finalize(result.result)
