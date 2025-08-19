#!/usr/bin/env python3
"""
Component Executor for Sandbox Execution

This script runs inside the nsjail sandbox and executes Langflow components
with the full runtime environment. It receives component code and parameters
via environment variables and returns results via stdout.
"""

import sys
import json
import os
import traceback
from pathlib import Path
from loguru import logger

def setup_environment():
    """Set up the sandbox environment for Langflow execution."""

    # Add Langflow to Python path
    langflow_paths = [
        "/opt/langflow/src/backend/base",
        "/app/src/backend/base",
        "/src/backend/base",
        "src/backend/base"
    ]

    for path in langflow_paths:
        if os.path.exists(path):
            sys.path.insert(0, path)
            break
    else:
        # Try to find langflow installation
        for path in sys.path:
            if "langflow" in path or "src" in path:
                continue  # Skip existing langflow paths

        # Add current working directory and common paths
        sys.path.insert(0, os.getcwd())
        sys.path.insert(0, "/app")

    # Check if network is enabled from environment
    network_enabled = os.environ.get('LANGFLOW_NETWORK_ENABLED', 'false').lower() == 'true'
    
    # Minimal DNS and TLS setup inside jail wit hout host bind mounts
    try:
        if network_enabled:
            # Only set up DNS if network is enabled
            os.makedirs("/etc", exist_ok=True)
            resolv = "nameserver 1.1.1.1\nnameserver 8.8.8.8\n"
            wrote_etc = False
            try:
                with open("/etc/resolv.conf", "w") as f:
                    f.write(resolv)
                with open("/etc/hosts", "w") as f:
                    f.write("127.0.0.1 localhost\n::1 localhost\n")
                wrote_etc = True
            except Exception as e:
                logger.error(f"SANDBOX_EXECUTOR_WARN: /etc write failed: {e}")
            if not wrote_etc:
                # Fallback to /run
                try:
                    os.makedirs("/run", exist_ok=True)
                    with open("/run/resolv.conf", "w") as f:
                        f.write(resolv)
                    os.environ.setdefault("RES_OPTIONS", "ndots:1")
                    os.environ.setdefault("LANGFLOW_RESOLV_FALLBACK", "/run/resolv.conf")
                except Exception as e2:
                    logger.error(f"SANDBOX_EXECUTOR_WARN: fallback /run write failed: {e2}")

        try:
            import certifi  # type: ignore
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        except Exception as e3:
            logger.warning(f"SANDBOX_EXECUTOR_WARN: certifi not available: {e3}")
    except Exception as e:
        logger.warning(f"SANDBOX_EXECUTOR_WARN: DNS/TLS setup exception: {e}")

def setup_mock_services():
    """Set up mock services to avoid file system access in sandbox."""
    import sys
    from pathlib import Path
    
    # Create a mock settings class that reads from environment
    class MockSettings:
        def __init__(self):
            # Dynamically set ALL attributes from LANGFLOW_ environment variables
            for key, value in os.environ.items():
                if key.startswith('LANGFLOW_'):
                    # Convert LANGFLOW_USER_AGENT to user_agent
                    attr_name = key[9:].lower()  # Remove LANGFLOW_ prefix
                    
                    # Type conversion
                    if value.lower() in ('true', 'false'):
                        value = value.lower() == 'true'
                    elif value.isdigit():
                        value = int(value)
                    elif '.' in value and value.replace('.', '').isdigit():
                        try:
                            value = float(value)
                        except ValueError:
                            pass  # Keep as string
                    
                    setattr(self, attr_name, value)
            
            # Create _items for iteration support
            self._items = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        
        def items(self):
            """Support iteration over settings."""
            return self._items.items()
        
        def get(self, key, default=None):
            """Support dict-like access."""
            return getattr(self, key, default)
            
        def __getattr__(self, name):
            """Return None for any undefined settings to avoid AttributeError."""
            return None
        
        def __contains__(self, key):
            """Support 'in' operator."""
            return hasattr(self, key)
    
    class MockSettingsService:
        def __init__(self):
            self.settings = MockSettings()
            self.auth_settings = self.settings  # Some components access auth_settings
            
        def get_settings(self):
            """Some components might call this method."""
            return self.settings
    
    # Mock the get_settings_service function
    mock_service = MockSettingsService()
    
    # Monkey-patch the services module
    try:
        import langflow.services.deps as deps
        original_get_settings = deps.get_settings_service
        deps.get_settings_service = lambda: mock_service
        
        # Also create a mock for get_session if needed
        def mock_get_session():
            """Mock session that returns None - components should handle this."""
            return None
        
        if hasattr(deps, 'get_session'):
            deps.get_session = mock_get_session

        # Log what settings were loaded
        settings_count = sum(1 for k in os.environ.keys() if k.startswith('LANGFLOW_'))

    except Exception as e:
        logger.error(f"SANDBOX_EXECUTOR_WARN: Failed to mock settings service: {e}")

