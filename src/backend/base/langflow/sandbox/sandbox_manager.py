"""Sandbox manager for secure component execution with nsjail isolation."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING
from uuid import uuid4

from loguru import logger
from sqlmodel import Session

from .sandbox_context import (
    SandboxExecutionContext,
    SandboxExecutionResult,
    SandboxConfig
)
from .policies import SecurityPolicy
from .signature import ComponentSecurityManager

if TYPE_CHECKING:
    from langflow.custom.custom_component.custom_component import CustomComponent


class SandboxManager:
    """Sandbox manager for secure component execution."""
    
    def __init__(self, config: Optional[SandboxConfig] = None, db_session: Optional[Session] = None):
        self.config = config or SandboxConfig()
        self.security_policy = SecurityPolicy(self.config)
        self.db_session = db_session
        self.verifier = ComponentSecurityManager(self.security_policy, db_session)
        
        # Set up secure sandbox environment
        self._setup_sandbox_environment()
    
    async def execute_component(
        self, 
        code: str,
        component_path: str,
        component_instance: Optional[CustomComponent] = None,
        context: Optional[SandboxExecutionContext] = None
    ) -> SandboxExecutionResult:
        """Execute component code in sandbox with appropriate trust level."""

        # Execute component code in a sandboxed (nsjail) environment.
        if context is None:
            context = SandboxExecutionContext(
                execution_id=str(uuid4()),
                execution_type="component",
                component_path=component_path
            )

        # Step 4: Get sandbox profile and apply settings
        profile = self.security_policy.get_profile()
        if not profile:
            logger.error("No sandbox profile found! (Sandboxing enabled but no profile available)")
            return SandboxExecutionResult(
                execution_id=context.execution_id,
                success=False,
                error="No sandbox profile configured (BUG)",
                error_category="configuration_error",
                stdout="",
                stderr="",
                execution_time=0.0,
            )
        logger.info(f"Using single sandbox profile (hostname: {profile.nsjail_config.hostname})")

        # Validate code size against profile limits
        is_valid, error_msg = profile.validate_code_size(code)
        if not is_valid:
            logger.error(f"Code size validation failed: {error_msg}")
            return SandboxExecutionResult(
                execution_id=context.execution_id,
                success=False,
                error=error_msg,
                error_category="CODE_SIZE_LIMIT",
                stdout="",
                stderr="",
                execution_time=0.0,
            )
        
        context.timeout = profile.max_execution_time_seconds
        context.max_memory_mb = profile.max_memory_mb
        context.allow_network = profile.network_enabled
        context.secrets_required = profile.allow_secrets_for_untrusted

        # Step 5: Resolve secrets if allowed for untrusted components
        secrets_env = {}
        if profile.allow_secrets_for_untrusted and component_instance:
            # Resolve secrets from component parameters
            secrets_env = await self._resolve_component_secrets(component_instance)
            logger.info(f"Resolved {len(secrets_env)} secrets for untrusted component {component_path}")
        elif not profile.allow_secrets_for_untrusted and component_instance:
            # Provide empty strings for secrets when not allowed
            secrets_env = await self._resolve_empty_secrets(component_instance)
            logger.info(f"Secrets access denied for untrusted component {component_path} - using empty strings (allow_secrets_for_untrusted=false)")

        # Step 6: Execute component using the component executor
        if component_instance:
            # Use the full runtime component executor
            result = await self._prepare_component_payload(
                code=code,
                component_path=component_path,
                component_instance=component_instance,
                context=context,
                profile=profile,
                secrets_env=secrets_env
            )
            return result
        else:
            # Fallback to raw code execution (for direct Python code)
            executable_code = code
        
        # Step 6: Log execution decision
        logger.info(
            f"Executing {component_path} in sandbox",
            extra={
                "component": component_path,
                "sandbox_profile": profile.name,
                "execution_id": context.execution_id
            }
        )
        
        # Step 7: Execute in nsjail sandbox via the executor
        return await self._run_in_nsjail(
            code=executable_code,
            context=context,
            profile=profile,
            secrets_env=secrets_env,
        )
    
    def _extract_essential_data(self, params: dict) -> dict:
        """Extract only essential data from component parameters, removing complex objects."""
        essential = {}
        
        for key, value in params.items():
            try:
                essential[key] = self._extract_value_data(value)
            except Exception as e:
                logger.debug(f"Failed to extract data from parameter {key} of type {type(value)}: {e}")
                # Skip parameters that can't be processed
                continue
                
        return essential
    
    def _extract_value_data(self, value):
        """Extract essential data from a single value."""
        # Handle None
        if value is None:
            return None
            
        # Handle basic JSON-serializable types
        if isinstance(value, (str, int, float, bool)):
            return value
            
        # Handle SecretStr objects (from pydantic)
        if hasattr(value, '__class__') and value.__class__.__name__ == 'SecretStr':
            # SecretStr objects need to be converted to string
            return str(value.get_secret_value()) if hasattr(value, 'get_secret_value') else str(value)
            
        # Handle collections recursively
        if isinstance(value, list):
            return [self._extract_value_data(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._extract_value_data(item) for item in value)
        if isinstance(value, dict):
            return {k: self._extract_value_data(v) for k, v in value.items()}
            
        # Handle Pydantic models FIRST (before checking for .data attribute)
        if hasattr(value, 'model_dump') and callable(getattr(value, 'model_dump')):
            # Pydantic model - use model_dump and add type marker
            if value.__class__.__name__ == 'Data':
                # Special handling for Data objects to preserve structure
                dumped = {
                    'data': value.data,
                    'text_key': value.text_key,
                    'default_value': value.default_value,
                    '__langflow_type__': 'Data'
                }
                logger.info(f"Serializing Data object: {dumped}")
            else:
                dumped = value.model_dump()
                # Add type marker for Message objects
                if value.__class__.__name__ == 'Message':
                    dumped['__langflow_type__'] = 'Message'
            return dumped
            
        # Handle Langflow-specific objects - extract their data content
        if hasattr(value, 'data') and not callable(getattr(value, 'data')):
            # Object has a data attribute (like Data objects)
            return self._extract_value_data(value.data)
        elif hasattr(value, 'get_result') and callable(getattr(value, 'get_result')):
            # Object has a get_result method
            return self._extract_value_data(value.get_result())
        elif hasattr(value, 'value') and not callable(getattr(value, 'value')):
            # Object has a value attribute
            return self._extract_value_data(value.value)
        elif hasattr(value, '__dict__'):
            # Generic object - try to extract simple attributes
            simple_attrs = {}
            for attr_name, attr_value in value.__dict__.items():
                if not attr_name.startswith('_') and not callable(attr_value):
                    try:
                        # Test if attribute is JSON serializable
                        json.dumps(attr_value, default=str)
                        simple_attrs[attr_name] = self._extract_value_data(attr_value)
                    except (TypeError, ValueError):
                        continue
            return simple_attrs if simple_attrs else str(value)
        else:
            # Fallback: convert to string representation
            return str(value)
    
    async def _resolve_component_secrets(self, component_instance: CustomComponent) -> Dict[str, str]:
        """Resolve secrets from component parameters and database variables."""
        secrets_env = {}
        
        # Check if the component has load_from_db_fields
        if hasattr(component_instance, '_vertex') and component_instance._vertex:
            vertex = component_instance._vertex
            if hasattr(vertex, 'load_from_db_fields') and vertex.load_from_db_fields:
                # Get the component parameters
                params = component_instance._parameters or {}
                
                # Import session scope for database access
                from langflow.services.deps import session_scope
                
                async with session_scope() as session:
                    for field in vertex.load_from_db_fields:
                        if field in params and params[field]:
                            try:
                                # Try to get the secret from database
                                secret_value = await component_instance.get_variable(
                                    name=params[field], 
                                    field=field,
                                    session=session
                                )
                                
                                if secret_value:
                                    # Pass as environment variable with LANGFLOW_SECRET_ prefix
                                    env_key = f"LANGFLOW_SECRET_{field.upper()}"
                                    secrets_env[env_key] = str(secret_value)
                                    logger.debug(f"Resolved secret for field {field}")
                                else:
                                    # Try environment variable as fallback
                                    env_value = os.getenv(params[field])
                                    if env_value:
                                        env_key = f"LANGFLOW_SECRET_{field.upper()}"
                                        secrets_env[env_key] = env_value
                                        logger.debug(f"Using environment variable for field {field}")
                                        
                            except Exception as e:
                                logger.warning(f"Failed to resolve secret for field {field}: {e}")
                                # Try environment variable as fallback
                                env_value = os.getenv(params.get(field, ''))
                                if env_value:
                                    env_key = f"LANGFLOW_SECRET_{field.upper()}"
                                    secrets_env[env_key] = env_value
        
        # Also pass through any existing LANGFLOW_ or OPENAI_API_KEY environment variables
        for key, value in os.environ.items():
            if key.startswith('LANGFLOW_') or key.endswith('_API_KEY') or key.endswith('_SECRET'):
                if key not in secrets_env:  # Don't override resolved secrets
                    secrets_env[key] = value
        
        return secrets_env
        
    async def _resolve_empty_secrets(self, component_instance: CustomComponent) -> Dict[str, str]:
        """Resolve empty strings for secrets when access is denied."""
        secrets_env = {}
        
        # Check if the component has load_from_db_fields
        if hasattr(component_instance, '_vertex') and component_instance._vertex:
            vertex = component_instance._vertex
            if hasattr(vertex, 'load_from_db_fields') and vertex.load_from_db_fields:
                # Get the component parameters
                params = component_instance._parameters or {}
                
                # For each field that would normally load from DB, provide an empty string
                for field in vertex.load_from_db_fields:
                    if field in params and params[field]:
                        # Pass empty string as environment variable with LANGFLOW_SECRET_ prefix
                        env_key = f"LANGFLOW_SECRET_{field.upper()}"
                        secrets_env[env_key] = ""
                        logger.debug(f"Providing empty string for secret field {field}")
        
        # Also provide empty strings for common API key environment variables
        for key in os.environ.keys():
            if (key.startswith('LANGFLOW_') or key.endswith('_API_KEY') or key.endswith('_SECRET')) and key not in secrets_env:
                secrets_env[key] = ""
        
        return secrets_env
    
    async def _prepare_component_payload(
        self,
        code: str,
        component_path: str,
        component_instance: CustomComponent,
        context: SandboxExecutionContext,
        profile,
        secrets_env: Dict[str, str]
    ) -> SandboxExecutionResult:
        """Execute component with full Langflow runtime inside sandbox."""
        try:
            # Get component class name
            component_class_name = component_instance.__class__.__name__
            logger.info(f"Executing {component_class_name} in sandbox")
            
            # Special logging for TypeConverter
            if component_class_name == "TypeConverterComponent":
                logger.info(f"TypeConverter input_data attribute: {getattr(component_instance, 'input_data', 'NOT FOUND')}")
                if hasattr(component_instance, 'input_data'):
                    input_data = getattr(component_instance, 'input_data')
                    logger.info(f"TypeConverter input_data type: {type(input_data).__name__}")
                    if hasattr(input_data, 'data'):
                        logger.info(f"TypeConverter input_data.data: {input_data.data}")
            
            # Prepare component parameters - extract essential data only
            component_params = {}
            if hasattr(component_instance, '_parameters'):
                raw_params = component_instance._parameters or {}
                component_params = self._extract_essential_data(raw_params)

            # Also check for attributes that were set directly on the component
            # This is important for resolved vertex references
            for attr_name in dir(component_instance):
                if not attr_name.startswith('_') and attr_name not in ['inputs', 'outputs', 'display_name', 'description', 'icon', 'name', 'documentation', 'code']:
                    try:
                        attr_value = getattr(component_instance, attr_name)
                        if not callable(attr_value) and attr_value is not None:
                            # Check if this is an input that was resolved from a vertex
                            # Either it's not in params yet, or it's an empty string
                            if attr_name not in component_params or (isinstance(component_params.get(attr_name), str) and component_params[attr_name] == ""):
                                # This was likely a vertex reference that got resolved
                                component_params[attr_name] = self._extract_value_data(attr_value)
                                
                    except Exception as e:
                        # Skip attributes that can't be accessed
                        pass
            
            if hasattr(component_instance, 'inputs'):
                for input_def in component_instance.inputs:
                    if hasattr(input_def, 'name'):
                        input_name = input_def.name
                        if hasattr(component_instance, input_name):
                            input_value = getattr(component_instance, input_name)
                            
                            # Check if the input_value is a Vertex reference
                            if hasattr(input_value, '__class__') and input_value.__class__.__name__ == 'Vertex':
                                # This is a problem - Vertex references should be resolved before sandboxing
                                input_value = ""  # Default to empty string as we can't resolve it here
                            
                            # Only override if the value is different from the parameter definition
                            if input_value is not None and (
                                input_name not in component_params or 
                                component_params.get(input_name) != input_value
                            ):
                                component_params[input_name] = self._extract_value_data(input_value)
            
            # If secrets are provided, mark parameters that should use secrets
            if secrets_env:
                # Check which parameters have corresponding secrets
                for key in list(component_params.keys()):
                    secret_env_key = f"LANGFLOW_SECRET_{key.upper()}"
                    if secret_env_key in secrets_env:
                        # Mark this parameter to use the secret
                        # The executor will look for this in environment
                        component_params[key] = f"__SECRET__{key}"
                        logger.debug(f"Parameter {key} will use secret from environment")
                        
                        # If this is an empty string secret (when allow_secrets_for_untrusted=false),
                        # log this specifically for debugging
                        if secrets_env[secret_env_key] == "":
                            logger.debug(f"Parameter {key} will use empty string (secrets not allowed)")
            
            # Add component metadata
            component_params.update({
                '_id': getattr(component_instance, '_id', context.execution_id),
                '_user_id': getattr(component_instance, '_user_id', None),
                '_vertex_type': 'Component',
                '_base_type': 'component'
            })
            
            # Extract real vertex data if available
            vertex_data = None
            if hasattr(component_instance, '_vertex') and component_instance._vertex:
                vertex = component_instance._vertex
                try:
                    # Serialize essential vertex attributes
                    vertex_data = {
                        'id': vertex.id,
                        'vertex_type': getattr(vertex, 'vertex_type', 'Component'),
                        'base_type': getattr(vertex, 'base_type', 'component'),
                        'outputs': []
                    }
                    
                    # Serialize outputs if they exist
                    if hasattr(vertex, 'outputs') and vertex.outputs:
                        for i, output in enumerate(vertex.outputs):
                            if hasattr(output, 'model_dump') and callable(getattr(output, 'model_dump')):
                                # Pydantic model - use model_dump
                                dumped = output.model_dump()
                                vertex_data['outputs'].append(dumped)
                            elif isinstance(output, dict):
                                # Already a dictionary - use it directly
                                vertex_data['outputs'].append(output)
                            elif hasattr(output, '__dict__'):
                                # Regular object - serialize attributes
                                # DON'T default method to 'build' - preserve None if not set
                                method_value = getattr(output, 'method', None)
                                output_dict = {
                                    'name': getattr(output, 'name', 'result'),
                                    'types': getattr(output, 'types', ['Data']),
                                    'selected': getattr(output, 'selected', None),
                                    'hidden': getattr(output, 'hidden', None),
                                    'display_name': getattr(output, 'display_name', None),
                                }
                                # Only add method if it's not None
                                if method_value is not None:
                                    output_dict['method'] = method_value
                                vertex_data['outputs'].append(output_dict)
                            else:
                                # Fallback for other types
                                logger.info(f"VERTEX_SERIALIZATION: Using fallback for: {output}")
                                fallback_dict = {
                                    'name': str(output.get('name', 'result')),
                                    'method': 'build'
                                }
                                logger.info(f"VERTEX_SERIALIZATION: Fallback dict: {fallback_dict}")
                                vertex_data['outputs'].append(fallback_dict)
                    
                    logger.debug(f"Serialized vertex data: {vertex_data}")
                    
                except Exception as e:
                    logger.warning(f"Failed to serialize vertex data: {e}")
                    vertex_data = None
            else:
                logger.info(f"SANDBOX_MANAGER: No vertex found on component")
            
            # Prepare environment variables for the component executor
            # Merge PYTHONPATH to include venv site-packages from profile env
            manager_pp = '/opt/langflow/src/backend/base:/app/src/backend/base:/src/backend/base'
            profile_pp = profile.nsjail_config.env.get('PYTHONPATH', '') if hasattr(profile, 'nsjail_config') else ''
            merged_pp = ':'.join([p for p in [manager_pp, profile_pp] if p])
            
            # Add venv to PYTHONPATH if not already there
            if '/app/.venv' not in merged_pp:
                merged_pp = f"{merged_pp}:/app/.venv/lib/python3.12/site-packages"
            
            logger.info(f"SANDBOX DEBUG - PYTHONPATH: {merged_pp}")

            # Build a richer vertex payload with real outputs when available
            full_vertex_data = vertex_data or {}
            try:
                if hasattr(component_instance, '_vertex') and component_instance._vertex:
                    v = component_instance._vertex
                    outs = []
                    if hasattr(v, 'outputs') and v.outputs:
                        for o in v.outputs:
                            if hasattr(o, 'model_dump') and callable(getattr(o, 'model_dump', None)):
                                outs.append(o.model_dump())
                            elif isinstance(o, dict):
                                outs.append(o)
                            else:
                                outs.append({
                                    'name': getattr(o, 'name', 'result'),
                                    'types': getattr(o, 'types', ['Data']),
                                    'selected': getattr(o, 'selected', 'Data'),
                                })
                    if outs:
                        full_vertex_data['outputs'] = outs
                    if 'id' not in full_vertex_data:
                        full_vertex_data['id'] = getattr(v, 'id', context.execution_id)
            except Exception:
                pass

            # Prepare input data to pass via stdin
            stdin_data = {
                'code': code,
                'params': component_params,
                'class_name': component_class_name,
                'execution_id': context.execution_id,
                'vertex_data': full_vertex_data
            }
            # Custom JSON encoder for handling special types
            class SandboxJSONEncoder(json.JSONEncoder):
                def default(self, obj):
                    # Handle SecretStr objects
                    if hasattr(obj, '__class__') and obj.__class__.__name__ == 'SecretStr':
                        return str(obj.get_secret_value()) if hasattr(obj, 'get_secret_value') else str(obj)
                    # Handle other non-serializable objects
                    try:
                        return super().default(obj)
                    except TypeError:
                        return str(obj)
            
            stdin_json = json.dumps(stdin_data, cls=SandboxJSONEncoder)
            
            # Log the size of data being passed
            logger.debug(f"Passing {len(stdin_json)} bytes via stdin to sandbox")
            
            # Start with the profile's filtered environment variables
            # This respects the env_params whitelist from config.json
            executor_env = profile.nsjail_config.env.copy()
            
            # Add essential execution environment variables
            executor_env.update({
                'LANGFLOW_USE_STDIN': 'true',  # Signal to executor to read from stdin
                'LANGFLOW_EXECUTION_ID': context.execution_id,
                'LANGFLOW_NETWORK_ENABLED': str(profile.network_enabled).lower(),  # Pass network setting
                'PYTHONPATH': merged_pp,
                'PYTHONUNBUFFERED': '1',
                'PYTHONDONTWRITEBYTECODE': '1',
                'HOME': '/tmp',  # Set a home directory for the sandbox
                'USER': 'sandbox',  # Set a user name
                'TMPDIR': '/tmp',  # Set temp directory
            })
            
            # Add secrets if provided and allowed by profile
            if secrets_env and profile.allow_secrets_for_untrusted:
                executor_env.update(secrets_env)
                logger.debug(f"Added {len(secrets_env)} secrets to sandbox environment")
            elif secrets_env and not profile.allow_secrets_for_untrusted:
                logger.warning(f"Secrets requested but not allowed by profile (allow_secrets_for_untrusted=False)")
            
            # Create execution-specific temporary directory to prevent cross-tenant access
            import uuid
            
            # Use container hostname + execution ID for uniqueness across containers
            container_id = os.environ.get('HOSTNAME', 'unknown')
            unique_suffix = f"{container_id}-{context.execution_id[:8]}"
            host_tmp_dir = f"/tmp/langflow-sandbox-{unique_suffix}"
            
            # Create the unique temporary directory
            os.makedirs(host_tmp_dir, exist_ok=True)
            os.chmod(host_tmp_dir, 0o777)  # Restrictive permissions - only owner can access
            
            # Add the execution-specific temp mount to nsjail config
            profile.nsjail_config.add_execution_temp_mount(context.execution_id, host_tmp_dir)
            
            logger.info(f"Created execution-specific temp directory: {host_tmp_dir}")
            
            try:
                # Use nsjail in privileged Docker container
                nsjail_cmd = ["sudo", "/usr/local/bin/nsjail"]
                nsjail_cmd.extend(profile.nsjail_config.to_command_args())
                nsjail_cmd.extend([
                    "--time_limit", str(context.timeout),
                ])
                
                # Debug: Log network isolation status and full command
                logger.info(f"SANDBOX NETWORK DEBUG - network_enabled: {profile.network_enabled}, "
                           f"disable_clone_newnet: {profile.nsjail_config.disable_clone_newnet}")
                
                # Check if --disable_clone_newnet is in the command
                has_disable_flag = "--disable_clone_newnet" in nsjail_cmd
                logger.info(f"NSJAIL COMMAND DEBUG - Has --disable_clone_newnet flag: {has_disable_flag}")
                logger.info(f"NSJAIL COMMAND (first 20 args): {' '.join(nsjail_cmd[:20])}")
                
                # Add environment variables
                for key, value in executor_env.items():
                    nsjail_cmd.extend(["--env", f"{key}={value}"])
                
                # Use the Docker Python with venv packages available via PYTHONPATH
                python_executable = "/usr/local/bin/python"
                
                nsjail_cmd.extend([
                    "--", python_executable, "/opt/executor.py"
                ])
                
                # Execute the component executor with stdin
                start_time = datetime.utcnow()
                process = await asyncio.create_subprocess_exec(
                    *nsjail_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Send input data via stdin and get output
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=stdin_json.encode('utf-8')),
                    timeout=context.timeout + 10
                )
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Decode outputs
                stdout_str = stdout.decode('utf-8') if stdout else ""
                stderr_str = stderr.decode('utf-8') if stderr else ""
                
                logger.debug(f"Component executor completed: return_code={process.returncode}, time={execution_time:.2f}s")
                
                if stdout_str:
                    logger.info(f"Component executor stdout: {stdout_str[:200]}...")
                if stderr_str:
                    # Filter out nsjail debug output
                    filtered_stderr_lines = []
                    has_actual_errors = False
                    for line in stderr_str.split('\n'):
                        # Skip nsjail info lines (they start with [I] or contain jail parameters)
                        if (line.strip().startswith('[I][') or 
                            'Mode: STANDALONE' in line or 
                            'Jail parameters:' in line or
                            'hostname:' in line or
                            'clone_new' in line or
                            'max_conns' in line or
                            'time_limit:' in line or
                            'process:' in line or
                            'bind:[' in line or
                            'personality:' in line or
                            'daemonize:' in line or
                            'chroot:' in line):
                            continue
                        # Check for actual errors
                        if line.strip() and ('ERROR' in line or 'Error' in line or 'error' in line or 
                                           'WARN' in line or 'Warning' in line or 'warning' in line or
                                           'Traceback' in line or 'Exception' in line):
                            has_actual_errors = True
                        # Keep non-nsjail lines
                        if line.strip():
                            filtered_stderr_lines.append(line)
                    
                    filtered_stderr = '\n'.join(filtered_stderr_lines).strip()
                    
                    if filtered_stderr:
                        # Use appropriate log level and message based on content
                        if has_actual_errors:
                            logger.warning(f"Component executor warnings/errors: {filtered_stderr[:500]}{'...' if len(filtered_stderr) > 500 else ''}")
                        else:
                            logger.info(f"Component executor output: {filtered_stderr[:500]}{'...' if len(filtered_stderr) > 500 else ''}")
                    
                    # Always log full stderr at debug level for troubleshooting
                    logger.debug(f"Component executor stderr (full): {stderr_str}")
                
                # Parse the result from stdout
                result_data = None
                if stdout_str.strip():
                    try:
                        # Look for JSON output (the last JSON object in stdout)
                        lines = stdout_str.strip().split('\n')
                        for line in reversed(lines):
                            if line.strip().startswith('{'):
                                result_data = json.loads(line.strip())
                                break
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse component executor output as JSON: {e}")
                
                # Create execution result
                if process.returncode == 0 and result_data and result_data.get('success'):
                    # Extract the result and any additional metadata
                    result = result_data.get('result')
                    
                    # Check if output_name or method_called was provided
                    output_name = result_data.get('output_name')
                    method_called = result_data.get('method_called')
                    
                    # If we have metadata, wrap the result
                    if output_name or method_called:
                        result = {
                            '_result': result,
                            '_output_name': output_name,
                            '_method_called': method_called
                        }
                    
                    return SandboxExecutionResult(
                        execution_id=context.execution_id,
                        success=True,
                        result=result,
                        stdout=stdout_str,
                        stderr=stderr_str,
                        execution_time=execution_time,
                        
                    )
                else:
                    # Analyze failure and provide meaningful error messages
                    error_msg, error_category = self._analyze_sandbox_failure(
                        process.returncode, stderr_str, stdout_str, execution_time, context
                    )
                    
                    return SandboxExecutionResult(
                        execution_id=context.execution_id,
                        success=False,
                        error=error_msg,
                        error_category=error_category,
                        stdout=stdout_str,
                        stderr=stderr_str,
                        execution_time=execution_time,
                        
                    )
                    
            finally:
                # Always cleanup the execution-specific temp directory
                try:
                    if os.path.exists(host_tmp_dir):
                        shutil.rmtree(host_tmp_dir)
                        logger.debug(f"Cleaned up execution temp directory: {host_tmp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory {host_tmp_dir}: {e}")
                
        except Exception as e:
            logger.error(f"Component runtime execution error: {e}")
            # Ensure cleanup even if an exception occurs
            try:
                if 'host_tmp_dir' in locals() and os.path.exists(host_tmp_dir):
                    shutil.rmtree(host_tmp_dir)
                    logger.debug(f"Emergency cleanup of temp directory: {host_tmp_dir}")
            except Exception as cleanup_error:
                logger.warning(f"Failed emergency cleanup of temp directory: {cleanup_error}")
            
            return SandboxExecutionResult(
                execution_id=context.execution_id,
                success=False,
                error=f"Runtime execution failed: {str(e)}",
                stdout="",
                stderr="",
                execution_time=0.0,
                
            )
    
    async def _run_in_nsjail(
        self,
        code: str,
        context: SandboxExecutionContext,
        profile,
        secrets_env: Optional[Dict[str, str]] = None,
    ) -> SandboxExecutionResult:
        """Execute code directly with nsjail using command line arguments (no config files)."""
        
        try:
            # This legacy direct execution path has been removed in favor of the executor-based path.
            raise RuntimeError("Direct -c execution path removed; use executor-based path")
            
            # Debug: Log the command being executed
            logger.debug(f"Executing nsjail command: {' '.join(nsjail_cmd[:10])}... (truncated)")
            logger.debug(f"Prepared code length: {len(prepared_code)} chars")
            
            # Execute nsjail with CLI args
            start_time = datetime.utcnow()
            process = await asyncio.create_subprocess_exec(
                *nsjail_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=context.timeout + 10
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Decode outputs
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""
            
            # Debug: Log the result
            logger.debug(f"nsjail execution completed: return_code={process.returncode}, time={execution_time:.2f}s")
            if stdout_str:
                logger.info(f"nsjail stdout: {stdout_str}")
            if stderr_str:
                # Split stderr to show nsjail info vs Python output separately
                stderr_lines = stderr_str.split('\n')
                nsjail_lines = [line for line in stderr_lines if line.startswith('[I]')]
                python_lines = [line for line in stderr_lines if not line.startswith('[I]') and line.strip()]
                
                if nsjail_lines:
                    logger.debug(f"nsjail info: {' '.join(nsjail_lines[:3])}...")  # First few lines only
                if python_lines:
                    logger.error(f"Python execution output: {' '.join(python_lines)}")
                else:
                    logger.warning("No Python output in stderr - Python may not be executing")
            
            # Return result with error analysis if failed
            if process.returncode == 0:
                return SandboxExecutionResult(
                    execution_id=context.execution_id,
                    success=True,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    execution_time=execution_time,
                    
                )
            else:
                # Analyze failure and provide meaningful error messages
                error_msg, error_category = self._analyze_sandbox_failure(
                    process.returncode, stderr_str, stdout_str, execution_time, context
                )
                
                return SandboxExecutionResult(
                    execution_id=context.execution_id,
                    success=False,
                    error=error_msg,
                    error_category=error_category,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    execution_time=execution_time,
                    
                )
                
        except Exception as e:
            logger.error(f"nsjail CLI execution error: {e}")
            return SandboxExecutionResult(
                execution_id=context.execution_id,
                success=False,
                stdout="",
                stderr=f"nsjail execution failed: {str(e)}",
                execution_time=0.0,
                
            )
    
    def _analyze_sandbox_failure(self, return_code: int, stderr: str, stdout: str, execution_time: float, context: SandboxExecutionContext) -> tuple[str, str]:
        """Analyze sandbox failure and return meaningful error message and category."""

        # First, check if we have enhanced error info from the executor
        if stdout:
            try:
                lines = stdout.strip().split('\n')
                for line in reversed(lines):
                    if line.strip().startswith('{'):
                        result_data = json.loads(line.strip())
                        if not result_data.get('success') and result_data.get('policy_hint'):
                            # We have a policy hint from the executor
                            error_msg = result_data.get('error', 'Unknown error')
                            policy_hint = result_data.get('policy_hint')
                            combined_msg = f"{error_msg}\n\nSandbox Policy Hint: {policy_hint}"
                            
                            # Determine category based on the error
                            if "multiprocessing" in error_msg.lower():
                                return (combined_msg, "multiprocessing_blocked")
                            elif "import" in error_msg.lower():
                                return (combined_msg, "import_blocked")
                            elif "permission" in error_msg.lower():
                                return (combined_msg, "permission_denied")
                            else:
                                return (combined_msg, "policy_violation")
                        break
            except:
                pass  # Fall through to standard analysis
        
        # Check for time limit first (before memory limit) since both can result in return code 137
        # Look for nsjail time limit messages in stderr
        time_limit_indicators = [
            "time limit",
            "run time >=",
            "killing it"
        ]
        
        if (return_code == 137 and any(indicator in stderr.lower() for indicator in time_limit_indicators)) or \
           return_code == 124 or execution_time >= context.timeout - 1:
            return (
                f"Component execution timed out after {context.timeout} seconds. "
                f"Consider optimizing performance or breaking down complex operations.",
                "cpu_timeout"
            )
        
        # Memory limit exceeded (check after time limit since both can be return code 137)
        if return_code == 137 or "killed" in stderr.lower() or "oom" in stderr.lower():
            return (
                f"Component execution exceeded memory limit ({context.max_memory_mb}MB). "
                f"Consider optimizing memory usage or reducing data size.",
                "memory_limit"
            )
        
        # Network restriction violations (seccomp policy)
        if "enetdown" in stderr.lower() or "network unreachable" in stderr.lower():
            return (
                "Network access blocked for untrusted component. "
                "Network calls are not allowed in UNTRUSTED mode for security.",
                "network_blocked"
            )
        
        # Import/package restrictions
        if "import" in stderr.lower() and ("not allowed" in stderr.lower() or "blocked" in stderr.lower()):
            return (
                f"Import restriction violation. Component tried to import blocked packages. "
                "import_blocked"
            )
        
        # Module not found errors
        if "modulenotfounderror" in stderr.lower() or "no module named" in stderr.lower():
            # Extract the actual module name from the error
            import_error_details = ""
            for line in stderr.split('\n'):
                if "no module named" in line.lower():
                    import_error_details = f"\nDetails: {line.strip()}"
                    break
            return (
                "Required Python package not found. "
                "The component requires dependencies that are not installed in the sandbox." +
                import_error_details,
                "missing_dependency"
            )
        
        # Sandbox policy compilation errors
        if "could not compile policy" in stderr.lower():
            return (
                "Sandbox security policy compilation failed. "
                "This is a system configuration issue that requires administrator attention.",
                "policy_error"
            )
        
        # File system access violations
        if "permission denied" in stderr.lower() and ("file" in stderr.lower() or "directory" in stderr.lower()):
            return (
                "File system access denied. "
                f"Component tried to access files outside allowed paths.",
                "file_access_denied"
            )
        
        # Syntax or runtime errors in component code
        if "syntaxerror" in stderr.lower():
            return (
                "Python syntax error in component code. "
                "Check component implementation for syntax issues.",
                "syntax_error"
            )
        
        # nsjail-specific failures
        if "nsjail" in stderr.lower():
            if "failed to parse" in stderr.lower():
                return (
                    "Sandbox configuration error. "
                    "Invalid nsjail configuration detected.",
                    "config_error"
                )
            elif "exec failed" in stderr.lower():
                return (
                    "Sandbox execution failed. "
                    "Could not execute Python interpreter in sandbox environment.",
                    "exec_error"
                )
        
        # Generic Python exceptions
        python_errors = ["traceback", "error:", "exception"]
        if any(err in stderr.lower() for err in python_errors):
            # Try to extract the actual error message
            lines = stderr.split('\n')
            error_lines = [line.strip() for line in lines if line.strip() and not line.startswith('[')]
            if error_lines:
                actual_error = error_lines[-1] if error_lines else "Unknown Python error"
                return (
                    f"Component execution failed with Python error: {actual_error}",
                    "python_error"
                )
        
        # Default case for unknown failures
        if return_code != 0:
            return (
                f"Component execution failed with exit code {return_code}. "
                f"Check component implementation and sandbox configuration.",
                "execution_failed"
            )
        
        # Success case but no result (shouldn't happen in error path)
        return (
            "Component execution completed but produced no result. "
            "This may indicate an issue with component output handling.",
            "no_result"
        )
    
    def _setup_sandbox_environment(self):
        """Set up secure sandbox chroot environment."""
        import os
        import stat
        # Get chroot path from the single sandbox profile
        chroot_path = self.security_policy.profile.nsjail_config.chroot
        if not chroot_path:
            return  # No chroot configured
        try:
            # Create the sandbox root directory with restricted permissions
            if not os.path.exists(chroot_path):
                os.makedirs(chroot_path, mode=0o755)
                logger.info(f"Created sandbox chroot directory: {chroot_path}")
            
            # Create basic directory structure inside chroot
            essential_dirs = [
                f"{chroot_path}/tmp",
                f"{chroot_path}/usr",
                f"{chroot_path}/usr/bin", 
                f"{chroot_path}/usr/lib",
                f"{chroot_path}/usr/local",
                f"{chroot_path}/usr/local/lib",
                f"{chroot_path}/lib",
                f"{chroot_path}/bin"
            ]
            
            for dir_path in essential_dirs:
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path, mode=0o755)
            
            # Copy essential binaries and create symlinks inside chroot
            try:
                # Create essential symlinks and device files
                essential_links = [
                    ("/usr/bin/python3", f"{chroot_path}/usr/bin/python3"),
                    ("/bin/sh", f"{chroot_path}/bin/sh"),
                ]
                
                for src, dst in essential_links:
                    if os.path.exists(src) and not os.path.exists(dst):
                        try:
                            # Try to create a hard link, fall back to copy
                            os.link(src, dst)
                        except (OSError, PermissionError):
                            try:
                                import shutil
                                shutil.copy2(src, dst)
                                os.chmod(dst, 0o755)
                            except Exception as e:
                                logger.debug(f"Could not link/copy {src}: {e}")
                
                # Create minimal /dev directory with essential device files
                dev_dir = f"{chroot_path}/dev"
                if not os.path.exists(dev_dir):
                    os.makedirs(dev_dir, mode=0o755)
                
                # Create essential device files if they don't exist
                essential_devs = [
                    (f"{chroot_path}/dev/null", 0o666),
                    (f"{chroot_path}/dev/zero", 0o666),
                ]
                
                for dev_path, mode in essential_devs:
                    if not os.path.exists(dev_path):
                        try:
                            # Create empty files that will be bind-mounted by nsjail
                            open(dev_path, 'a').close()
                            os.chmod(dev_path, mode)
                        except Exception as e:
                            logger.debug(f"Could not create {dev_path}: {e}")
                            
            except Exception as e:
                logger.debug(f"Error setting up sandbox essentials: {e}")
            
            # Ensure restrictive permissions on sandbox root
            os.chmod(chroot_path, 0o755)
            
            logger.info(f"Sandbox environment initialized at {chroot_path}")
            
        except Exception as e:
            logger.warning(f"Failed to set up sandbox environment at {chroot_path}: {e}")
            # Continue without chroot - less secure but functional
            if self.security_policy.profile.nsjail_config.chroot:
                self.security_policy.profile.nsjail_config.chroot = ""
            logger.warning("Disabled chroot due to setup failure - REDUCED SECURITY")
    

    


# Global singleton
_sandbox_manager: Optional[SandboxManager] = None

def get_sandbox_manager(db_session: Optional[Session] = None) -> SandboxManager:
    """Get the global sandbox manager instance."""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager(db_session=db_session)
    return _sandbox_manager