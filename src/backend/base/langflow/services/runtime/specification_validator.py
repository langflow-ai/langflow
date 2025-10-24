"""
Enhanced Validation Framework for Genesis Multi-Runtime Architecture.

This module provides comprehensive validation capabilities including type compatibility
checking, component relationship validation, and runtime-specific constraints.
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationType(Enum):
    """Types of validation checks."""
    STRUCTURE = "structure"
    COMPONENT_TYPE = "component_type"
    TYPE_COMPATIBILITY = "type_compatibility"
    RELATIONSHIP = "relationship"
    CONFIGURATION = "configuration"
    RUNTIME_SPECIFIC = "runtime_specific"


@dataclass
class ValidationIssue:
    """Represents a validation issue."""
    severity: ValidationSeverity
    validation_type: ValidationType
    component_id: Optional[str]
    field_name: Optional[str]
    message: str
    suggestion: Optional[str] = None
    code: Optional[str] = None


@dataclass
class ValidationResult:
    """Results of validation operation."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings_count: int = 0
    errors_count: int = 0

    def __post_init__(self):
        """Calculate counts after initialization."""
        self.warnings_count = len([i for i in self.issues if i.severity == ValidationSeverity.WARNING])
        self.errors_count = len([i for i in self.issues if i.severity == ValidationSeverity.ERROR])
        self.is_valid = self.errors_count == 0


class TypeCompatibilityMatrix:
    """
    Matrix for checking type compatibility between component inputs and outputs.
    """

    def __init__(self):
        """Initialize type compatibility matrix."""
        self.compatibility_rules = self._build_compatibility_matrix()

    def _build_compatibility_matrix(self) -> Dict[str, Set[str]]:
        """Build comprehensive type compatibility matrix."""
        return {
            # Message types can be used with multiple targets
            "Message": {
                "Message", "str", "Text", "any", "Any"
            },

            # Data types compatibility
            "Data": {
                "Data", "Dict", "dict", "Any", "any", "JSON", "DataFrame"
            },

            # Document types
            "Document": {
                "Document", "Data", "str", "Text", "any", "Any"
            },

            # Tool types
            "Tool": {
                "Tool", "any", "Any"
            },

            # DataFrame compatibility
            "DataFrame": {
                "DataFrame", "Data", "any", "Any", "List", "list"
            },

            # String/Text compatibility
            "str": {
                "str", "Text", "Message", "any", "Any"
            },
            "Text": {
                "Text", "str", "Message", "any", "Any"
            },

            # Prompt types
            "PromptComponent": {
                "PromptComponent", "Message", "str", "Text", "any", "Any"
            },

            # Vector types
            "Embeddings": {
                "Embeddings", "List", "list", "Data", "any", "Any"
            },

            # Universal compatibility
            "any": {
                "Message", "Data", "Document", "Tool", "DataFrame",
                "str", "Text", "PromptComponent", "Embeddings", "Any", "any"
            },
            "Any": {
                "Message", "Data", "Document", "Tool", "DataFrame",
                "str", "Text", "PromptComponent", "Embeddings", "Any", "any"
            }
        }

    def are_compatible(self, output_type: str, input_type: str) -> bool:
        """
        Check if output type is compatible with input type.

        Args:
            output_type: Type of output from source component
            input_type: Type expected by target component input

        Returns:
            True if types are compatible
        """
        # Exact match
        if output_type == input_type:
            return True

        # Check compatibility matrix
        compatible_types = self.compatibility_rules.get(output_type, set())
        return input_type in compatible_types

    def get_compatible_types(self, type_name: str) -> Set[str]:
        """Get all types compatible with given type."""
        return self.compatibility_rules.get(type_name, {type_name})