def create_mock_vertex(component_params):
    """Create a minimal vertex object for component instantiation."""
    class MockVertex:
        def __init__(self, params):
            self.id = params.get('_id', 'sandbox_component')
            self.params = params
            self.vertex_type = params.get('_vertex_type', 'Component')
            self.base_type = params.get('_base_type', 'component')
            self.load_from_db_fields = []
            self.outputs = []

    return MockVertex(component_params)

def convert_bytes_to_string(obj):
    """Recursively convert bytes to string in a dictionary or list."""
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    elif isinstance(obj, dict):
        return {k: convert_bytes_to_string(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_bytes_to_string(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_bytes_to_string(item) for item in obj)
    else:
        return obj

def execute_component():
    """Execute the component with full Langflow runtime."""
    try:
        # Check if we should read from stdin
        use_stdin = os.environ.get('LANGFLOW_USE_STDIN', 'false').lower() == 'true'

        if use_stdin:
            # Read all input data from stdin
            try:
                stdin_data = sys.stdin.read()

                if not stdin_data:
                    raise ValueError("No input data received from stdin")

                # Parse the JSON input
                data = json.loads(stdin_data)

                # Extract parameters from stdin data
                component_code = data.get('code')
                component_params = data.get('params', {})
                component_class_name = data.get('class_name')
                execution_id = data.get('execution_id', 'sandbox_exec')
                vertex_data = data.get('vertex_data', {})

                if not component_code:
                    raise ValueError("No component code provided in stdin data")

            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse stdin JSON: {e}")
            except Exception as e:
                raise ValueError(f"Failed to read stdin: {e}")

        else:
            # Fallback to environment variables (for backward compatibility)
            component_code = os.environ.get('LANGFLOW_COMPONENT_CODE')
            component_params_json = os.environ.get('LANGFLOW_COMPONENT_PARAMS', '{}')
            component_class_name = os.environ.get('LANGFLOW_COMPONENT_CLASS')
            execution_id = os.environ.get('LANGFLOW_EXECUTION_ID', 'sandbox_exec')
            vertex_data_json = os.environ.get('LANGFLOW_VERTEX_DATA', '{}')

            if not component_code:
                raise ValueError("No component code provided in LANGFLOW_COMPONENT_CODE")

            # Parse parameters and vertex data
            component_params = json.loads(component_params_json)
            vertex_data = json.loads(vertex_data_json)

        # Set up environment
        setup_environment()
        
        # Mock the settings service to avoid file system access
        setup_mock_services()

        # Import required Langflow modules
        try:
            from langflow.custom.custom_component.custom_component import CustomComponent
            from langflow.custom.custom_component.component import Component
            from langflow.schema.data import Data
            from langflow.schema.message import Message
            from langflow.io import Output
            from langflow.services.deps import get_tracing_service
        except ImportError as e:
            logger.error(f"Failed to import Langflow modules: {e}")
            logger.error("Available paths:")
            for path in sys.path[:5]:  # Show first 5 paths
                logger.error(f"  {path}")
            raise

        # Import all necessary classes for the component code
        from langflow.io import MessageTextInput, Output

        global_namespace = {
            'CustomComponent': CustomComponent,
            'Component': Component,
            'Data': Data,
            'Message': Message,
            'Output': Output,
            'MessageTextInput': MessageTextInput,
            'os': os,  # Make os module available for os.environ access
            '__name__': '__main__'
        }

        # Execute the component code in controlled namespace
        exec(component_code, global_namespace)

        # Find the component class
        component_class = None
        if component_class_name and component_class_name in global_namespace:
            component_class = global_namespace[component_class_name]
        else:
            # Look for any class that ends with 'Component'
            for name, obj in global_namespace.items():
                if isinstance(obj, type) and name.endswith('Component') and name != 'Component' and name != 'CustomComponent':
                    component_class = obj
                    component_class_name = name
                    break

        if not component_class:
            raise ValueError(f"Component class {component_class_name} not found in executed code")

        # Create mock vertex for instantiation
        mock_vertex = create_mock_vertex(component_params)

        # Instantiate the component
        component_instance = component_class(
            _user_id=component_params.get('_user_id'),
            _parameters=component_params,
            _vertex=mock_vertex,
            _tracing_service=None,  # Disable tracing in sandbox
            _id=mock_vertex.id,
        )
        
        # List of attributes that should not be set directly (read-only properties)
        READONLY_ATTRS = {
            'ctx', 'graph', 'trace_name', 'trace_type', 'repr_value',
            'ERROR_CODE_NULL', 'ERROR_FUNCTION_ENTRYPOINT_NAME_NULL',
            'add_tool_output', 'cache', 'code_class_base_inheritance',
            'field_config', 'flow_id', 'flow_name', 'frozen',
            'function_entrypoint_name', 'user_id'
        }
        
        for key, value in component_params.items():
            # Skip read-only attributes
            if key in READONLY_ATTRS:
                continue

            if not key.startswith('_'):  # Skip internal parameters
                # Check if this parameter is marked to use a secret
                if isinstance(value, str) and value.startswith("__SECRET__"):
                    # Extract the secret key name
                    secret_key = value.replace("__SECRET__", "")
                    secret_env_key = f"LANGFLOW_SECRET_{secret_key.upper()}"
                    if secret_env_key in os.environ:
                        # Use the secret value from environment
                        setattr(component_instance, key, os.environ[secret_env_key])
                    else:
                        # Set to empty string instead of None when secret is not available
                        setattr(component_instance, key, "")
                else:
                    # Reconstruct Message and Data objects from dictionaries
                    if isinstance(value, dict):
                        # Check for type markers
                        if value.get('__langflow_type__') == 'Data':
                            value_copy = value.copy()
                            value_copy.pop('__langflow_type__', None)
                            reconstructed = Data(**value_copy)
                            setattr(component_instance, key, reconstructed)
                        elif value.get('__langflow_type__') == 'Message':
                            value_copy = value.copy()
                            value_copy.pop('__langflow_type__', None)
                            reconstructed = Message(**value_copy)
                            setattr(component_instance, key, reconstructed)
                        # Legacy format detection
                        elif value.get('_type') == 'Data':
                            data_value = value.get('value', value)
                            reconstructed = Data(value=data_value)
                            setattr(component_instance, key, reconstructed)
                        elif 'text' in value and 'sender' in value:
                            # Likely a Message object
                            try:
                                reconstructed = Message(**value)
                                setattr(component_instance, key, reconstructed)
                            except Exception:
                                setattr(component_instance, key, value)
                        else:
                            setattr(component_instance, key, value)
                    elif isinstance(value, list):
                        # Handle lists of objects
                        reconstructed_list = []
                        for item in value:
                            if isinstance(item, dict):
                                if item.get('__langflow_type__') == 'Data':
                                    item_copy = item.copy()
                                    item_copy.pop('__langflow_type__', None)
                                    reconstructed_list.append(Data(**item_copy))
                                elif item.get('__langflow_type__') == 'Message':
                                    item_copy = item.copy()
                                    item_copy.pop('__langflow_type__', None)
                                    reconstructed_list.append(Message(**item_copy))
                                else:
                                    reconstructed_list.append(item)
                            else:
                                reconstructed_list.append(item)
                        setattr(component_instance, key, reconstructed_list)
                    else:
                        setattr(component_instance, key, value)

        # Set outputs from vertex data if available
        if 'outputs' in vertex_data and vertex_data['outputs']:
            # Convert output dicts to proper Output objects if needed
            from langflow.io import Output
            outputs = []
            for output_data in vertex_data['outputs']:
                if isinstance(output_data, dict):
                    # Create Output object from dict
                    output = Output(
                        name=output_data.get('name', 'output'),
                        display_name=output_data.get('display_name', 'Output'),
                        method=output_data.get('method', 'build_output')
                    )
                    outputs.append(output)
                else:
                    outputs.append(output_data)
            component_instance.outputs = outputs

        # Quick DNS probe before executing component
        try:
            import socket
            test_host = socket.gethostbyname("example.com")
        except Exception as e:
            logger.warning(f"SANDBOX_NETWORK_TEST: Failed to resolve example.com: {e} - Network appears isolated", file=sys.stderr)
        
        # Execute the component
        
        # Check if this is a Component (has outputs) or CustomComponent (has build method)
        import inspect
        
        # Track which outputs were produced
        outputs_produced = {}
        
        if hasattr(component_instance, 'outputs') and component_instance.outputs:
            # Default to first output
            output = component_instance.outputs[0]
            method_name = output.method if hasattr(output, 'method') else output.get('method', 'build_output')
            output_name = output.name if hasattr(output, 'name') else output.get('name', 'result')
            
            if hasattr(component_instance, method_name):
                method = getattr(component_instance, method_name)
                if inspect.iscoroutinefunction(method):
                    import asyncio
                    result = asyncio.run(method())
                else:
                    result = method()
                
                # Store which output was produced
                outputs_produced[output_name] = result
            else:
                raise ValueError(f"Component does not have method {method_name}")
        elif hasattr(component_instance, 'build'):
            # This is a CustomComponent with a build method
            if inspect.iscoroutinefunction(component_instance.build):
                import asyncio
                result = asyncio.run(component_instance.build())
            else:
                result = component_instance.build()
        else:
            raise ValueError("Component has neither outputs nor build method")

        # Prepare result for output - handle Data objects specially
        if hasattr(result, '__class__') and result.__class__.__name__ == 'Data':
            # Handle Data objects by preserving their structure
            if hasattr(result, 'data'):
                data = result.data
                if isinstance(data, dict):
                    data = convert_bytes_to_string(data)
                    # Make a copy and add the type marker
                    output_data = data.copy()
                    output_data["_type"] = "Data"
                elif isinstance(data, bytes):
                    data = data.decode('utf-8', errors='replace')
                    output_data = {"value": data, "_type": "Data"}
                else:
                    # For non-dict data, wrap it properly
                    output_data = {"value": data, "_type": "Data"}
            else:
                output_data = {"value": str(result), "_type": "Data"}
        elif hasattr(result, '__class__') and result.__class__.__name__ == 'DataFrame':
            # Handle DataFrame objects
            if hasattr(result, 'to_dict'):
                # Convert DataFrame to dict representation
                output_data = {
                    "data": result.to_dict(orient='records'),
                    "_type": "DataFrame"
                }
            else:
                output_data = {"value": str(result), "_type": "DataFrame"}
        elif hasattr(result, 'data'):
            data = result.data
            if isinstance(data, dict):
                data = convert_bytes_to_string(data)
            elif isinstance(data, bytes):
                data = data.decode('utf-8', errors='replace')
            output_data = data
        elif hasattr(result, 'model_dump'):
            # For Pydantic models, especially Message objects
            # Try using mode='json' for proper nested serialization
            try:
                output_data = result.model_dump(mode='json')
            except TypeError:
                # Fallback for older Pydantic versions that don't support mode parameter
                output_data = result.model_dump()

                # Recursively convert any remaining Pydantic models to dicts
                def convert_pydantic_to_dict(obj):
                    if hasattr(obj, 'model_dump'):
                        return convert_pydantic_to_dict(obj.model_dump())
                    elif isinstance(obj, dict):
                        return {k: convert_pydantic_to_dict(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_pydantic_to_dict(item) for item in obj]
                    else:
                        return obj

                output_data = convert_pydantic_to_dict(output_data)

            if isinstance(output_data, dict):
                output_data = convert_bytes_to_string(output_data)
        elif isinstance(result, (dict, list)):
            output_data = convert_bytes_to_string(result) if isinstance(result, dict) else result
        elif isinstance(result, bytes):
            output_data = result.decode('utf-8', errors='replace')
        elif isinstance(result, (str, int, float, bool)):
            output_data = result
        else:
            output_data = str(result)

        # Return results as JSON to stdout
        execution_result = {
            "success": True,
            "result": output_data,
            "component_class": component_class_name,
            "execution_id": execution_id,
        }

        # Add output information if we have it
        if outputs_produced:
            # For now, we're handling single output case
            # In future, we could return all outputs_produced
            output_names = list(outputs_produced.keys())
            if output_names:
                execution_result["output_name"] = output_names[0]
        
        # Always include the method that was called for Components
        if hasattr(component_instance, 'outputs') and component_instance.outputs and 'method_name' in locals():
            execution_result["method_called"] = method_name

        # Check if result is too large and truncate if necessary
        try:
            result_json = json.dumps(execution_result)
        except TypeError as e:
            # Handle JSON serialization errors for nested Pydantic models
            if "is not JSON serializable" in str(e) and isinstance(execution_result['result'], dict):
                # Convert any remaining Pydantic models in the result
                for k, v in execution_result['result'].items():
                    if hasattr(v, 'model_dump'):
                        execution_result['result'][k] = v.model_dump()

                # Try again after conversion
                result_json = json.dumps(execution_result)
            else:
                raise
        max_size = 10 * 1024 * 1024  # 10MB limit

        if len(result_json) > max_size:
            # Truncate the result field
            if isinstance(execution_result["result"], dict):
                # For dict results, try to preserve structure but truncate values
                truncated_result = {}
                for key, value in execution_result["result"].items():
                    if isinstance(value, str) and len(value) > 1000:
                        truncated_result[key] = value[:1000] + "... [truncated]"
                    elif isinstance(value, (dict, list)) and len(str(value)) > 1000:
                        truncated_result[key] = str(value)[:1000] + "... [truncated]"
                    else:
                        truncated_result[key] = value
                execution_result["result"] = truncated_result
            elif isinstance(execution_result["result"], str):
                execution_result["result"] = execution_result["result"][:10000] + "... [truncated]"
            else:
                execution_result["result"] = str(execution_result["result"])[:10000] + "... [truncated]"

            execution_result["truncated"] = True
            result_json = json.dumps(execution_result)

        print(result_json)
        print("SANDBOX_EXECUTOR_SUCCESS", file=sys.stderr)
        return 0

    except Exception as e:
        # Analyze the error to provide better feedback
        error_message = str(e)
        error_type = type(e).__name__
        policy_hint = None
        simplified_error = False

        # Check for common sandbox policy violations
        if "multiprocessing" in error_message.lower() or error_type == "ImportError" and "multiprocessing" in error_message:
            policy_hint = "Multiprocessing is blocked in the sandbox."
            error_message = "Multiprocessing not allowed"
            simplified_error = True
        elif "[Errno 2] No such file or directory" in error_message:
            if "multiprocessing" in traceback.format_exc():
                policy_hint = "Subprocess spawning is not allowed in the sandbox."
                error_message = "Subprocess creation blocked"
                simplified_error = True
            else:
                policy_hint = "File or executable not found in sandbox."
                # Extract just the filename if possible
                if "'" in error_message:
                    filename = error_message.split("'")[1]
                    error_message = f"File not found: {filename}"
        elif "Permission denied" in error_message:
            policy_hint = "Operation requires higher privileges than sandbox allows."
            error_message = "Permission denied"
            simplified_error = True
        elif error_type == "ImportError":
            module_name = error_message.split("'")[1] if "'" in error_message else "unknown"
            if module_name in ["os", "sys", "subprocess", "multiprocessing", "__builtins__"]:
                policy_hint = f"Module '{module_name}' is blocked by security policy."
                error_message = f"Import blocked: {module_name}"
                simplified_error = True
            else:
                policy_hint = f"Module '{module_name}' not available in sandbox."
                error_message = f"Module not found: {module_name}"
                simplified_error = True
        elif "network" in error_message.lower() or "connection" in error_message.lower() or "[Errno 100]" in error_message:
            policy_hint = "Network access is disabled in the sandbox."
            error_message = "Network access denied"
            simplified_error = True
        elif "timeout" in error_message.lower():
            policy_hint = "Operation exceeded time limit."
            error_message = "Execution timeout"
            simplified_error = True
        elif "SSL" in error_message or "certificate" in error_message.lower():
            policy_hint = "SSL/TLS operations are blocked when network is disabled."
            error_message = "SSL operation blocked"
            simplified_error = True
        elif "URLError" in error_type or "HTTPError" in error_type:
            policy_hint = "HTTP requests are blocked in the sandbox."
            error_message = "HTTP request blocked"
            simplified_error = True

        # Only include full traceback for non-simplified errors
        include_traceback = not simplified_error
        
        error_result = {
            "success": False,
            "error": error_message,
            "error_type": error_type,
            "policy_hint": policy_hint,
            "execution_id": os.environ.get('LANGFLOW_EXECUTION_ID', 'unknown'),
        }
        
        if include_traceback:
            error_result["traceback"] = traceback.format_exc()

        print(json.dumps(error_result))
        # Use simplified error message in stderr too
        print(f"SANDBOX_EXECUTOR_ERROR: {error_message}", file=sys.stderr)
        if policy_hint:
            print(f"SANDBOX_EXECUTOR_HINT: {policy_hint}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    import warnings
    # Suppress asyncio cleanup warnings that occur when network is blocked
    warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*was never awaited")
    warnings.filterwarnings("ignore", message=".*Exception ignored in.*")
    sys.exit(execute_component())