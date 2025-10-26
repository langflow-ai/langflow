"""
Professional Variable Resolver for the Dynamic Agent Specification Framework.

This module provides comprehensive variable resolution and template substitution
capabilities for agent specifications with support for complex interpolation,
conditional logic, and secure variable handling.
"""

import logging
import re
from typing import Dict, Any, Optional, Union, List, Set, Type
from datetime import datetime
import json
import time

from ..models.error_models import (
    ErrorHandler, ErrorResult, ErrorCategory, ErrorSeverity, CommonErrorIds
)

logger = logging.getLogger(__name__)


class VariableResolver:
    """
    Professional variable resolver with advanced template substitution capabilities.

    This resolver provides:
    - Template variable substitution with ${variable} syntax
    - Nested variable resolution
    - Conditional variable substitution
    - Environment variable integration
    - Type-safe variable conversion
    - Circular dependency detection
    - Secure variable handling
    - Comprehensive error handling and validation
    """

    def __init__(self, allow_environment_variables: bool = False, max_depth: int = 10):
        """
        Initialize the variable resolver.

        Args:
            allow_environment_variables: Whether to allow environment variable substitution
            max_depth: Maximum recursion depth for nested variable resolution
        """
        self._service_name = "VariableResolver"
        self.error_handler = ErrorHandler(self._service_name)
        self.allow_environment_variables = allow_environment_variables
        self.max_depth = max_depth
        self.resolution_timeout = 30.0  # Maximum time for variable resolution

        # Compile regex patterns with error handling
        try:
            self.variable_pattern = re.compile(r'\$\{([^}]+)\}')
            self.conditional_pattern = re.compile(r'\$\{([^}]+)\?([^:]*):([^}]*)\}')
            self.environment_pattern = re.compile(r'\$\{env\.([^}]+)\}')
        except re.error as e:
            logger.error(f"Failed to compile regex patterns: {e}")
            raise ValueError(f"Variable resolver initialization failed: {e}")

        # Supported variable types for validation
        self.supported_types = {
            str, int, float, bool, list, dict, type(None)
        }

        # Maximum sizes to prevent memory issues
        self.max_string_length = 100000
        self.max_dict_depth = 20
        self.max_list_length = 10000

    def resolve_component_variables(self,
                                  config: Dict[str, Any],
                                  variables: Dict[str, Any]) -> Union[Dict[str, Any], ErrorResult]:
        """
        Resolve variables in component configuration.

        Args:
            config: Component configuration dictionary
            variables: Available variables for substitution

        Returns:
            Configuration with resolved variables or ErrorResult
        """
        start_time = time.time()

        try:
            # Validate inputs
            validation_result = self._validate_resolution_inputs(config, variables, "resolve_component_variables")
            if not validation_result.success:
                return validation_result

            logger.debug(f"Resolving variables in component config with {len(variables)} variables")

            # Create a safe copy to avoid modifying the original
            copy_result = self._safe_deep_copy(config)
            if isinstance(copy_result, ErrorResult):
                return copy_result
            resolved_config = copy_result

            # Resolve variables recursively with timeout protection
            resolution_result = self._resolve_dict_variables_safe(resolved_config, variables, depth=0, start_time=start_time)
            if isinstance(resolution_result, ErrorResult):
                return resolution_result

            logger.debug("Successfully resolved component variables")
            return resolution_result

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="resolve_component_variables",
                exception=e,
                error_id=CommonErrorIds.VARIABLE_RESOLUTION_FAILED,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.HIGH,
                suggested_fix="Check component configuration structure and variable definitions",
                retry_possible=True
            )
            return ErrorResult.error_result([error])

    def resolve_specification_variables(self,
                                      specification: Dict[str, Any],
                                      variables: Dict[str, Any]) -> Union[Dict[str, Any], ErrorResult]:
        """
        Resolve variables throughout an entire specification.

        Args:
            specification: Agent specification dictionary
            variables: Available variables for substitution

        Returns:
            Specification with resolved variables or ErrorResult
        """
        start_time = time.time()

        try:
            # Validate inputs
            validation_result = self._validate_resolution_inputs(specification, variables, "resolve_specification_variables")
            if not validation_result.success:
                return validation_result

            logger.debug(f"Resolving variables in specification with {len(variables)} variables")

            # Create a safe copy to avoid modifying the original
            copy_result = self._safe_deep_copy(specification)
            if isinstance(copy_result, ErrorResult):
                return copy_result
            resolved_spec = copy_result

            # Extract built-in variables from specification
            builtin_result = self._extract_builtin_variables_safe(resolved_spec)
            if isinstance(builtin_result, ErrorResult):
                return builtin_result
            builtin_variables = builtin_result

            all_variables = {**builtin_variables, **variables}

            # Resolve variables recursively with timeout protection
            resolution_result = self._resolve_dict_variables_safe(resolved_spec, all_variables, depth=0, start_time=start_time)
            if isinstance(resolution_result, ErrorResult):
                return resolution_result

            logger.debug("Successfully resolved specification variables")
            return resolution_result

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="resolve_specification_variables",
                exception=e,
                error_id=CommonErrorIds.VARIABLE_RESOLUTION_FAILED,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.HIGH,
                suggested_fix="Check specification structure and variable definitions",
                retry_possible=True
            )
            return ErrorResult.error_result([error])

    def validate_variables(self,
                         template_text: str,
                         available_variables: Dict[str, Any]) -> Union[Dict[str, List[str]], ErrorResult]:
        """
        Validate variable references in template text.

        Args:
            template_text: Text containing variable references
            available_variables: Variables available for substitution

        Returns:
            Dictionary with 'missing', 'circular', and 'invalid' variable lists or ErrorResult
        """
        try:
            # Validate inputs
            if not isinstance(template_text, str):
                error = self.error_handler.create_error(
                    operation="validate_variables",
                    error_id=CommonErrorIds.VARIABLE_TYPE_VALIDATION_FAILED,
                    message="Template text must be a string",
                    category=ErrorCategory.VALIDATION,
                    severity=ErrorSeverity.HIGH,
                    suggested_fix="Provide a valid string for template_text"
                )
                return ErrorResult.error_result([error])

            if not isinstance(available_variables, dict):
                error = self.error_handler.create_error(
                    operation="validate_variables",
                    error_id=CommonErrorIds.VARIABLE_TYPE_VALIDATION_FAILED,
                    message="Available variables must be a dictionary",
                    category=ErrorCategory.VALIDATION,
                    severity=ErrorSeverity.HIGH,
                    suggested_fix="Provide a valid dictionary for available_variables"
                )
                return ErrorResult.error_result([error])

            result = {
                "missing": [],
                "circular": [],
                "invalid": []
            }

            # Find all variable references with error handling
            refs_result = self._extract_variable_references_safe(template_text)
            if isinstance(refs_result, ErrorResult):
                return refs_result
            variable_refs = refs_result

            # Validate variable types
            type_validation_result = self._validate_variable_types(available_variables)
            if isinstance(type_validation_result, ErrorResult):
                return type_validation_result

            # Check for missing variables
            for var_ref in variable_refs:
                if var_ref not in available_variables:
                    # Check if it's an environment variable
                    if var_ref.startswith("env."):
                        if not self.allow_environment_variables:
                            result["invalid"].append(f"Environment variables not allowed: {var_ref}")
                    else:
                        result["missing"].append(var_ref)

            # Check for circular dependencies with error handling
            circular_result = self._detect_circular_dependencies_safe(template_text, available_variables)
            if isinstance(circular_result, ErrorResult):
                return circular_result
            result["circular"].extend(circular_result)

            return result

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="validate_variables",
                exception=e,
                error_id=CommonErrorIds.VARIABLE_TYPE_VALIDATION_FAILED,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.HIGH,
                retry_possible=False
            )
            return ErrorResult.error_result([error])

    def extract_variable_references(self, content: Union[str, Dict[str, Any], List[Any]]) -> Set[str]:
        """
        Extract all variable references from content.

        Args:
            content: Content to scan for variable references

        Returns:
            Set of variable reference names
        """
        variables = set()

        try:
            if isinstance(content, str):
                variables.update(self._extract_variable_references(content))
            elif isinstance(content, dict):
                for value in content.values():
                    variables.update(self.extract_variable_references(value))
            elif isinstance(content, list):
                for item in content:
                    variables.update(self.extract_variable_references(item))

        except Exception as e:
            logger.warning(f"Failed to extract variable references: {e}")

        return variables

    def create_variable_context(self,
                              base_variables: Dict[str, Any],
                              component_context: Optional[Dict[str, Any]] = None,
                              specification_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a comprehensive variable context for resolution.

        Args:
            base_variables: Base variables provided by user
            component_context: Component-specific context variables
            specification_context: Specification-specific context variables

        Returns:
            Combined variable context
        """
        context = {}

        try:
            # Add base variables
            context.update(base_variables)

            # Add specification context
            if specification_context:
                context.update(specification_context)

            # Add component context (highest priority)
            if component_context:
                context.update(component_context)

            # Add built-in variables
            builtin_vars = self._get_builtin_variables()
            # Only add builtin variables that don't override user variables
            for key, value in builtin_vars.items():
                if key not in context:
                    context[key] = value

            logger.debug(f"Created variable context with {len(context)} variables")
            return context

        except Exception as e:
            logger.error(f"Failed to create variable context: {e}")
            return base_variables

    def _resolve_dict_variables(self,
                              data: Dict[str, Any],
                              variables: Dict[str, Any],
                              depth: int) -> Dict[str, Any]:
        """Recursively resolve variables in a dictionary."""
        if depth >= self.max_depth:
            logger.warning(f"Maximum recursion depth ({self.max_depth}) reached in variable resolution")
            return data

        resolved = {}

        for key, value in data.items():
            try:
                if isinstance(value, str):
                    resolved[key] = self._resolve_string_variables(value, variables, depth + 1)
                elif isinstance(value, dict):
                    resolved[key] = self._resolve_dict_variables(value, variables, depth + 1)
                elif isinstance(value, list):
                    resolved[key] = self._resolve_list_variables(value, variables, depth + 1)
                else:
                    resolved[key] = value
            except Exception as e:
                logger.warning(f"Failed to resolve variable in key '{key}': {e}")
                resolved[key] = value  # Keep original value if resolution fails

        return resolved

    def _resolve_list_variables(self,
                              data: List[Any],
                              variables: Dict[str, Any],
                              depth: int) -> List[Any]:
        """Recursively resolve variables in a list."""
        if depth >= self.max_depth:
            return data

        resolved = []

        for item in data:
            try:
                if isinstance(item, str):
                    resolved.append(self._resolve_string_variables(item, variables, depth + 1))
                elif isinstance(item, dict):
                    resolved.append(self._resolve_dict_variables(item, variables, depth + 1))
                elif isinstance(item, list):
                    resolved.append(self._resolve_list_variables(item, variables, depth + 1))
                else:
                    resolved.append(item)
            except Exception as e:
                logger.warning(f"Failed to resolve variable in list item: {e}")
                resolved.append(item)  # Keep original item if resolution fails

        return resolved

    def _resolve_string_variables(self,
                                text: str,
                                variables: Dict[str, Any],
                                depth: int) -> Union[str, Any]:
        """Resolve variables in a string."""
        if depth >= self.max_depth:
            return text

        try:
            # Handle conditional variables first: ${var?true_value:false_value}
            text = self._resolve_conditional_variables(text, variables)

            # Handle environment variables if allowed
            if self.allow_environment_variables:
                text = self._resolve_environment_variables(text)

            # Handle regular variables: ${variable}
            def replace_variable(match):
                var_name = match.group(1).strip()

                # Handle nested object access (e.g., ${config.model})
                if '.' in var_name:
                    return str(self._resolve_nested_variable(var_name, variables))

                # Handle simple variable
                if var_name in variables:
                    value = variables[var_name]
                    # If the entire string is just a variable reference, return the actual value
                    if text.strip() == match.group(0):
                        return value
                    # Otherwise, convert to string for interpolation
                    return str(value)

                # Variable not found, keep original reference
                logger.debug(f"Variable '{var_name}' not found, keeping original reference")
                return match.group(0)

            resolved_text = self.variable_pattern.sub(replace_variable, text)

            # If the result is the same as input and contains unresolved variables,
            # it might need another pass for nested variables
            if resolved_text != text and self.variable_pattern.search(resolved_text) and depth < self.max_depth - 1:
                return self._resolve_string_variables(resolved_text, variables, depth + 1)

            # Check if the entire string was a single variable that should return the actual value
            if isinstance(resolved_text, str):
                single_var_match = re.match(r'^\$\{([^}]+)\}$', text)
                if single_var_match:
                    var_name = single_var_match.group(1).strip()
                    if var_name in variables:
                        return variables[var_name]

            return resolved_text

        except Exception as e:
            logger.warning(f"Failed to resolve string variables in '{text}': {e}")
            return text

    def _resolve_conditional_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """Resolve conditional variables with ternary operator syntax."""
        def replace_conditional(match):
            condition_var = match.group(1).strip()
            true_value = match.group(2)
            false_value = match.group(3)

            # Evaluate condition
            condition_result = False
            if condition_var in variables:
                value = variables[condition_var]
                # Evaluate truthiness
                if isinstance(value, bool):
                    condition_result = value
                elif isinstance(value, (int, float)):
                    condition_result = value != 0
                elif isinstance(value, str):
                    condition_result = value.lower() not in ['', 'false', '0', 'no', 'off']
                elif value is not None:
                    condition_result = True

            return true_value if condition_result else false_value

        return self.conditional_pattern.sub(replace_conditional, text)

    def _resolve_environment_variables(self, text: str) -> str:
        """Resolve environment variables."""
        import os

        def replace_env_var(match):
            env_var_name = match.group(1)
            env_value = os.environ.get(env_var_name)
            return env_value if env_value is not None else match.group(0)

        return self.environment_pattern.sub(replace_env_var, text)

    def _resolve_nested_variable(self, var_path: str, variables: Dict[str, Any]) -> Any:
        """Resolve nested variable access like 'config.model'."""
        parts = var_path.split('.')
        current = variables

        try:
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return f"${{{var_path}}}"  # Return original if path not found

            return current

        except Exception as e:
            logger.debug(f"Failed to resolve nested variable '{var_path}': {e}")
            return f"${{{var_path}}}"

    def _extract_variable_references(self, text: str) -> List[str]:
        """Extract variable reference names from text."""
        variables = []

        # Extract regular variables
        for match in self.variable_pattern.finditer(text):
            var_name = match.group(1).strip()
            variables.append(var_name)

        # Extract conditional variables
        for match in self.conditional_pattern.finditer(text):
            var_name = match.group(1).strip()
            variables.append(var_name)

        # Extract environment variables
        for match in self.environment_pattern.finditer(text):
            var_name = f"env.{match.group(1)}"
            variables.append(var_name)

        return variables

    def _detect_circular_dependencies(self,
                                    text: str,
                                    variables: Dict[str, Any]) -> List[str]:
        """Detect circular dependencies in variable references."""
        circular = []

        try:
            # Build dependency graph
            var_refs = self._extract_variable_references(text)
            dependencies = {}

            for var_ref in var_refs:
                if var_ref in variables:
                    value = variables[var_ref]
                    if isinstance(value, str):
                        dependencies[var_ref] = self._extract_variable_references(value)

            # Detect cycles using DFS
            def has_cycle(var, visited, rec_stack):
                visited.add(var)
                rec_stack.add(var)

                for dependency in dependencies.get(var, []):
                    if dependency not in visited:
                        if has_cycle(dependency, visited, rec_stack):
                            return True
                    elif dependency in rec_stack:
                        return True

                rec_stack.remove(var)
                return False

            visited = set()
            for var in dependencies:
                if var not in visited:
                    if has_cycle(var, visited, set()):
                        circular.append(var)

        except Exception as e:
            logger.warning(f"Failed to detect circular dependencies: {e}")

        return circular

    def _extract_builtin_variables(self, specification: Dict[str, Any]) -> Dict[str, Any]:
        """Extract built-in variables from specification metadata."""
        builtin = {}

        try:
            # Add specification metadata as variables
            builtin['spec_name'] = specification.get('name', '')
            builtin['spec_version'] = specification.get('version', '1.0.0')
            builtin['spec_domain'] = specification.get('domain', 'general')
            builtin['spec_kind'] = specification.get('kind', 'Single Agent')

            # Add component count
            components = specification.get('components', {})
            if isinstance(components, dict):
                builtin['component_count'] = len(components)
            elif isinstance(components, list):
                builtin['component_count'] = len(components)
            else:
                builtin['component_count'] = 0

        except Exception as e:
            logger.warning(f"Failed to extract builtin variables: {e}")

        return builtin

    def _get_builtin_variables(self) -> Dict[str, Any]:
        """Get system built-in variables."""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'time': datetime.utcnow().strftime('%H:%M:%S'),
            'framework_version': '2.0.0',
            'converter_name': 'SpecificationFramework'
        }

    def _deep_copy_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deep copy of a dictionary."""
        result = self._safe_deep_copy(data)
        if isinstance(result, ErrorResult):
            # Fallback for backward compatibility
            logger.warning("Safe deep copy failed, using fallback")
            return self._manual_deep_copy(data)
        return result

    def _manual_deep_copy(self, data: Any) -> Any:
        """Manual deep copy implementation."""
        if isinstance(data, dict):
            return {key: self._manual_deep_copy(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._manual_deep_copy(item) for item in data]
        else:
            return data  # For primitive types and non-serializable objects

    def _validate_resolution_inputs(self,
                                   data: Any,
                                   variables: Dict[str, Any],
                                   operation: str) -> ErrorResult:
        """Validate inputs for variable resolution operations."""
        errors = []

        if not isinstance(data, dict):
            error = self.error_handler.create_error(
                operation=operation,
                error_id=CommonErrorIds.VARIABLE_TYPE_VALIDATION_FAILED,
                message="Data must be a dictionary",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.CRITICAL,
                suggested_fix="Ensure data parameter is a dictionary"
            )
            errors.append(error)

        if not isinstance(variables, dict):
            error = self.error_handler.create_error(
                operation=operation,
                error_id=CommonErrorIds.VARIABLE_TYPE_VALIDATION_FAILED,
                message="Variables must be a dictionary",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.CRITICAL,
                suggested_fix="Ensure variables parameter is a dictionary"
            )
            errors.append(error)

        if errors:
            return ErrorResult.error_result(errors)

        return ErrorResult.success_result(None)

    def _safe_deep_copy(self, data: Any) -> Union[Any, ErrorResult]:
        """Create a safe deep copy with error handling."""
        try:
            # Check for reasonable size limits
            if isinstance(data, dict):
                if len(data) > 10000:  # Reasonable limit
                    error = self.error_handler.create_error(
                        operation="safe_deep_copy",
                        error_id="data_too_large",
                        message=f"Dictionary too large for safe copying: {len(data)} items",
                        category=ErrorCategory.PERFORMANCE,
                        severity=ErrorSeverity.MEDIUM,
                        suggested_fix="Reduce data size or use streaming processing"
                    )
                    return ErrorResult.error_result([error])

            # Use JSON serialization for deep copy (handles most cases)
            json_str = json.dumps(data, ensure_ascii=True)
            if len(json_str) > 1000000:  # 1MB limit
                error = self.error_handler.create_error(
                    operation="safe_deep_copy",
                    error_id="data_too_large",
                    message=f"Serialized data too large: {len(json_str)} bytes",
                    category=ErrorCategory.PERFORMANCE,
                    severity=ErrorSeverity.MEDIUM,
                    suggested_fix="Reduce data complexity"
                )
                return ErrorResult.error_result([error])

            return json.loads(json_str)

        except (TypeError, ValueError) as json_error:
            # Fallback to manual copy for non-serializable objects
            logger.debug(f"JSON copy failed, using manual copy: {json_error}")
            try:
                return self._manual_deep_copy(data)
            except Exception as manual_error:
                error = self.error_handler.handle_exception(
                    operation="safe_deep_copy",
                    exception=manual_error,
                    error_id="deep_copy_failed",
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.HIGH,
                    retry_possible=False
                )
                return ErrorResult.error_result([error])

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="safe_deep_copy",
                exception=e,
                error_id="deep_copy_failed",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.HIGH,
                retry_possible=False
            )
            return ErrorResult.error_result([error])

    def _resolve_dict_variables_safe(self,
                                   data: Dict[str, Any],
                                   variables: Dict[str, Any],
                                   depth: int,
                                   start_time: float) -> Union[Dict[str, Any], ErrorResult]:
        """Safely resolve variables in a dictionary with timeout and error handling."""
        try:
            # Check timeout
            if time.time() - start_time > self.resolution_timeout:
                error = self.error_handler.create_error(
                    operation="resolve_dict_variables_safe",
                    error_id="resolution_timeout",
                    message=f"Variable resolution timeout after {self.resolution_timeout}s",
                    category=ErrorCategory.PERFORMANCE,
                    severity=ErrorSeverity.HIGH,
                    suggested_fix="Simplify variable structure or increase timeout",
                    retry_possible=True
                )
                return ErrorResult.error_result([error])

            # Check depth limit
            if depth >= self.max_depth:
                error = self.error_handler.create_error(
                    operation="resolve_dict_variables_safe",
                    error_id=CommonErrorIds.VARIABLE_CIRCULAR_DEPENDENCY,
                    message=f"Maximum recursion depth ({self.max_depth}) reached",
                    category=ErrorCategory.VALIDATION,
                    severity=ErrorSeverity.HIGH,
                    field_path=f"depth_{depth}",
                    suggested_fix="Check for circular dependencies or reduce variable complexity"
                )
                return ErrorResult.error_result([error])

            resolved = {}

            for key, value in data.items():
                try:
                    # Validate key
                    if not isinstance(key, str):
                        error = self.error_handler.create_error(
                            operation="resolve_dict_variables_safe",
                            error_id=CommonErrorIds.VARIABLE_TYPE_VALIDATION_FAILED,
                            message=f"Dictionary key must be string, got {type(key)}",
                            category=ErrorCategory.VALIDATION,
                            severity=ErrorSeverity.MEDIUM,
                            field_path=str(key)
                        )
                        return ErrorResult.error_result([error])

                    if isinstance(value, str):
                        result = self._resolve_string_variables_safe(value, variables, depth + 1, start_time)
                        if isinstance(result, ErrorResult):
                            return result
                        resolved[key] = result
                    elif isinstance(value, dict):
                        result = self._resolve_dict_variables_safe(value, variables, depth + 1, start_time)
                        if isinstance(result, ErrorResult):
                            return result
                        resolved[key] = result
                    elif isinstance(value, list):
                        result = self._resolve_list_variables_safe(value, variables, depth + 1, start_time)
                        if isinstance(result, ErrorResult):
                            return result
                        resolved[key] = result
                    else:
                        # Validate value type
                        if not self._is_supported_type(value):
                            warning = self.error_handler.create_warning(
                                operation="resolve_dict_variables_safe",
                                warning_id="unsupported_value_type",
                                message=f"Unsupported value type {type(value)} for key '{key}'",
                                category=ErrorCategory.VALIDATION,
                                severity=ErrorSeverity.LOW,
                                field_path=key
                            )
                            # Continue with original value but log warning
                            logger.warning(warning.message)

                        resolved[key] = value

                except Exception as e:
                    error = self.error_handler.handle_exception(
                        operation="resolve_dict_variables_safe",
                        exception=e,
                        error_id=CommonErrorIds.VARIABLE_RESOLUTION_FAILED,
                        category=ErrorCategory.VALIDATION,
                        severity=ErrorSeverity.MEDIUM,
                        field_path=key,
                        retry_possible=False
                    )
                    # Try to continue with original value
                    resolved[key] = value
                    logger.warning(f"Failed to resolve variable in key '{key}': {e}")

            return resolved

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="resolve_dict_variables_safe",
                exception=e,
                error_id=CommonErrorIds.VARIABLE_RESOLUTION_FAILED,
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.HIGH,
                retry_possible=True
            )
            return ErrorResult.error_result([error])

    def _resolve_string_variables_safe(self,
                                     text: str,
                                     variables: Dict[str, Any],
                                     depth: int,
                                     start_time: float) -> Union[Union[str, Any], ErrorResult]:
        """Safely resolve variables in a string with error handling."""
        try:
            # Check timeout
            if time.time() - start_time > self.resolution_timeout:
                error = self.error_handler.create_error(
                    operation="resolve_string_variables_safe",
                    error_id="resolution_timeout",
                    message=f"Variable resolution timeout after {self.resolution_timeout}s",
                    category=ErrorCategory.PERFORMANCE,
                    severity=ErrorSeverity.HIGH
                )
                return ErrorResult.error_result([error])

            # Check string length limit
            if len(text) > self.max_string_length:
                error = self.error_handler.create_error(
                    operation="resolve_string_variables_safe",
                    error_id="string_too_large",
                    message=f"String too large for processing: {len(text)} characters",
                    category=ErrorCategory.PERFORMANCE,
                    severity=ErrorSeverity.MEDIUM,
                    suggested_fix="Reduce string size"
                )
                return ErrorResult.error_result([error])

            # Check depth limit
            if depth >= self.max_depth:
                return text

            # Use the original method with error wrapping
            try:
                return self._resolve_string_variables(text, variables, depth)
            except RecursionError:
                error = self.error_handler.create_error(
                    operation="resolve_string_variables_safe",
                    error_id=CommonErrorIds.VARIABLE_CIRCULAR_DEPENDENCY,
                    message="Recursion limit reached, possible circular dependency",
                    category=ErrorCategory.VALIDATION,
                    severity=ErrorSeverity.HIGH,
                    suggested_fix="Check for circular variable references"
                )
                return ErrorResult.error_result([error])

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="resolve_string_variables_safe",
                exception=e,
                error_id=CommonErrorIds.VARIABLE_RESOLUTION_FAILED,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                retry_possible=False
            )
            return ErrorResult.error_result([error])

    def _resolve_list_variables_safe(self,
                                   data: List[Any],
                                   variables: Dict[str, Any],
                                   depth: int,
                                   start_time: float) -> Union[List[Any], ErrorResult]:
        """Safely resolve variables in a list with error handling."""
        try:
            # Check timeout
            if time.time() - start_time > self.resolution_timeout:
                error = self.error_handler.create_error(
                    operation="resolve_list_variables_safe",
                    error_id="resolution_timeout",
                    message=f"Variable resolution timeout after {self.resolution_timeout}s",
                    category=ErrorCategory.PERFORMANCE,
                    severity=ErrorSeverity.HIGH
                )
                return ErrorResult.error_result([error])

            # Check depth and size limits
            if depth >= self.max_depth:
                return data  # Return original on depth limit

            if len(data) > self.max_list_length:
                error = self.error_handler.create_error(
                    operation="resolve_list_variables_safe",
                    error_id="list_too_large",
                    message=f"List too large for processing: {len(data)} items",
                    category=ErrorCategory.PERFORMANCE,
                    severity=ErrorSeverity.MEDIUM,
                    suggested_fix="Reduce list size or use streaming processing"
                )
                return ErrorResult.error_result([error])

            resolved = []

            for i, item in enumerate(data):
                try:
                    if isinstance(item, str):
                        result = self._resolve_string_variables_safe(item, variables, depth + 1, start_time)
                        if isinstance(result, ErrorResult):
                            # Continue with original item on error
                            resolved.append(item)
                            logger.warning(f"Failed to resolve variable in list item {i}")
                        else:
                            resolved.append(result)
                    elif isinstance(item, dict):
                        result = self._resolve_dict_variables_safe(item, variables, depth + 1, start_time)
                        if isinstance(result, ErrorResult):
                            resolved.append(item)
                            logger.warning(f"Failed to resolve variables in list item {i}")
                        else:
                            resolved.append(result)
                    elif isinstance(item, list):
                        result = self._resolve_list_variables_safe(item, variables, depth + 1, start_time)
                        if isinstance(result, ErrorResult):
                            resolved.append(item)
                            logger.warning(f"Failed to resolve variables in nested list item {i}")
                        else:
                            resolved.append(result)
                    else:
                        resolved.append(item)

                except Exception as e:
                    # Continue with original item on error
                    resolved.append(item)
                    logger.warning(f"Failed to resolve variable in list item {i}: {e}")

            return resolved

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="resolve_list_variables_safe",
                exception=e,
                error_id=CommonErrorIds.VARIABLE_RESOLUTION_FAILED,
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.HIGH,
                retry_possible=True
            )
            return ErrorResult.error_result([error])

    def _validate_variable_types(self, variables: Dict[str, Any]) -> Union[None, ErrorResult]:
        """Validate that all variables are of supported types."""
        errors = []

        for var_name, var_value in variables.items():
            if not self._is_supported_type(var_value):
                error = self.error_handler.create_error(
                    operation="validate_variable_types",
                    error_id=CommonErrorIds.VARIABLE_TYPE_VALIDATION_FAILED,
                    message=f"Unsupported variable type {type(var_value)} for variable '{var_name}'",
                    category=ErrorCategory.VALIDATION,
                    severity=ErrorSeverity.MEDIUM,
                    field_path=var_name,
                    suggested_fix=f"Use one of supported types: {', '.join(t.__name__ for t in self.supported_types)}"
                )
                errors.append(error)

        if errors:
            return ErrorResult.error_result(errors)

        return None

    def _is_supported_type(self, value: Any) -> bool:
        """Check if a value is of a supported type."""
        return type(value) in self.supported_types

    def _extract_variable_references_safe(self, text: str) -> Union[List[str], ErrorResult]:
        """Safely extract variable references with error handling."""
        try:
            return self._extract_variable_references(text)
        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="extract_variable_references_safe",
                exception=e,
                error_id=CommonErrorIds.VARIABLE_TEMPLATE_PARSING_FAILED,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                retry_possible=False
            )
            return ErrorResult.error_result([error])

    def _detect_circular_dependencies_safe(self,
                                         text: str,
                                         variables: Dict[str, Any]) -> Union[List[str], ErrorResult]:
        """Safely detect circular dependencies with error handling."""
        try:
            return self._detect_circular_dependencies(text, variables)
        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="detect_circular_dependencies_safe",
                exception=e,
                error_id=CommonErrorIds.VARIABLE_CIRCULAR_DEPENDENCY,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                retry_possible=False
            )
            return ErrorResult.error_result([error])

    def _extract_builtin_variables_safe(self, specification: Dict[str, Any]) -> Union[Dict[str, Any], ErrorResult]:
        """Safely extract built-in variables with error handling."""
        try:
            return self._extract_builtin_variables(specification)
        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="extract_builtin_variables_safe",
                exception=e,
                error_id="builtin_variables_extraction_failed",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.LOW,
                retry_possible=False,
                suggested_fix="Check specification structure"
            )
            return ErrorResult.error_result([error])