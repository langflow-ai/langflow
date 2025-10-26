"""
Professional Specification Validator for the Dynamic Agent Specification Framework.

This module provides comprehensive validation of YAML agent specifications including
structure validation, component validation, healthcare compliance, and business logic validation.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

from ..models.validation_models import ValidationResult, ValidationError, ValidationWarning
from ..services.component_discovery import SimplifiedComponentValidator

logger = logging.getLogger(__name__)


class SpecificationValidator:
    """
    Professional validator for agent specifications with comprehensive validation rules.

    This validator provides:
    - Structural validation of specification format
    - Component definition validation
    - Relationship and dependency validation
    - Healthcare compliance validation (HIPAA)
    - Business logic and naming convention validation
    - Performance and scalability validation
    """

    def __init__(self):
        """Initialize the specification validator."""
        self.component_validator = SimplifiedComponentValidator()
        self.required_fields = self._get_required_fields()
        self.healthcare_component_types = self._get_healthcare_component_types()

    async def validate_specification(self,
                                   specification: Dict[str, Any],
                                   enable_healthcare_compliance: bool = False) -> ValidationResult:
        """
        Perform comprehensive validation of an agent specification.

        Args:
            specification: Agent specification dictionary to validate
            enable_healthcare_compliance: Enable HIPAA compliance validation

        Returns:
            ValidationResult with validation status, errors, and warnings
        """
        validation_start = datetime.utcnow()
        errors = []
        warnings = []

        try:
            logger.debug("Starting comprehensive specification validation")

            # Phase 1: Basic structure validation
            structure_errors, structure_warnings = self._validate_specification_structure(specification)
            errors.extend(structure_errors)
            warnings.extend(structure_warnings)

            if structure_errors:
                # Don't continue if basic structure is invalid
                return ValidationResult.create_invalid(
                    errors, warnings, healthcare_compliance=enable_healthcare_compliance
                )

            # Phase 2: Component validation
            component_errors, component_warnings = await self._validate_components(specification)
            errors.extend(component_errors)
            warnings.extend(component_warnings)

            # Phase 3: Relationship validation
            relationship_errors, relationship_warnings = self._validate_component_relationships(specification)
            errors.extend(relationship_errors)
            warnings.extend(relationship_warnings)

            # Phase 4: Business logic validation
            business_errors, business_warnings = self._validate_business_logic(specification)
            errors.extend(business_errors)
            warnings.extend(business_warnings)

            # Phase 5: Healthcare compliance validation (if enabled)
            healthcare_compliant = True
            if enable_healthcare_compliance:
                healthcare_errors, healthcare_warnings, healthcare_compliant = self._validate_healthcare_compliance(
                    specification
                )
                errors.extend(healthcare_errors)
                warnings.extend(healthcare_warnings)

            # Phase 6: Performance and scalability validation
            performance_warnings = self._validate_performance_characteristics(specification)
            warnings.extend(performance_warnings)

            validation_time = (datetime.utcnow() - validation_start).total_seconds()
            is_valid = len(errors) == 0

            logger.info(f"Specification validation completed in {validation_time:.3f}s - Valid: {is_valid}")

            return ValidationResult(
                is_valid=is_valid,
                validation_errors=errors,
                warnings=warnings,
                healthcare_compliant=healthcare_compliant if enable_healthcare_compliance else None,
                validation_time_seconds=validation_time,
                components_validated=self._count_components(specification),
                relationships_validated=self._count_relationships(specification)
            )

        except Exception as e:
            error_message = f"Validation process failed: {str(e)}"
            logger.error(error_message, exc_info=True)

            return ValidationResult.create_invalid(
                [ValidationError(
                    error_type="validation_failure",
                    message=error_message,
                    field_path="root",
                    severity="critical"
                )],
                warnings,
                healthcare_compliance=enable_healthcare_compliance
            )

    def _validate_specification_structure(self, spec: Dict[str, Any]) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate the basic structure and required fields of the specification.

        Args:
            spec: Specification dictionary to validate

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        try:
            # Check if specification is a dictionary
            if not isinstance(spec, dict):
                errors.append(ValidationError(
                    error_type="structure",
                    message="Specification must be a dictionary",
                    field_path="root",
                    severity="critical"
                ))
                return errors, warnings

            # Validate required top-level fields
            for field in self.required_fields["top_level"]:
                if field not in spec:
                    errors.append(ValidationError(
                        error_type="missing_field",
                        message=f"Required field '{field}' is missing",
                        field_path=field,
                        severity="critical"
                    ))

            # Validate field types
            field_type_validations = {
                "name": str,
                "description": str,
                "agentGoal": str,
                "version": str,
                "domain": str,
                "kind": str
            }

            for field, expected_type in field_type_validations.items():
                if field in spec and not isinstance(spec[field], expected_type):
                    errors.append(ValidationError(
                        error_type="invalid_type",
                        message=f"Field '{field}' must be of type {expected_type.__name__}",
                        field_path=field,
                        severity="error"
                    ))

            # Validate specification ID format (if present)
            if "id" in spec:
                id_validation_error = self._validate_specification_id(spec["id"])
                if id_validation_error:
                    errors.append(id_validation_error)

            # Validate version format
            if "version" in spec:
                version_validation_error = self._validate_version_format(spec["version"])
                if version_validation_error:
                    errors.append(version_validation_error)

            # Check for deprecated fields
            deprecated_fields = ["mvp", "edge_generator", "legacy_mode"]
            for deprecated_field in deprecated_fields:
                if deprecated_field in spec:
                    warnings.append(ValidationWarning(
                        warning_type="deprecated_field",
                        message=f"Field '{deprecated_field}' is deprecated and should be removed",
                        field_path=deprecated_field,
                        severity="medium"
                    ))

        except Exception as e:
            errors.append(ValidationError(
                error_type="structure_validation_error",
                message=f"Structure validation failed: {str(e)}",
                field_path="root",
                severity="critical"
            ))

        return errors, warnings

    async def _validate_components(self, spec: Dict[str, Any]) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate all components in the specification.

        Args:
            spec: Specification dictionary

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        components = spec.get("components", {})

        # Validate components structure
        if not components:
            errors.append(ValidationError(
                error_type="missing_components",
                message="Specification must contain at least one component",
                field_path="components",
                severity="critical"
            ))
            return errors, warnings

        # Handle both dict and list component formats
        if isinstance(components, dict):
            component_items = components.items()
        elif isinstance(components, list):
            component_items = [(comp.get("id", f"component_{i}"), comp) for i, comp in enumerate(components)]
        else:
            errors.append(ValidationError(
                error_type="invalid_components_format",
                message="Components must be a dictionary or list",
                field_path="components",
                severity="critical"
            ))
            return errors, warnings

        # Validate individual components
        component_ids = set()
        for component_id, component_definition in component_items:
            comp_errors, comp_warnings = await self._validate_single_component(
                component_id, component_definition, f"components.{component_id}"
            )
            errors.extend(comp_errors)
            warnings.extend(comp_warnings)

            # Check for duplicate component IDs
            if component_id in component_ids:
                errors.append(ValidationError(
                    error_type="duplicate_component_id",
                    message=f"Duplicate component ID: {component_id}",
                    field_path=f"components.{component_id}",
                    severity="error"
                ))
            else:
                component_ids.add(component_id)

        return errors, warnings

    async def _validate_single_component(self,
                                 component_id: str,
                                 component: Dict[str, Any],
                                 field_path: str) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate a single component definition.

        Args:
            component_id: Component identifier
            component: Component definition dictionary
            field_path: JSON path to the component

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        # Validate component is a dictionary
        if not isinstance(component, dict):
            errors.append(ValidationError(
                error_type="invalid_component_format",
                message=f"Component {component_id} must be a dictionary",
                field_path=field_path,
                severity="error"
            ))
            return errors, warnings

        # Validate required component fields
        for field in self.required_fields["component"]:
            if field not in component:
                errors.append(ValidationError(
                    error_type="missing_component_field",
                    message=f"Component {component_id} missing required field: {field}",
                    field_path=f"{field_path}.{field}",
                    severity="error"
                ))

        # Validate component type using dynamic component validator
        component_type = component.get("type", "")
        if component_type:
            try:
                is_valid = await self.component_validator.validate_component(component_type)
                if not is_valid:
                    errors.append(ValidationError(
                        error_type="unsupported_component_type",
                        message=f"Unsupported component type: {component_type}",
                        field_path=f"{field_path}.type",
                        severity="error",
                        suggested_fix="Check available components in Langflow /all endpoint"
                    ))
            except Exception as e:
                logger.warning(f"Error validating component type {component_type}: {e}")
                warnings.append(ValidationWarning(
                    warning_type="component_validation_error",
                    message=f"Could not validate component type {component_type}: {e}",
                    field_path=f"{field_path}.type",
                    severity="medium"
                ))

        # Validate component name
        name = component.get("name", "")
        if name and not self._is_valid_component_name(name):
            warnings.append(ValidationWarning(
                warning_type="naming_convention",
                message=f"Component name '{name}' should follow naming conventions",
                field_path=f"{field_path}.name",
                severity="low",
                suggestion="Use descriptive names with spaces or hyphens"
            ))

        # Validate component kind
        kind = component.get("kind", "")
        valid_kinds = ["Agent", "Tool", "Data", "Prompt", "Model", "Memory", "Custom"]
        if kind and kind not in valid_kinds:
            warnings.append(ValidationWarning(
                warning_type="invalid_component_kind",
                message=f"Component kind '{kind}' is not standard",
                field_path=f"{field_path}.kind",
                severity="medium",
                suggestion=f"Use one of: {', '.join(valid_kinds)}"
            ))

        # Validate configuration
        config = component.get("config", {})
        if config and not isinstance(config, dict):
            errors.append(ValidationError(
                error_type="invalid_config_format",
                message=f"Component {component_id} config must be a dictionary",
                field_path=f"{field_path}.config",
                severity="error"
            ))

        # Validate provides relationships
        provides = component.get("provides", [])
        if provides:
            provides_errors, provides_warnings = self._validate_provides_relationships(
                component_id, provides, f"{field_path}.provides"
            )
            errors.extend(provides_errors)
            warnings.extend(provides_warnings)

        return errors, warnings

    def _validate_provides_relationships(self,
                                       component_id: str,
                                       provides: List[Dict[str, Any]],
                                       field_path: str) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate provides relationships for a component.

        Args:
            component_id: Component identifier
            provides: List of provides relationships
            field_path: JSON path to provides field

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        if not isinstance(provides, list):
            errors.append(ValidationError(
                error_type="invalid_provides_format",
                message=f"Component {component_id} provides must be a list",
                field_path=field_path,
                severity="error"
            ))
            return errors, warnings

        valid_use_as_types = [
            "tools", "input", "system_prompt", "prompt", "query", "memory",
            "output", "data", "context", "knowledge", "config"
        ]

        for i, provide in enumerate(provides):
            provide_path = f"{field_path}[{i}]"

            if not isinstance(provide, dict):
                errors.append(ValidationError(
                    error_type="invalid_provide_format",
                    message=f"Provide relationship {i} must be a dictionary",
                    field_path=provide_path,
                    severity="error"
                ))
                continue

            # Validate required provide fields
            if "useAs" not in provide:
                errors.append(ValidationError(
                    error_type="missing_use_as",
                    message=f"Provide relationship {i} missing 'useAs' field",
                    field_path=f"{provide_path}.useAs",
                    severity="error"
                ))

            if "in" not in provide:
                errors.append(ValidationError(
                    error_type="missing_target",
                    message=f"Provide relationship {i} missing 'in' field",
                    field_path=f"{provide_path}.in",
                    severity="error"
                ))

            # Validate useAs value
            use_as = provide.get("useAs", "")
            if use_as and use_as not in valid_use_as_types:
                warnings.append(ValidationWarning(
                    warning_type="non_standard_use_as",
                    message=f"Non-standard useAs value: {use_as}",
                    field_path=f"{provide_path}.useAs",
                    severity="medium",
                    suggestion=f"Consider using: {', '.join(valid_use_as_types[:5])}"
                ))

        return errors, warnings

    def _validate_component_relationships(self, spec: Dict[str, Any]) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate relationships between components.

        Args:
            spec: Specification dictionary

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        components = spec.get("components", {})

        # Build component ID set
        if isinstance(components, dict):
            component_ids = set(components.keys())
            components_dict = components
        elif isinstance(components, list):
            component_ids = set(comp.get("id", f"comp_{i}") for i, comp in enumerate(components))
            components_dict = {comp.get("id", f"comp_{i}"): comp for i, comp in enumerate(components)}
        else:
            return errors, warnings

        # Validate relationship targets exist
        for comp_id, component in components_dict.items():
            provides = component.get("provides", [])

            for i, provide in enumerate(provides):
                if not isinstance(provide, dict):
                    continue

                target_id = provide.get("in")
                if target_id and target_id not in component_ids:
                    errors.append(ValidationError(
                        error_type="invalid_relationship_target",
                        message=f"Component {comp_id} references non-existent component: {target_id}",
                        field_path=f"components.{comp_id}.provides[{i}].in",
                        severity="error"
                    ))

        # Check for circular dependencies
        circular_dependencies = self._detect_circular_dependencies(components_dict)
        for cycle in circular_dependencies:
            errors.append(ValidationError(
                error_type="circular_dependency",
                message=f"Circular dependency detected: {' -> '.join(cycle)}",
                field_path="components",
                severity="error"
            ))

        # Check for isolated components
        connected_components = self._find_connected_components(components_dict)
        if len(connected_components) > 1:
            warnings.append(ValidationWarning(
                warning_type="isolated_components",
                message=f"Specification contains {len(connected_components)} disconnected component groups",
                field_path="components",
                severity="medium",
                suggestion="Consider adding connections between component groups"
            ))

        return errors, warnings

    def _validate_business_logic(self, spec: Dict[str, Any]) -> Tuple[List[ValidationError], List[ValidationWarning]]:
        """
        Validate business logic and naming conventions.

        Args:
            spec: Specification dictionary

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        # Check for poor naming conventions
        poor_naming_terms = ["mvp", "temp", "test", "todo", "fixme", "hack", "edge_generator"]
        spec_name = spec.get("name", "").lower()

        for term in poor_naming_terms:
            if term in spec_name:
                warnings.append(ValidationWarning(
                    warning_type="poor_naming",
                    message=f"Specification name contains unprofessional term: '{term}'",
                    field_path="name",
                    severity="medium",
                    suggestion="Use professional, descriptive names"
                ))

        # Validate agent goal is meaningful
        agent_goal = spec.get("agentGoal", "")
        if len(agent_goal) < 10:
            warnings.append(ValidationWarning(
                warning_type="insufficient_agent_goal",
                message="Agent goal should be more descriptive",
                field_path="agentGoal",
                severity="low",
                suggestion="Provide a clear, detailed description of the agent's purpose"
            ))

        # Check for realistic component counts
        components = spec.get("components", {})
        component_count = len(components) if isinstance(components, (dict, list)) else 0

        if component_count > 50:
            warnings.append(ValidationWarning(
                warning_type="high_component_count",
                message=f"High component count ({component_count}) may impact performance",
                field_path="components",
                severity="medium",
                suggestion="Consider breaking into multiple specifications"
            ))

        return errors, warnings

    def _validate_healthcare_compliance(self, spec: Dict[str, Any]) -> Tuple[List[ValidationError], List[ValidationWarning], bool]:
        """
        Validate healthcare compliance (HIPAA) requirements.

        Args:
            spec: Specification dictionary

        Returns:
            Tuple of (errors, warnings, is_compliant)
        """
        errors = []
        warnings = []
        is_compliant = True

        components = spec.get("components", {})

        # Normalize components to dict format
        if isinstance(components, list):
            components_dict = {comp.get("id", f"comp_{i}"): comp for i, comp in enumerate(components)}
        else:
            components_dict = components

        # Check for healthcare-related components
        healthcare_components = []
        for comp_id, component in components_dict.items():
            component_type = component.get("type", "")
            if any(term in component_type for term in self.healthcare_component_types):
                healthcare_components.append((comp_id, component))

        if not healthcare_components:
            return errors, warnings, True  # No healthcare components, compliance not applicable

        # Validate healthcare components have proper configuration
        for comp_id, component in healthcare_components:
            config = component.get("config", {})

            # Check for PHI handling configuration
            if "phi_handling" not in config and "encryption" not in config:
                warnings.append(ValidationWarning(
                    warning_type="missing_phi_handling",
                    message=f"Healthcare component {comp_id} lacks PHI handling configuration",
                    field_path=f"components.{comp_id}.config",
                    severity="high",
                    suggestion="Add phi_handling or encryption configuration"
                ))

            # Check for audit logging
            if "audit_logging" not in config:
                warnings.append(ValidationWarning(
                    warning_type="missing_audit_logging",
                    message=f"Healthcare component {comp_id} lacks audit logging configuration",
                    field_path=f"components.{comp_id}.config",
                    severity="medium",
                    suggestion="Enable audit logging for compliance"
                ))

        # Check for data flow between healthcare and non-healthcare components
        for comp_id, component in components_dict.items():
            if comp_id not in [hc[0] for hc in healthcare_components]:
                provides = component.get("provides", [])
                for provide in provides:
                    target_id = provide.get("in", "")
                    if target_id in [hc[0] for hc in healthcare_components]:
                        warnings.append(ValidationWarning(
                            warning_type="phi_data_flow",
                            message=f"Non-healthcare component {comp_id} provides data to healthcare component {target_id}",
                            field_path=f"components.{comp_id}.provides",
                            severity="high",
                            suggestion="Ensure PHI data is properly handled in data flow"
                        ))

        return errors, warnings, len([w for w in warnings if w.severity == "high"]) == 0

    def _validate_performance_characteristics(self, spec: Dict[str, Any]) -> List[ValidationWarning]:
        """
        Validate performance and scalability characteristics.

        Args:
            spec: Specification dictionary

        Returns:
            List of performance warnings
        """
        warnings = []

        components = spec.get("components", {})
        component_count = len(components) if isinstance(components, (dict, list)) else 0

        # Normalize components for analysis
        if isinstance(components, list):
            components_dict = {comp.get("id", f"comp_{i}"): comp for i, comp in enumerate(components)}
        else:
            components_dict = components

        # Count relationships
        total_relationships = 0
        for component in components_dict.values():
            provides = component.get("provides", [])
            total_relationships += len(provides)

        # Performance warnings
        if total_relationships > 100:
            warnings.append(ValidationWarning(
                warning_type="high_relationship_count",
                message=f"High relationship count ({total_relationships}) may impact conversion performance",
                field_path="components",
                severity="medium",
                suggestion="Consider optimizing component relationships"
            ))

        # Check for potential memory-intensive components
        memory_intensive_types = ["genesis:embedding", "genesis:vector_store", "genesis:large_model"]
        memory_intensive_count = 0

        for component in components_dict.values():
            component_type = component.get("type", "")
            if any(term in component_type for term in memory_intensive_types):
                memory_intensive_count += 1

        if memory_intensive_count > 3:
            warnings.append(ValidationWarning(
                warning_type="high_memory_usage",
                message=f"Multiple memory-intensive components ({memory_intensive_count}) detected",
                field_path="components",
                severity="medium",
                suggestion="Monitor memory usage during execution"
            ))

        return warnings


    def _get_required_fields(self) -> Dict[str, List[str]]:
        """Get required fields for different specification sections."""
        return {
            "top_level": ["name", "description", "agentGoal", "components"],
            "component": ["type"]
        }

    def _get_healthcare_component_types(self) -> Set[str]:
        """Get healthcare-related component type identifiers."""
        return {
            "ehr", "eligibility", "claims", "medical", "patient", "phi", "hipaa",
            "pharmacy", "healthcare", "clinical", "diagnosis", "treatment"
        }

    def _validate_specification_id(self, spec_id: str) -> Optional[ValidationError]:
        """Validate specification ID format."""
        # URN format: urn:agent:genesis:{domain}:{name}:{version}
        urn_pattern = r"^urn:agent:genesis:[a-z0-9\-]+:[a-z0-9\-]+:[0-9]+\.[0-9]+\.[0-9]+$"

        if not re.match(urn_pattern, spec_id):
            return ValidationError(
                error_type="invalid_id_format",
                message="Specification ID must follow URN format: urn:agent:genesis:{domain}:{name}:{version}",
                field_path="id",
                severity="error",
                suggested_fix="Use format: urn:agent:genesis:domain:name:1.0.0"
            )

        return None

    def _validate_version_format(self, version: str) -> Optional[ValidationError]:
        """Validate version format (semantic versioning)."""
        semver_pattern = r"^[0-9]+\.[0-9]+\.[0-9]+$"

        if not re.match(semver_pattern, version):
            return ValidationError(
                error_type="invalid_version_format",
                message="Version must follow semantic versioning format (e.g., 1.0.0)",
                field_path="version",
                severity="error",
                suggested_fix="Use format: major.minor.patch (e.g., 1.0.0)"
            )

        return None

    def _is_valid_component_name(self, name: str) -> bool:
        """Check if component name follows naming conventions."""
        # Allow letters, numbers, spaces, hyphens, and underscores
        # Avoid poor terms
        poor_terms = ["mvp", "temp", "test", "todo", "fixme", "hack"]
        name_lower = name.lower()

        return (
            bool(re.match(r"^[a-zA-Z0-9\s\-_]+$", name)) and
            len(name) > 2 and
            not any(term in name_lower for term in poor_terms)
        )

    def _detect_circular_dependencies(self, components: Dict[str, Any]) -> List[List[str]]:
        """Detect circular dependencies in component relationships."""
        # Build adjacency list
        graph = {}
        for comp_id, component in components.items():
            graph[comp_id] = []
            provides = component.get("provides", [])
            for provide in provides:
                # Handle both string and dict formats for provides
                if isinstance(provide, str):
                    # Simple string format - no explicit target, skip for circular dependency check
                    continue
                elif isinstance(provide, dict):
                    target_id = provide.get("in")
                    if target_id:
                        graph[comp_id].append(target_id)

        # DFS to detect cycles
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node):
            if node in rec_stack:
                # Found cycle
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor in components:  # Only follow valid components
                    dfs(neighbor)

            rec_stack.remove(node)
            path.pop()

        for comp_id in components:
            if comp_id not in visited:
                dfs(comp_id)

        return cycles

    def _find_connected_components(self, components: Dict[str, Any]) -> List[Set[str]]:
        """Find connected component groups."""
        # Build undirected graph
        graph = {comp_id: set() for comp_id in components}

        for comp_id, component in components.items():
            provides = component.get("provides", [])
            for provide in provides:
                # Handle both string and dict formats for provides
                if isinstance(provide, str):
                    # Simple string format - no explicit target, skip for connected components check
                    continue
                elif isinstance(provide, dict):
                    target_id = provide.get("in")
                    if target_id and target_id in components:
                        graph[comp_id].add(target_id)
                        graph[target_id].add(comp_id)

        # Find connected components using DFS
        visited = set()
        connected_groups = []

        def dfs(node, group):
            if node in visited:
                return
            visited.add(node)
            group.add(node)
            for neighbor in graph[node]:
                dfs(neighbor, group)

        for comp_id in components:
            if comp_id not in visited:
                group = set()
                dfs(comp_id, group)
                connected_groups.append(group)

        return connected_groups

    def _count_components(self, spec: Dict[str, Any]) -> int:
        """Count total components in specification."""
        components = spec.get("components", {})
        if isinstance(components, dict):
            return len(components)
        elif isinstance(components, list):
            return len(components)
        else:
            return 0

    # Removed duplicate method - using the original _validate_healthcare_compliance above

    def _count_relationships(self, spec: Dict[str, Any]) -> int:
        """Count total relationships in specification."""
        components = spec.get("components", {})
        total_relationships = 0

        if isinstance(components, dict):
            components_list = list(components.values())
        elif isinstance(components, list):
            components_list = components
        else:
            return 0

        for component in components_list:
            if isinstance(component, dict):
                provides = component.get("provides", [])
                total_relationships += len(provides)

        return total_relationships