class EnhancedValidator:
    """
    Enhanced validator for Genesis specifications with comprehensive validation capabilities.
    """

    def __init__(self):
        """Initialize enhanced validator."""
        self.type_matrix = TypeCompatibilityMatrix()
        self._load_component_mappings()

    def _load_component_mappings(self):
        """Load component mappings for validation."""
        try:
            from langflow.services.genesis.mapper import ComponentMapper
            self.mapper = ComponentMapper()
        except ImportError as e:
            logger.warning(f"Could not load ComponentMapper: {e}")
            self.mapper = None

    def validate_specification(self, spec: Dict[str, Any],
                             runtime: str = "langflow") -> ValidationResult:
        """
        Perform comprehensive validation of Genesis specification.

        Args:
            spec: Genesis specification dictionary
            runtime: Target runtime for validation

        Returns:
            Comprehensive validation result
        """
        issues = []

        # Basic structure validation
        issues.extend(self._validate_structure(spec))

        # Component validation
        issues.extend(self._validate_components(spec))

        # Type compatibility validation
        issues.extend(self._validate_type_compatibility(spec))

        # Relationship validation
        issues.extend(self._validate_relationships(spec))

        # Configuration validation
        issues.extend(self._validate_configurations(spec))

        # Runtime-specific validation
        issues.extend(self._validate_runtime_constraints(spec, runtime))

        return ValidationResult(
            is_valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
            issues=issues
        )

    def _validate_structure(self, spec: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate basic specification structure."""
        issues = []

        # Required top-level fields
        required_fields = ["name", "description", "agentGoal", "components"]
        for field in required_fields:
            if field not in spec:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.STRUCTURE,
                    component_id=None,
                    field_name=field,
                    message=f"Required field '{field}' is missing",
                    suggestion=f"Add '{field}' field to specification",
                    code="MISSING_REQUIRED_FIELD"
                ))

        # Validate components structure
        if "components" in spec:
            components = spec["components"]
            if not isinstance(components, (dict, list)):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.STRUCTURE,
                    component_id=None,
                    field_name="components",
                    message="Components must be a dictionary or list",
                    suggestion="Use dictionary format for components",
                    code="INVALID_COMPONENTS_TYPE"
                ))
            elif isinstance(components, (dict, list)) and len(components) == 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.STRUCTURE,
                    component_id=None,
                    field_name="components",
                    message="At least one component is required",
                    suggestion="Add input, agent, and output components",
                    code="EMPTY_COMPONENTS"
                ))

        return issues

    def _validate_components(self, spec: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate individual components."""
        issues = []

        components = spec.get("components", {})
        if not components:
            return issues

        # Convert list to dict if needed
        if isinstance(components, list):
            component_dict = {f"component_{i}": comp for i, comp in enumerate(components)}
        else:
            component_dict = components

        for comp_id, component in component_dict.items():
            if not isinstance(component, dict):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.COMPONENT_TYPE,
                    component_id=comp_id,
                    field_name=None,
                    message=f"Component '{comp_id}' must be a dictionary",
                    code="INVALID_COMPONENT_TYPE"
                ))
                continue

            # Required component fields
            required_comp_fields = ["type"]
            for field in required_comp_fields:
                if field not in component:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.COMPONENT_TYPE,
                        component_id=comp_id,
                        field_name=field,
                        message=f"Component '{comp_id}' missing required field '{field}'",
                        suggestion=f"Add '{field}' field to component",
                        code="MISSING_COMPONENT_FIELD"
                    ))

            # Validate component type is supported
            comp_type = component.get("type")
            if comp_type and self.mapper:
                try:
                    mapping = self.mapper.map_component(comp_type)
                    if not mapping.get("component"):
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            validation_type=ValidationType.COMPONENT_TYPE,
                            component_id=comp_id,
                            field_name="type",
                            message=f"Component type '{comp_type}' may not have proper mapping",
                            suggestion="Check component type spelling or add mapping",
                            code="UNMAPPED_COMPONENT_TYPE"
                        ))
                except Exception:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        validation_type=ValidationType.COMPONENT_TYPE,
                        component_id=comp_id,
                        field_name="type",
                        message=f"Could not validate component type '{comp_type}'",
                        code="COMPONENT_TYPE_VALIDATION_FAILED"
                    ))

        return issues

    def _validate_type_compatibility(self, spec: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate type compatibility between connected components."""
        issues = []

        components = spec.get("components", {})
        if not components:
            return issues

        # Convert list to dict if needed
        if isinstance(components, list):
            component_dict = {comp.get("id", f"component_{i}"): comp
                            for i, comp in enumerate(components)}
        else:
            component_dict = components

        # Build component I/O mappings
        component_io = self._get_component_io_info(component_dict)

        # Check each provides relationship
        for comp_id, component in component_dict.items():
            # Skip if component is not a dictionary (validation error case)
            if not isinstance(component, dict):
                continue

            provides = component.get("provides", [])
            if not isinstance(provides, list):
                continue

            for provide in provides:
                if not isinstance(provide, dict):
                    continue

                target_id = provide.get("in")
                use_as = provide.get("useAs", "input")

                if not target_id:
                    continue

                # Get source output type
                source_io = component_io.get(comp_id, {})
                source_output_types = source_io.get("output_types", ["any"])

                # Get target input type
                target_io = component_io.get(target_id, {})
                target_input_types = target_io.get("input_types", ["any"])

                # Check if target field accepts this useAs
                if use_as == "tools":
                    # Tool connections - target should accept Tool type
                    expected_types = ["Tool", "any", "Any"]
                    if not any(self.type_matrix.are_compatible("Tool", target_type)
                              for target_type in target_input_types):
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            validation_type=ValidationType.TYPE_COMPATIBILITY,
                            component_id=comp_id,
                            field_name="provides",
                            message=f"Tool output from '{comp_id}' may not be compatible with '{target_id}' input types {target_input_types}",
                            suggestion="Ensure target component accepts Tool inputs",
                            code="TOOL_TYPE_MISMATCH"
                        ))
                else:
                    # Regular data connections
                    compatible = False
                    for source_type in source_output_types:
                        for target_type in target_input_types:
                            if self.type_matrix.are_compatible(source_type, target_type):
                                compatible = True
                                break
                        if compatible:
                            break

                    if not compatible:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            validation_type=ValidationType.TYPE_COMPATIBILITY,
                            component_id=comp_id,
                            field_name="provides",
                            message=f"Output types {source_output_types} from '{comp_id}' may not be compatible with input types {target_input_types} of '{target_id}'",
                            suggestion="Check component type compatibility",
                            code="TYPE_COMPATIBILITY_WARNING"
                        ))

        return issues

    def _validate_relationships(self, spec: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate component relationships and references."""
        issues = []

        components = spec.get("components", {})
        if not components:
            return issues

        # Convert list to dict if needed
        if isinstance(components, list):
            component_dict = {comp.get("id", f"component_{i}"): comp
                            for i, comp in enumerate(components)}
        else:
            component_dict = components

        component_ids = set(component_dict.keys())

        # Validate provides relationships
        for comp_id, component in component_dict.items():
            # Skip if component is not a dictionary (validation error case)
            if not isinstance(component, dict):
                continue

            provides = component.get("provides", [])
            if not isinstance(provides, list):
                continue

            for i, provide in enumerate(provides):
                if not isinstance(provide, dict):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.RELATIONSHIP,
                        component_id=comp_id,
                        field_name=f"provides[{i}]",
                        message=f"Provides entry {i} in '{comp_id}' must be a dictionary",
                        code="INVALID_PROVIDES_ENTRY"
                    ))
                    continue

                target_id = provide.get("in")
                if target_id and target_id not in component_ids:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.RELATIONSHIP,
                        component_id=comp_id,
                        field_name=f"provides[{i}].in",
                        message=f"Component '{comp_id}' provides to non-existent component '{target_id}'",
                        suggestion=f"Check component ID spelling or add component '{target_id}'",
                        code="INVALID_PROVIDES_TARGET"
                    ))

                use_as = provide.get("useAs")
                if not use_as:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        validation_type=ValidationType.RELATIONSHIP,
                        component_id=comp_id,
                        field_name=f"provides[{i}].useAs",
                        message=f"Missing 'useAs' field in provides entry {i} of '{comp_id}'",
                        suggestion="Add 'useAs' field (e.g., 'input', 'tools', 'prompt')",
                        code="MISSING_USE_AS"
                    ))

        # Check for workflow patterns
        self._validate_workflow_patterns(component_dict, issues)

        return issues

    def _validate_configurations(self, spec: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate component configurations."""
        issues = []

        components = spec.get("components", {})
        if not components:
            return issues

        # Convert list to dict if needed
        if isinstance(components, list):
            component_dict = {comp.get("id", f"component_{i}"): comp
                            for i, comp in enumerate(components)}
        else:
            component_dict = components

        for comp_id, component in component_dict.items():
            # Skip if component is not a dictionary (validation error case)
            if not isinstance(component, dict):
                continue

            config = component.get("config", {})
            comp_type = component.get("type")

            if config and not isinstance(config, dict):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.CONFIGURATION,
                    component_id=comp_id,
                    field_name="config",
                    message=f"Configuration for '{comp_id}' must be a dictionary",
                    code="INVALID_CONFIG_TYPE"
                ))
                continue

            # Tool mode validation
            as_tools = component.get("asTools", False)
            if as_tools:
                # Check if component type is suitable for tool mode
                if comp_type and self.mapper and self.mapper.is_tool_component(comp_type):
                    # Check if there are provides relationships with useAs: tools
                    provides = component.get("provides", [])
                    has_tool_provides = any(
                        p.get("useAs") == "tools" for p in provides if isinstance(p, dict)
                    )
                    if not has_tool_provides:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            validation_type=ValidationType.CONFIGURATION,
                            component_id=comp_id,
                            field_name="asTools",
                            message=f"Component '{comp_id}' has asTools=true but no 'useAs: tools' provides relationships",
                            suggestion="Add provides relationship with 'useAs: tools'",
                            code="MISSING_TOOL_PROVIDES"
                        ))
                else:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        validation_type=ValidationType.CONFIGURATION,
                        component_id=comp_id,
                        field_name="asTools",
                        message=f"Component type '{comp_type}' may not be suitable for tool mode",
                        suggestion="Use appropriate tool component types",
                        code="UNSUITABLE_TOOL_TYPE"
                    ))

        return issues

    def _validate_runtime_constraints(self, spec: Dict[str, Any], runtime: str) -> List[ValidationIssue]:
        """Validate runtime-specific constraints."""
        issues = []

        # Runtime-specific validations
        if runtime == "temporal":
            issues.extend(self._validate_temporal_constraints(spec))
        elif runtime == "kafka":
            issues.extend(self._validate_kafka_constraints(spec))
        elif runtime == "langflow":
            issues.extend(self._validate_langflow_constraints(spec))

        return issues

    def _validate_temporal_constraints(self, spec: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate Temporal-specific constraints."""
        issues = []

        # Temporal works best with stateful, long-running workflows
        run_mode = spec.get("runMode", "")
        if run_mode == "RealTime":
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                validation_type=ValidationType.RUNTIME_SPECIFIC,
                component_id=None,
                field_name="runMode",
                message="Real-time mode may not be optimal for Temporal runtime",
                suggestion="Consider 'Scheduled' or 'Batch' mode for Temporal workflows",
                code="TEMPORAL_REALTIME_WARNING"
            ))

        return issues

    def _validate_kafka_constraints(self, spec: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate Kafka-specific constraints."""
        issues = []

        # Kafka needs streaming-compatible components
        interaction_mode = spec.get("interactionMode", "")
        if interaction_mode not in ["Streaming", "RequestResponse"]:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                validation_type=ValidationType.RUNTIME_SPECIFIC,
                component_id=None,
                field_name="interactionMode",
                message="Kafka runtime works best with 'Streaming' interaction mode",
                suggestion="Consider setting interactionMode to 'Streaming'",
                code="KAFKA_INTERACTION_MODE"
            ))

        return issues

    def _validate_langflow_constraints(self, spec: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate Langflow-specific constraints."""
        issues = []

        # Langflow requires proper I/O flow
        components = spec.get("components", {})
        if isinstance(components, list):
            component_dict = {comp.get("id", f"component_{i}"): comp
                            for i, comp in enumerate(components)}
        else:
            component_dict = components

        # Check for input and output components
        has_input = any(
            comp.get("type", "").endswith("_input") or "input" in comp.get("type", "").lower()
            for comp in component_dict.values() if isinstance(comp, dict)
        )
        has_output = any(
            comp.get("type", "").endswith("_output") or "output" in comp.get("type", "").lower()
            for comp in component_dict.values() if isinstance(comp, dict)
        )

        if not has_input:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                validation_type=ValidationType.RUNTIME_SPECIFIC,
                component_id=None,
                field_name="components",
                message="No input component detected for Langflow workflow",
                suggestion="Add a chat_input or similar input component",
                code="LANGFLOW_MISSING_INPUT"
            ))

        if not has_output:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                validation_type=ValidationType.RUNTIME_SPECIFIC,
                component_id=None,
                field_name="components",
                message="No output component detected for Langflow workflow",
                suggestion="Add a chat_output or similar output component",
                code="LANGFLOW_MISSING_OUTPUT"
            ))

        return issues

    def _get_component_io_info(self, component_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Get I/O information for components."""
        component_io = {}

        if not self.mapper:
            return component_io

        for comp_id, component in component_dict.items():
            # Skip if component is not a dictionary (validation error case)
            if not isinstance(component, dict):
                continue

            comp_type = component.get("type")
            if not comp_type:
                continue

            try:
                mapping = self.mapper.map_component(comp_type)
                langflow_component = mapping.get("component")

                if langflow_component:
                    io_mapping = self.mapper.get_component_io_mapping(langflow_component)
                    component_io[comp_id] = io_mapping
                else:
                    # Default I/O for unknown components
                    component_io[comp_id] = {
                        "input_types": ["any"],
                        "output_types": ["any"]
                    }
            except Exception:
                component_io[comp_id] = {
                    "input_types": ["any"],
                    "output_types": ["any"]
                }

        return component_io

    def _validate_workflow_patterns(self, component_dict: Dict[str, Any], issues: List[ValidationIssue]):
        """Validate common workflow patterns."""
        # Check for circular dependencies
        dependencies = {}
        for comp_id, component in component_dict.items():
            # Skip if component is not a dictionary (validation error case)
            if not isinstance(component, dict):
                continue

            provides = component.get("provides", [])
            targets = [p.get("in") for p in provides if isinstance(p, dict) and p.get("in")]
            dependencies[comp_id] = targets

        # Simple cycle detection
        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in dependencies.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited = set()
        for comp_id in component_dict.keys():
            if comp_id not in visited:
                if has_cycle(comp_id, visited, set()):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.RELATIONSHIP,
                        component_id=comp_id,
                        field_name="provides",
                        message="Circular dependency detected in component relationships",
                        suggestion="Review provides relationships to eliminate cycles",
                        code="CIRCULAR_DEPENDENCY"
                    ))
                    break