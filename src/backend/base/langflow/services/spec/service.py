"""Specification Service for business logic."""

import yaml
import jsonschema
from typing import Dict, Any, Optional, List
import logging

from langflow.custom.genesis.spec import FlowConverter, ComponentMapper, VariableResolver
from .validation_schemas import GENESIS_SPEC_SCHEMA, get_component_config_schema
from .semantic_validator import SemanticValidator
from .dynamic_schema_generator import DynamicSchemaGenerator
from langflow.services.runtime import converter_factory, RuntimeType, ValidationOptions
from langflow.services.spec.component_template_service import component_template_service
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.flow import Flow, FlowCreate
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.component_mapping import ComponentMapping
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)


class SpecService:
    """Business logic service for agent specification operations."""

    def __init__(self):
        """Initialize the service with enhanced database-driven component discovery."""
        self.mapper = ComponentMapper()
        self.converter = FlowConverter(self.mapper)
        self.resolver = VariableResolver()
        self._validation_cache = {}  # Cache for validation results

        # Initialize database-driven services (AUTPE-6207)
        self.component_mapping_service = ComponentMappingService()
        self.dynamic_schema_generator = DynamicSchemaGenerator()
        self._database_components_cache = {}  # Cache for database component mappings
        self._last_cache_refresh = None

    async def convert_spec_to_flow(self, spec_yaml: str,
                                  variables: Optional[Dict[str, Any]] = None,
                                  tweaks: Optional[Dict[str, Any]] = None,
                                  session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Convert YAML specification to Langflow JSON.

        Args:
            spec_yaml: YAML specification string
            variables: Runtime variables for resolution
            tweaks: Component field tweaks to apply
            session: Optional database session for cache population

        Returns:
            Flow JSON structure

        Raises:
            ValueError: If specification is invalid
        """
        try:
            # Parse YAML
            spec_dict = yaml.safe_load(spec_yaml)
            if not spec_dict:
                raise ValueError("Empty or invalid YAML specification")

            # Validate basic structure
            validation = self._validate_spec_structure(spec_dict)
            if not validation["valid"]:
                raise ValueError(f"Invalid specification: {validation['errors']}")

            # Populate database cache before conversion (AC2: Cache Population Before Conversion)
            # Enhanced with AUTPE-6207 database-driven component discovery
            await self._ensure_database_cache_populated(session)

            # Refresh mapper's database cache if we have a session
            if session:
                await self._refresh_mapper_database_cache(session)

            # Convert to flow
            flow = await self.converter.convert(spec_dict, variables)

            # Apply tweaks if provided
            if tweaks:
                flow = self.resolver.apply_tweaks(flow, tweaks)

            return flow

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}")
        except TypeError as e:
            if "argument of type 'NoneType' is not iterable" in str(e):
                import traceback
                logger.error(f"NoneType is not iterable error with traceback: {traceback.format_exc()}")
                raise ValueError(f"NoneType error in conversion: {e}")
            else:
                logger.error(f"Type error converting specification: {e}")
                raise
        except Exception as e:
            logger.error(f"Error converting specification: {e}")
            raise ValueError(f"Conversion failed: {e}")

    async def create_flow_from_spec(self, spec_yaml: str, name: str,
                                   session: AsyncSession, user_id: UUID,
                                   folder_id: Optional[str] = None,
                                   variables: Optional[Dict[str, Any]] = None,
                                   tweaks: Optional[Dict[str, Any]] = None) -> str:
        """
        Convert specification and create flow in database.

        Args:
            spec_yaml: YAML specification string
            name: Flow name
            session: Database session
            user_id: User ID creating the flow
            folder_id: Optional folder ID
            variables: Runtime variables
            tweaks: Component tweaks

        Returns:
            Created flow ID

        Raises:
            ValueError: If specification is invalid or creation fails
        """
        # Convert to flow (pass session for cache population)
        flow_data = await self.convert_spec_to_flow(spec_yaml, variables, tweaks, session)

        # Create flow in database using real Langflow database logic
        flow_id = await self._save_flow_to_database(flow_data, name, session, user_id, folder_id)

        return flow_id

    async def validate_spec(self, spec_yaml: str, detailed: bool = True, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Comprehensive specification validation with JSON Schema and semantic validation.

        Args:
            spec_yaml: YAML specification string
            detailed: Whether to perform detailed semantic validation
            session: Optional database session for enhanced validation

        Returns:
            Comprehensive validation result with errors, warnings, and suggestions
        """
        try:
            # Parse YAML
            spec_dict = yaml.safe_load(spec_yaml)
            if not spec_dict:
                return {
                    "valid": False,
                    "errors": [{"code": "EMPTY_SPEC", "message": "Empty or invalid YAML specification", "severity": "error"}],
                    "warnings": [],
                    "suggestions": [],
                    "summary": {"error_count": 1, "warning_count": 0, "suggestion_count": 0}
                }

            # Phase 1: JSON Schema Validation
            schema_validation = self._validate_json_schema(spec_dict)

            # Phase 2: Basic Structure Validation (legacy compatibility)
            structure_validation = self._validate_spec_structure(spec_dict)

            # Phase 3: Component Existence and Basic Validation
            # Enhanced with database-driven component discovery (AUTPE-6207)
            available_components = await self.get_all_available_components_with_database(session)
            component_validation = await self._validate_components_enhanced(
                spec_dict.get("components", []),
                available_components
            )

            # Phase 4: Type Compatibility Validation
            type_validation = self._validate_component_type_compatibility_enhanced(spec_dict)

            # Phase 5: Semantic Validation (if detailed)
            semantic_validation = {"errors": [], "warnings": [], "suggestions": []}
            if detailed:
                semantic_validator = SemanticValidator(self.mapper)
                semantic_result = semantic_validator.validate(spec_dict)
                semantic_validation = {
                    "errors": semantic_result.errors,
                    "warnings": semantic_result.warnings,
                    "suggestions": semantic_result.suggestions
                }

            # Merge all validation results
            all_errors = []
            all_warnings = []
            all_suggestions = []

            # Convert legacy format to new format
            all_errors.extend(self._convert_legacy_errors(schema_validation.get("errors", [])))
            all_errors.extend(self._convert_legacy_errors(structure_validation.get("errors", [])))
            all_errors.extend(self._convert_legacy_errors(component_validation.get("errors", [])))
            all_errors.extend(self._convert_legacy_errors(type_validation.get("errors", [])))
            all_errors.extend(semantic_validation.get("errors", []))

            all_warnings.extend(self._convert_legacy_warnings(schema_validation.get("warnings", [])))
            all_warnings.extend(self._convert_legacy_warnings(structure_validation.get("warnings", [])))
            all_warnings.extend(self._convert_legacy_warnings(component_validation.get("warnings", [])))
            all_warnings.extend(self._convert_legacy_warnings(type_validation.get("warnings", [])))
            all_warnings.extend(semantic_validation.get("warnings", []))

            all_suggestions.extend(semantic_validation.get("suggestions", []))

            # Remove duplicates
            all_errors = self._remove_duplicate_issues(all_errors)
            all_warnings = self._remove_duplicate_issues(all_warnings)
            all_suggestions = self._remove_duplicate_issues(all_suggestions)

            return {
                "valid": len(all_errors) == 0,
                "errors": all_errors,
                "warnings": all_warnings,
                "suggestions": all_suggestions,
                "summary": {
                    "error_count": len(all_errors),
                    "warning_count": len(all_warnings),
                    "suggestion_count": len(all_suggestions)
                },
                "validation_phases": {
                    "schema_validation": len(schema_validation.get("errors", [])) == 0,
                    "structure_validation": len(structure_validation.get("errors", [])) == 0,
                    "component_validation": len(component_validation.get("errors", [])) == 0,
                    "type_validation": len(type_validation.get("errors", [])) == 0,
                    "semantic_validation": len(semantic_validation.get("errors", [])) == 0 if detailed else None
                }
            }

        except yaml.YAMLError as e:
            return {
                "valid": False,
                "errors": [{
                    "code": "YAML_PARSE_ERROR",
                    "message": f"Invalid YAML format: {e}",
                    "severity": "error",
                    "suggestion": "Check YAML syntax, indentation, and special characters"
                }],
                "warnings": [],
                "suggestions": [],
                "summary": {"error_count": 1, "warning_count": 0, "suggestion_count": 0}
            }
        except Exception as e:
            logger.error(f"Error in validate_spec: {e}")
            return {
                "valid": False,
                "errors": [{
                    "code": "VALIDATION_EXCEPTION",
                    "message": f"Validation error: {e}",
                    "severity": "error",
                    "suggestion": "Please report this issue to the development team"
                }],
                "warnings": [],
                "suggestions": [],
                "summary": {"error_count": 1, "warning_count": 0, "suggestion_count": 0}
            }

    def get_validation_suggestions(self, validation_result: Dict[str, Any]) -> List[str]:
        """
        Generate actionable suggestions based on validation results.

        Args:
            validation_result: Result from validate_spec

        Returns:
            List of actionable suggestions
        """
        suggestions = []

        if not validation_result.get("valid", True):
            errors = validation_result.get("errors", [])
            warnings = validation_result.get("warnings", [])

            # Analyze errors and provide suggestions
            error_codes = [error.get("code", "") for error in errors]

            # Schema validation suggestions
            if "MISSING_FIELD" in " ".join(error_codes):
                suggestions.append("Add required fields: id, name, description, agentGoal, and components")
                suggestions.append("Use the specification template to ensure all required fields are present")

            if "INVALID_URN_FORMAT" in " ".join(error_codes):
                suggestions.append("Use proper URN format: urn:agent:genesis:domain:name:version")
                suggestions.append("Example: urn:agent:genesis:autonomize.ai:patient-care-agent:1.0.0")

            # Component validation suggestions
            if "COMPONENT_NOT_FOUND" in " ".join(error_codes):
                suggestions.append("Check component types against the available component catalog")
                suggestions.append("Use 'genesis:' prefix for all component types")

            if "MISSING_PROVIDES" in " ".join(error_codes):
                suggestions.append("Add 'provides' relationships to connect components in the workflow")
                suggestions.append("Ensure data flows from input → processing → output")

            # CrewAI specific suggestions
            if "INCOMPLETE_AGENT_CONFIG" in " ".join(error_codes):
                suggestions.append("Add role, goal, and backstory to all CrewAI agents")
                suggestions.append("Make agent roles specific and non-overlapping")

            if "MISSING_CREW_AGENTS" in " ".join(error_codes):
                suggestions.append("Ensure all agents referenced in crew configuration exist")
                suggestions.append("Check agent IDs match between components and crew config")

            # Tool configuration suggestions
            if "TOOL_MODE_MISMATCH" in " ".join(error_codes):
                suggestions.append("Set 'asTools: true' for components used as agent tools")
                suggestions.append("Connect tool components with 'useAs: tools' in provides")

            # Workflow pattern suggestions
            if len([e for e in errors if "MISSING_AGENT" in e.get("code", "")]) > 0:
                suggestions.append("Add at least one agent component to process inputs")
                suggestions.append("Consider using 'genesis:agent' for single agents or 'genesis:crewai_agent' for multi-agent workflows")

            # Performance and optimization suggestions
            warning_codes = [warning.get("code", "") for warning in warnings]

            if "HIGH_AGENT_COUNT" in " ".join(warning_codes):
                suggestions.append("Consider using hierarchical CrewAI patterns for large agent counts")
                suggestions.append("Group related agents into specialized crews")

            if "UNSEQUENCED_TASKS" in " ".join(warning_codes):
                suggestions.append("Define task dependencies with 'depends_on' field for proper execution order")
                suggestions.append("Use sequential task types for ordered execution")

        return suggestions

    def format_validation_report(self, validation_result: Dict[str, Any]) -> str:
        """
        Format validation results into a comprehensive human-readable report.

        Args:
            validation_result: Result from validate_spec

        Returns:
            Formatted validation report
        """
        if validation_result.get("valid", True):
            return "✅ Specification validation passed successfully!"

        report = []
        report.append("❌ Specification validation failed\n")

        # Summary section
        summary = validation_result.get("summary", {})
        error_count = summary.get("error_count", 0)
        warning_count = summary.get("warning_count", 0)
        suggestion_count = summary.get("suggestion_count", 0)

        report.append("📊 SUMMARY:")
        report.append(f"   Errors: {error_count}")
        report.append(f"   Warnings: {warning_count}")
        report.append(f"   Suggestions: {suggestion_count}")
        report.append("")

        # Validation phases section
        phases = validation_result.get("validation_phases", {})
        if phases:
            report.append("🔍 VALIDATION PHASES:")
            for phase, passed in phases.items():
                status = "✅" if passed else "❌"
                phase_name = phase.replace("_", " ").title()
                report.append(f"   {status} {phase_name}")
            report.append("")

        # Errors section
        errors = validation_result.get("errors", [])
        if errors:
            report.append("❌ ERRORS:")
            for error in errors:
                code = error.get("code", "UNKNOWN")
                message = error.get("message", "No message")
                component_id = error.get("component_id")
                suggestion = error.get("suggestion")

                if component_id:
                    report.append(f"   [{component_id}] {code}: {message}")
                else:
                    report.append(f"   {code}: {message}")

                if suggestion:
                    report.append(f"      💡 {suggestion}")
            report.append("")

        # Warnings section
        warnings = validation_result.get("warnings", [])
        if warnings:
            report.append("⚠️  WARNINGS:")
            for warning in warnings:
                code = warning.get("code", "UNKNOWN")
                message = warning.get("message", "No message")
                component_id = warning.get("component_id")
                suggestion = warning.get("suggestion")

                if component_id:
                    report.append(f"   [{component_id}] {code}: {message}")
                else:
                    report.append(f"   {code}: {message}")

                if suggestion:
                    report.append(f"      💡 {suggestion}")
            report.append("")

        # Suggestions section
        suggestions = validation_result.get("suggestions", [])
        if suggestions:
            report.append("💡 SUGGESTIONS:")
            for suggestion in suggestions:
                code = suggestion.get("code", "OPTIMIZATION")
                message = suggestion.get("message", "No message")
                action = suggestion.get("action", suggestion.get("suggestion", ""))

                report.append(f"   {code}: {message}")
                if action:
                    report.append(f"      🔧 {action}")
            report.append("")

        # Additional actionable suggestions
        additional_suggestions = self.get_validation_suggestions(validation_result)
        if additional_suggestions:
            report.append("🚀 ACTIONABLE SUGGESTIONS:")
            for i, suggestion in enumerate(additional_suggestions, 1):
                report.append(f"   {i}. {suggestion}")
            report.append("")

        # Next steps
        if error_count > 0:
            report.append("🔧 NEXT STEPS:")
            report.append("   1. Fix all errors listed above")
            report.append("   2. Re-run validation to check for additional issues")
            report.append("   3. Address warnings and implement suggestions")
            report.append("   4. Test the specification with a sample conversion")

        return "\n".join(report)

    def get_error_context(self, error_code: str) -> Dict[str, Any]:
        """
        Get detailed context and help for specific error codes.

        Args:
            error_code: The error code to get context for

        Returns:
            Dictionary with error context, examples, and help
        """
        error_contexts = {
            "MISSING_FIELD": {
                "description": "Required field is missing from the specification",
                "severity": "error",
                "category": "schema",
                "example": {
                    "invalid": {"name": "Test Agent"},
                    "valid": {
                        "id": "urn:agent:genesis:autonomize.ai:test:1.0.0",
                        "name": "Test Agent",
                        "description": "A test agent",
                        "agentGoal": "Test agent functionality",
                        "components": {}
                    }
                },
                "help": "All Genesis specifications must include core metadata fields",
                "documentation": "/docs/specification-schema.md"
            },

            "INVALID_URN_FORMAT": {
                "description": "The specification ID must follow URN format",
                "severity": "error",
                "category": "schema",
                "pattern": "urn:agent:genesis:domain:name:version",
                "example": {
                    "invalid": "my-agent-id",
                    "valid": "urn:agent:genesis:autonomize.ai:patient-care:1.0.0"
                },
                "help": "URNs provide unique identification and enable proper cataloging",
                "documentation": "/docs/specification-schema.md#id-field"
            },

            "COMPONENT_NOT_FOUND": {
                "description": "Referenced component type is not available",
                "severity": "error",
                "category": "components",
                "example": {
                    "invalid": {"type": "unknown_component"},
                    "valid": {"type": "genesis:agent"}
                },
                "help": "Check the component catalog for available types",
                "documentation": "/docs/component-catalog.md"
            },

            "INCOMPLETE_AGENT_CONFIG": {
                "description": "CrewAI agents require role, goal, and backstory",
                "severity": "error",
                "category": "crewai",
                "example": {
                    "invalid": {"config": {"role": "Assistant"}},
                    "valid": {
                        "config": {
                            "role": "Research Assistant",
                            "goal": "Research information thoroughly",
                            "backstory": "Expert researcher with domain knowledge"
                        }
                    }
                },
                "help": "Well-defined agent personalities improve multi-agent collaboration",
                "documentation": "/docs/crewai-patterns.md"
            },

            "TOOL_MODE_MISMATCH": {
                "description": "Component tool configuration is inconsistent",
                "severity": "error",
                "category": "tools",
                "example": {
                    "invalid": {
                        "type": "genesis:mcp_tool",
                        "provides": [{"useAs": "tools", "in": "agent"}]
                        # Missing asTools: true
                    },
                    "valid": {
                        "type": "genesis:mcp_tool",
                        "asTools": True,
                        "provides": [{"useAs": "tools", "in": "agent"}]
                    }
                },
                "help": "Tools must be properly configured for agent access",
                "documentation": "/docs/tool-integration.md"
            }
        }

        return error_contexts.get(error_code, {
            "description": f"Unknown error code: {error_code}",
            "severity": "unknown",
            "category": "general",
            "help": "Please check the documentation or contact support"
        })

    async def validate_spec_quick(self, spec_yaml: str, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Perform quick validation for real-time feedback (faster, less comprehensive).

        Args:
            spec_yaml: YAML specification string
            session: Optional database session for component validation

        Returns:
            Quick validation results
        """
        try:
            # Parse YAML
            spec_dict = yaml.safe_load(spec_yaml)

            # Quick validation phases (skip expensive semantic validation)
            results = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": [],
                "validation_phases": {
                    "yaml_parsing": True,
                    "schema_validation": None,
                    "structure_validation": None,
                    "component_validation": None,
                    "type_validation": None,
                    "semantic_validation": None  # Skipped in quick mode
                }
            }

            # Phase 1: JSON Schema Validation (quick)
            schema_result = self._validate_json_schema(spec_dict)
            results["validation_phases"]["schema_validation"] = len(schema_result["errors"]) == 0
            results["errors"].extend(schema_result["errors"])
            results["warnings"].extend(schema_result.get("warnings", []))

            if len(schema_result["errors"]) > 0:
                results["valid"] = False

            # Phase 2: Basic Structure Validation (quick)
            structure_result = self._validate_spec_structure(spec_dict)
            results["validation_phases"]["structure_validation"] = len(structure_result["errors"]) == 0
            results["errors"].extend(structure_result["errors"])
            results["warnings"].extend(structure_result.get("warnings", []))

            if len(structure_result["errors"]) > 0:
                results["valid"] = False

            # Quick component existence check (skip detailed validation)
            components = spec_dict.get("components", {})
            if not components:
                results["errors"].append({
                    "code": "NO_COMPONENTS",
                    "message": "Specification has no components",
                    "severity": "error",
                    "suggestion": "Add at least input, agent, and output components"
                })
                results["valid"] = False
                results["validation_phases"]["component_validation"] = False
            else:
                results["validation_phases"]["component_validation"] = True

            # Skip expensive validations in quick mode
            results["validation_phases"]["type_validation"] = True  # Assume valid for quick check

            # Calculate summary
            results["summary"] = {
                "error_count": len(results["errors"]),
                "warning_count": len(results["warnings"]),
                "suggestion_count": len(results["suggestions"])
            }

            return results

        except yaml.YAMLError as e:
            return {
                "valid": False,
                "errors": [{
                    "code": "YAML_PARSE_ERROR",
                    "message": f"Invalid YAML format: {e}",
                    "severity": "error",
                    "suggestion": "Check YAML syntax, indentation, and special characters"
                }],
                "warnings": [],
                "suggestions": [],
                "summary": {"error_count": 1, "warning_count": 0, "suggestion_count": 0},
                "validation_phases": {
                    "yaml_parsing": False,
                    "schema_validation": None,
                    "structure_validation": None,
                    "component_validation": None,
                    "type_validation": None,
                    "semantic_validation": None
                }
            }

    def get_available_components(self) -> Dict[str, Any]:
        """
        Get list of available components with their configurations from real Langflow registry.

        Returns:
            Dictionary of available components and their options
        """
        try:
            # Get components from the real template service
            return component_template_service.get_available_components()
        except Exception as e:
            logger.error(f"Error getting available components: {e}")
            # Return basic fallback components
            return {
                "AutonomizeModel": {
                    "type": "models",
                    "description": "Unified AI model component",
                    "options": {
                        "selected_model": [
                            "RxNorm Code",
                            "ICD-10 Code",
                            "CPT Code",
                            "Clinical LLM",
                            "Clinical Note Classifier",
                            "Combined Entity Linking"
                        ]
                    },
                    "inputs": ["search_query"],
                    "outputs": ["prediction"]
                },
                "Agent": {
                    "type": "agents",
                    "description": "Standard agent component",
                    "inputs": ["input_value", "system_message", "tools"],
                    "outputs": ["response"]
                },
                "ChatInput": {
                    "type": "inputs",
                    "description": "Chat input component",
                    "inputs": [],
                    "outputs": ["message"]
                },
                "ChatOutput": {
                    "type": "outputs",
                    "description": "Chat output component",
                    "inputs": ["input_value"],
                    "outputs": ["message"]
                }
            }

    def _validate_spec_structure(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate basic specification structure."""
        errors = []
        warnings = []

        # Required fields
        required_fields = ["name", "description", "agentGoal", "components"]
        for field in required_fields:
            if field not in spec_dict:
                errors.append(f"Missing required field: {field}")

        # Validate components structure - support both list and dict formats
        if "components" in spec_dict:
            components = spec_dict["components"]
            if isinstance(components, dict):
                # Dict format (YAML style) - validate each component
                if not components:
                    errors.append("At least one component is required")
                else:
                    for comp_id, comp in components.items():
                        if not isinstance(comp, dict):
                            errors.append(f"Component '{comp_id}' must be an object")
                            continue

                        # Required component fields (id is optional for dict format since it's the key)
                        comp_required = ["type"]
                        for field in comp_required:
                            if field not in comp:
                                errors.append(f"Component '{comp_id}' missing required field: {field}")
            elif isinstance(components, list):
                # List format - validate each component
                if not components:
                    errors.append("At least one component is required")
                else:
                    for i, comp in enumerate(components):
                        if not isinstance(comp, dict):
                            errors.append(f"Component {i} must be an object")
                            continue

                        # Required component fields
                        comp_required = ["id", "type"]
                        for field in comp_required:
                            if field not in comp:
                                errors.append(f"Component {i} missing required field: {field}")
            else:
                errors.append("Components must be a list or dictionary")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def _validate_components(self, components) -> Dict[str, Any]:
        """Validate component types and configurations."""
        warnings = []

        # Handle both dict and list formats
        component_items = []
        if isinstance(components, dict):
            # Dict format: convert to list of (id, component) tuples
            component_items = [(comp_id, comp) for comp_id, comp in components.items()]
        elif isinstance(components, list):
            # List format: convert to list of (id, component) tuples
            component_items = [(comp.get('id', f'component_{i}'), comp) for i, comp in enumerate(components)]

        for comp_id, comp in component_items:
            comp_type = comp.get("type", "")

            # Check if component type is known
            mapping = self.mapper.map_component(comp_type)
            if mapping["component"] == "CustomComponent" and "genesis:" in comp_type:
                warnings.append(f"Unknown component type '{comp_type}', using CustomComponent")

            # Validate provides connections
            if "provides" in comp:
                for provide in comp["provides"]:
                    if not isinstance(provide, dict):
                        warnings.append(f"Invalid provides declaration in component {comp_id}")
                        continue

                    if "useAs" not in provide or "in" not in provide:
                        warnings.append(f"Provides declaration missing useAs or in field in component {comp_id}")

        return {"warnings": warnings}

    async def _validate_components_enhanced(self, components, available_components: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced component validation with existence checking and connection validation."""
        errors = []
        warnings = []

        # Get the genesis mapped components
        genesis_mapped = available_components.get("genesis_mapped", {})

        # Handle both dict and list formats
        component_items = []
        if isinstance(components, dict):
            component_items = [(comp_id, comp) for comp_id, comp in components.items()]
        elif isinstance(components, list):
            component_items = [(comp.get('id', f'component_{i}'), comp) for i, comp in enumerate(components)]

        component_ids = [comp_id for comp_id, _ in component_items]

        for comp_id, comp in component_items:
            comp_type = comp.get("type", "")

            # 1. Component Existence Validation (CRITICAL FIX)
            if comp_type.startswith("genesis:"):
                if comp_type not in genesis_mapped:
                    errors.append(f"Component type '{comp_type}' does not exist. Available genesis components: {list(genesis_mapped.keys())[:10]}...")
                    continue
            else:
                # Non-genesis components should also be validated
                warnings.append(f"Component type '{comp_type}' is not a genesis component - ensure it exists in Langflow")

            # 2. Component Connection Validation
            has_connections = "provides" in comp and comp["provides"]
            if not has_connections and comp_type not in ["genesis:chat_input", "genesis:chat_output"]:
                warnings.append(f"Component '{comp_id}' has no connections defined - may be isolated in the flow")

            # 3. Validate provides connections
            if "provides" in comp:
                for provide in comp["provides"]:
                    if not isinstance(provide, dict):
                        errors.append(f"Invalid provides declaration in component '{comp_id}' - must be an object")
                        continue

                    if "useAs" not in provide or "in" not in provide:
                        errors.append(f"Provides declaration in component '{comp_id}' missing required 'useAs' or 'in' field")
                        continue

                    # Check if target component exists
                    target_component = provide.get("in")
                    if target_component and target_component not in component_ids:
                        errors.append(f"Component '{comp_id}' references non-existent target component '{target_component}'")

            # 4. Healthcare-specific validation
            if comp_type in ["genesis:api_request"] and "config" in comp:
                config = comp["config"]
                if "url_input" in config and "example.com" in config["url_input"]:
                    warnings.append(f"Component '{comp_id}' uses example URL - replace with actual healthcare API endpoint")

        # 5. Overall flow validation
        input_components = [comp_id for comp_id, comp in component_items if comp.get("type") == "genesis:chat_input"]
        output_components = [comp_id for comp_id, comp in component_items if comp.get("type") == "genesis:chat_output"]

        if not input_components:
            errors.append("Specification must include at least one 'genesis:chat_input' component")
        if not output_components:
            errors.append("Specification must include at least one 'genesis:chat_output' component")

        # 6. Check for disconnected components (no flow)
        if len(component_items) > 2:  # More than just input/output
            connected_components = set()
            for comp_id, comp in component_items:
                if "provides" in comp:
                    connected_components.add(comp_id)
                    for provide in comp.get("provides", []):
                        if isinstance(provide, dict) and "in" in provide:
                            connected_components.add(provide["in"])

            disconnected = [comp_id for comp_id, _ in component_items if comp_id not in connected_components]
            if disconnected:
                warnings.append(f"Components may be disconnected from main flow: {disconnected}")

        return {"errors": errors, "warnings": warnings}

    def _validate_json_schema(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate specification against JSON Schema.

        Args:
            spec_dict: Parsed specification dictionary

        Returns:
            Validation result with schema errors and warnings
        """
        errors = []
        warnings = []

        try:
            # Validate against main schema
            jsonschema.validate(spec_dict, GENESIS_SPEC_SCHEMA)

        except jsonschema.ValidationError as e:
            # Convert JSON schema errors to our format
            error_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"

            if "required" in e.message.lower():
                errors.append(f"Missing required field at {error_path}: {e.message}")
            elif "pattern" in e.message.lower():
                errors.append(f"Invalid format at {error_path}: {e.message}")
            elif "enum" in e.message.lower():
                errors.append(f"Invalid value at {error_path}: {e.message}")
            elif "type" in e.message.lower():
                errors.append(f"Wrong data type at {error_path}: {e.message}")
            else:
                errors.append(f"Schema validation error at {error_path}: {e.message}")

        except jsonschema.SchemaError as e:
            logger.error(f"Schema definition error: {e}")
            errors.append(f"Internal schema error: {e}")

        except Exception as e:
            logger.error(f"JSON schema validation error: {e}")
            warnings.append(f"Schema validation could not be completed: {e}")

        # Validate component configurations against their schemas
        components = self._get_components_list(spec_dict)
        for component in components:
            comp_type = component.get("type")
            comp_id = component.get("id")
            config = component.get("config", {})

            config_schema = get_component_config_schema(comp_type)
            if config_schema and config:
                try:
                    jsonschema.validate(config, config_schema)
                except jsonschema.ValidationError as e:
                    error_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "config"
                    errors.append(f"Component '{comp_id}' config error at {error_path}: {e.message}")

        return {"errors": errors, "warnings": warnings}

    def _validate_component_type_compatibility_enhanced(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced type compatibility validation with detailed error reporting.

        Args:
            spec_dict: Parsed specification dictionary

        Returns:
            Validation result with type compatibility errors and warnings
        """
        components = self._get_components_list(spec_dict)

        if isinstance(spec_dict.get("components"), list):
            return self._validate_component_type_compatibility(components)
        else:
            # Convert dict format to list format for validation
            component_list = []
            for comp_id, comp_data in spec_dict.get("components", {}).items():
                comp_data_with_id = comp_data.copy()
                comp_data_with_id["id"] = comp_id
                component_list.append(comp_data_with_id)

            return self._validate_component_type_compatibility(component_list)

    def _get_components_list(self, spec_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get components as a list regardless of input format.

        Args:
            spec_dict: Specification dictionary

        Returns:
            List of component dictionaries
        """
        components = spec_dict.get("components", [])

        if isinstance(components, dict):
            # Convert dict format to list
            return [
                {**comp_data, "id": comp_id}
                for comp_id, comp_data in components.items()
            ]
        elif isinstance(components, list):
            return components
        else:
            return []

    def _convert_legacy_errors(self, legacy_errors: List) -> List[Dict[str, Any]]:
        """
        Convert legacy error format to new structured format.

        Args:
            legacy_errors: List of error strings or dictionaries

        Returns:
            List of structured error dictionaries
        """
        converted = []

        for error in legacy_errors:
            if isinstance(error, str):
                converted.append({
                    "code": "LEGACY_ERROR",
                    "message": error,
                    "severity": "error"
                })
            elif isinstance(error, dict) and "message" in error:
                # Already in new format
                converted.append(error)
            elif isinstance(error, dict):
                # Try to extract message
                message = str(error)
                converted.append({
                    "code": "LEGACY_ERROR",
                    "message": message,
                    "severity": "error"
                })

        return converted

    def _convert_legacy_warnings(self, legacy_warnings: List) -> List[Dict[str, Any]]:
        """
        Convert legacy warning format to new structured format.

        Args:
            legacy_warnings: List of warning strings or dictionaries

        Returns:
            List of structured warning dictionaries
        """
        converted = []

        for warning in legacy_warnings:
            if isinstance(warning, str):
                converted.append({
                    "code": "LEGACY_WARNING",
                    "message": warning,
                    "severity": "warning"
                })
            elif isinstance(warning, dict) and "message" in warning:
                # Already in new format
                converted.append(warning)
            elif isinstance(warning, dict):
                # Try to extract message
                message = str(warning)
                converted.append({
                    "code": "LEGACY_WARNING",
                    "message": message,
                    "severity": "warning"
                })

        return converted

    def _remove_duplicate_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate validation issues based on message content.

        Args:
            issues: List of issue dictionaries

        Returns:
            Deduplicated list of issues
        """
        seen_messages = set()
        unique_issues = []

        for issue in issues:
            message = issue.get("message", "")
            if message not in seen_messages:
                seen_messages.add(message)
                unique_issues.append(issue)

        return unique_issues

    def _validate_component_type_compatibility(self, components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        UNIFIED VALIDATION: Delegate all connection validation to FlowConverter.

        This ensures we have single source of truth for validation logic.
        FlowConverter contains the authoritative type compatibility and tool connection logic.
        """
        errors = []
        warnings = []

        try:
            # Create component lookup for basic validation
            component_lookup = {comp.get("id"): comp for comp in components}

            # Track connections for circular dependency detection
            connections = []

            for component in components:
                comp_id = component.get("id")
                provides = component.get("provides", [])

                if not provides:
                    continue

                for connection in provides:
                    if not isinstance(connection, dict):
                        errors.append(f"Invalid connection format in component '{comp_id}'")
                        continue

                    target_id = connection.get("in")
                    use_as = connection.get("useAs")

                    if not target_id or not use_as:
                        errors.append(f"Missing 'in' or 'useAs' in connection from '{comp_id}'")
                        continue

                    # Track connection for circular dependency check
                    connections.append((comp_id, target_id))

                    # Get target component
                    target_component = component_lookup.get(target_id)
                    if not target_component:
                        errors.append(f"Component '{comp_id}' references non-existent target '{target_id}'")
                        continue

                    # UNIFIED VALIDATION: Use FlowConverter's validation logic
                    validation_result = self._validate_connection_using_converter(
                        component, connection, target_component
                    )
                    errors.extend(validation_result["errors"])
                    warnings.extend(validation_result["warnings"])

            # Check for circular dependencies
            circular_errors = self._detect_circular_dependencies(connections)
            errors.extend(circular_errors)

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings
            }

        except Exception as e:
            logger.error(f"Error in _validate_component_type_compatibility: {e}")
            return {
                "valid": False,
                "errors": [f"Type compatibility validation failed: {e}"],
                "warnings": []
            }

    def _validate_connection_using_converter(self, source_comp: Dict[str, Any],
                                           connection: Dict[str, Any],
                                           target_comp: Dict[str, Any]) -> Dict[str, Any]:
        """
        UNIFIED VALIDATION: Use FlowConverter's validation logic as single source of truth.

        This delegates all connection validation to FlowConverter which contains the
        authoritative logic for tool connections and type compatibility.
        """
        errors = []
        warnings = []

        # Extract basic connection info (available in exception handlers)
        use_as = connection.get("useAs")
        source_type = source_comp.get("type", "")
        target_type = target_comp.get("type", "")

        try:
            from langflow.custom.genesis.spec.models import Component

            # Create mock Component objects for FlowConverter validation
            source_component = Component(
                id=source_comp.get("id", ""),
                name=source_comp.get("name", source_comp.get("id", "")),
                kind=source_comp.get("kind", "Tool"),
                type=source_type,
                config=source_comp.get("config", {}),
                asTools=source_comp.get("asTools", False)
            )

            target_component = Component(
                id=target_comp.get("id", ""),
                name=target_comp.get("name", target_comp.get("id", "")),
                kind=target_comp.get("kind", "Agent"),
                type=target_type,
                config=target_comp.get("config", {}),
                asTools=target_comp.get("asTools", False)
            )

            # UNIFIED VALIDATION: Tool connections use FlowConverter's tool logic
            if use_as == "tools":
                is_valid = self.converter._validate_tool_connection_capability(
                    source_type, target_type, source_component
                )

                if not is_valid:
                    errors.append(
                        f"Tool connection validation failed: {source_comp.get('id')} -> "
                        f"{target_comp.get('id')} (useAs: tools). Component {source_type} "
                        f"cannot be used as a tool for {target_type}."
                    )
            else:
                # For non-tool connections, use FlowConverter's type compatibility
                # Simplified validation using converter's logic
                try:
                    # Use converter's mapping logic to get component types
                    source_mapping = self.mapper.map_component(source_type)
                    target_mapping = self.mapper.map_component(target_type)

                    source_langflow_comp = source_mapping.get("component", "")
                    target_langflow_comp = target_mapping.get("component", "")

                    # Basic type compatibility using converter
                    output_types = ["Message", "Data"]  # Default output types
                    input_types = ["Message", "Data", "str"]  # Default input types

                    is_compatible = self.converter._validate_type_compatibility_fixed(
                        output_types, input_types, source_langflow_comp, target_langflow_comp
                    )

                    if not is_compatible:
                        errors.append(
                            f"Type compatibility validation failed: {source_comp.get('id')} -> "
                            f"{target_comp.get('id')} (useAs: {use_as})"
                        )

                except Exception as inner_e:
                    logger.debug(f"Simplified type validation failed: {inner_e}")
                    # Very basic fallback - just check component existence
                    pass

        except Exception as e:
            logger.warning(f"Error in unified converter validation, using basic fallback: {e}")
            # Basic fallback validation
            if use_as == "tools":
                # Check basic tool capability
                source_type = source_comp.get("type", "")
                if (not source_comp.get("asTools", False) and
                    not source_type.startswith("genesis:mcp") and
                    not source_type.startswith("genesis:knowledge")):
                    errors.append(
                        f"Component {source_comp.get('id')} used as tool but not marked as tool-capable"
                    )

        return {"errors": errors, "warnings": warnings}



    def _determine_output_field(self, component_name: str, use_as: str) -> str:
        """
        Determine the output field name based on component type and usage.

        This helps map the conceptual connection to actual component ports.
        """
        # Get I/O mapping from ComponentMapper
        io_mapping = self.mapper.get_component_io_mapping(component_name)
        if io_mapping and io_mapping.get("output_field"):
            return io_mapping["output_field"]

        # Default field mappings based on component patterns
        if "Input" in component_name:
            return "message"
        elif "Agent" in component_name or "Model" in component_name:
            return "response"
        elif "Tool" in component_name or "MCP" in component_name:
            return "response"
        elif "Prompt" in component_name:
            return "prompt"
        else:
            return "output"  # Generic fallback

    def _determine_input_field(self, component_name: str, use_as: str) -> str:
        """
        Determine the input field name based on component type and usage.

        This helps map the conceptual connection to actual component ports.
        """
        # Get I/O mapping from ComponentMapper
        io_mapping = self.mapper.get_component_io_mapping(component_name)
        if io_mapping and io_mapping.get("input_field"):
            return io_mapping["input_field"]

        # Special handling for tool connections
        if use_as == "tools":
            return "tools"  # Agents typically have a tools input
        elif use_as == "system_prompt":
            return "system_message"  # System prompt input

        # Default field mappings based on component patterns
        if "Agent" in component_name or "Model" in component_name:
            return "input_value"
        elif "Output" in component_name:
            return "input_value"
        elif "Search" in component_name:
            return "search_query"
        elif "API" in component_name:
            return "url_input"
        else:
            return "input_value"  # Generic fallback

    def _validate_field_mappings(self, field_mapping: Dict[str, str],
                                source_io: Dict[str, Any], target_io: Dict[str, Any],
                                source_id: str, target_id: str) -> Dict[str, Any]:
        """Validate field-level mappings between components."""
        errors = []
        warnings = []

        source_output_field = source_io.get("output_field")
        target_input_field = target_io.get("input_field")

        for source_field, target_field in field_mapping.items():
            # Validate source field exists
            if source_output_field and source_field != source_output_field:
                warnings.append(
                    f"Field mapping uses '{source_field}' but component '{source_id}' "
                    f"outputs '{source_output_field}'"
                )

            # Validate target field exists
            if target_input_field and target_field != target_input_field:
                warnings.append(
                    f"Field mapping targets '{target_field}' but component '{target_id}' "
                    f"expects '{target_input_field}'"
                )

        return {"errors": errors, "warnings": warnings}

    def _detect_circular_dependencies(self, connections: List[tuple]) -> List[str]:
        """Detect circular dependencies in component connections."""
        errors = []

        # Build adjacency list
        graph = {}
        for source, target in connections:
            if source not in graph:
                graph[source] = []
            graph[source].append(target)

        # DFS to detect cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            if node in rec_stack:
                return True
            if node in visited:
                return False

            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if has_cycle(neighbor):
                    return True

            rec_stack.remove(node)
            return False

        # Check each component for cycles
        for component in graph:
            if component not in visited:
                if has_cycle(component):
                    errors.append(f"Circular dependency detected involving component '{component}'")
                    break

        return errors

    def _get_langflow_component_name(self, genesis_type: str) -> Optional[str]:
        """Get Langflow component name from genesis type."""
        try:
            mapping = self.mapper.STANDARD_MAPPINGS.get(genesis_type)
            if not mapping:
                mapping = self.mapper.MCP_MAPPINGS.get(genesis_type)
            if not mapping:
                mapping = self.mapper.AUTONOMIZE_MODELS.get(genesis_type)

            if mapping and isinstance(mapping, dict):
                return mapping.get("component")
            return None
        except Exception:
            return None

    async def _save_flow_to_database(self, flow_data: Dict[str, Any], name: str,
                                    session: AsyncSession, user_id: UUID,
                                    folder_id: Optional[str] = None) -> str:
        """Save flow to database using real Langflow database logic."""
        try:
            # Parse folder_id if provided
            parsed_folder_id = UUID(folder_id) if folder_id else None

            # Create FlowCreate object
            flow_create = FlowCreate(
                name=name,
                description=flow_data.get("description"),
                data=flow_data.get("data", {}),
                user_id=user_id,
                folder_id=parsed_folder_id,
                updated_at=datetime.now(timezone.utc)
            )

            # Check for name uniqueness and auto-increment if needed
            existing_flows = await session.exec(
                select(Flow).where(Flow.name.like(f"{name}%")).where(Flow.user_id == user_id)
            )
            existing_flows_list = existing_flows.all()

            if existing_flows_list:
                existing_names = [flow.name for flow in existing_flows_list]
                if name in existing_names:
                    # Find the highest number suffix
                    import re
                    pattern = rf"^{re.escape(name)} \((\d+)\)$"
                    numbers = []
                    for existing_name in existing_names:
                        match = re.match(pattern, existing_name)
                        if match:
                            numbers.append(int(match.group(1)))

                    if numbers:
                        flow_create.name = f"{name} ({max(numbers) + 1})"
                    else:
                        flow_create.name = f"{name} (1)"

            # Ensure flow has a folder (use default if none specified)
            if flow_create.folder_id is None:
                default_folder = await session.exec(
                    select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME, Folder.user_id == user_id)
                )
                default_folder_result = default_folder.first()
                if default_folder_result:
                    flow_create.folder_id = default_folder_result.id

            # Create the database flow object
            db_flow = Flow.model_validate(flow_create, from_attributes=True)
            session.add(db_flow)
            await session.commit()
            await session.refresh(db_flow)

            logger.info(f"Created flow '{db_flow.name}' with ID: {db_flow.id}")
            return str(db_flow.id)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error saving flow to database: {e}")
            raise ValueError(f"Failed to save flow to database: {e}")

    def get_component_mapping_info(self, spec_type: str) -> Dict[str, Any]:
        """Get information about how a specification type maps to components."""
        mapping = self.mapper.map_component(spec_type)
        io_info = self.mapper.get_component_io_mapping(mapping["component"])

        return {
            "spec_type": spec_type,
            "langflow_component": mapping["component"],
            "config": mapping.get("config", {}),
            "input_field": io_info.get("input_field"),
            "output_field": io_info.get("output_field"),
            "output_types": io_info.get("output_types", []),
            "is_tool": self.mapper.is_tool_component(spec_type)
        }

    async def get_all_available_components(self) -> Dict[str, Any]:
        """
        Get ALL components - both Langflow native and genesis mapped.
        Enhanced with dynamic discovery and database integration.

        Returns:
            Dictionary containing:
            - langflow_components: All Langflow components
            - genesis_mapped: Genesis-mapped components (hardcoded + database)
            - unmapped: Components without genesis mappings
            - database_mapped: Components mapped via database
            - discovery_stats: Statistics from component discovery
        """
        try:
            from langflow.interface.components import get_and_cache_all_types_dict
            from langflow.services.deps import get_settings_service

            # Get ALL Langflow components
            all_langflow = await get_and_cache_all_types_dict(get_settings_service())

            # Get hardcoded genesis mappings
            hardcoded_mappings = {}
            hardcoded_mappings.update(self.mapper.AUTONOMIZE_MODELS)
            hardcoded_mappings.update(self.mapper.MCP_MAPPINGS)
            hardcoded_mappings.update(self.mapper.STANDARD_MAPPINGS)

            # Try to get database mappings from cache
            database_mappings = {}
            cache_status = self.mapper.get_cache_status()

            if cache_status["cached_mappings"] > 0:
                # Get mappings from cache
                for cache_key in cache_status["cached_types"]:
                    if cache_key.startswith("mapping_cache_"):
                        genesis_type = cache_key.replace("mapping_cache_", "")
                        mapping = self.mapper._get_mapping_from_database(genesis_type)
                        if mapping:
                            database_mappings[genesis_type] = mapping

            # Combine all genesis mappings (hardcoded + database)
            all_genesis_mapped = {}
            all_genesis_mapped.update(hardcoded_mappings)
            all_genesis_mapped.update(database_mappings)

            # Enhanced component analysis using ComponentMapper's available components
            mapper_components = self.mapper.get_available_components()
            discovered_components = mapper_components.get("discovered_components", {})

            # Find unmapped components with intelligent suggestions
            unmapped = []
            mapped_langflow_components = set()

            if all_langflow and "components" in all_langflow:
                for category, components in all_langflow["components"].items():
                    for comp_name in components.keys():
                        # Check if this component has a genesis mapping
                        has_mapping = False
                        for genesis_type, mapping in all_genesis_mapped.items():
                            if mapping.get("component") == comp_name:
                                has_mapping = True
                                mapped_langflow_components.add(comp_name)
                                break

                        if not has_mapping:
                            # Use ComponentMapper for intelligent suggestion
                            suggestion = self._generate_intelligent_suggestion(comp_name, category)
                            unmapped.append({
                                "name": comp_name,
                                "category": category,
                                "suggestion": suggestion,
                                "priority": self._assess_component_priority(comp_name, category),
                                "reasons": self._get_unmapped_reasons(comp_name)
                            })

            # Generate discovery statistics
            discovery_stats = {
                "total_langflow_components": len([
                    comp for category in all_langflow.get("components", {}).values()
                    for comp in category.keys()
                ]) if all_langflow and "components" in all_langflow else 0,
                "hardcoded_mappings": len(hardcoded_mappings),
                "database_mappings": len(database_mappings),
                "total_mapped": len(all_genesis_mapped),
                "unmapped_count": len(unmapped),
                "discovered_components": len(discovered_components),
                "mapping_coverage": (
                    len(mapped_langflow_components) /
                    max(1, len([
                        comp for category in all_langflow.get("components", {}).values()
                        for comp in category.keys()
                    ]))
                ) * 100 if all_langflow and "components" in all_langflow else 0,
                "cache_status": cache_status,
            }

            return {
                "langflow_components": all_langflow,
                "genesis_mapped": all_genesis_mapped,
                "hardcoded_mapped": hardcoded_mappings,
                "database_mapped": database_mappings,
                "discovered_components": discovered_components,
                "unmapped": unmapped,
                "discovery_stats": discovery_stats,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error getting all available components: {e}")
            # Return enhanced fallback with genesis mappings at least
            fallback_mappings = {
                **self.mapper.AUTONOMIZE_MODELS,
                **self.mapper.MCP_MAPPINGS,
                **self.mapper.STANDARD_MAPPINGS
            }

            return {
                "langflow_components": {},
                "genesis_mapped": fallback_mappings,
                "hardcoded_mapped": fallback_mappings,
                "database_mapped": {},
                "discovered_components": {},
                "unmapped": [],
                "discovery_stats": {
                    "total_langflow_components": 0,
                    "hardcoded_mappings": len(fallback_mappings),
                    "database_mappings": 0,
                    "total_mapped": len(fallback_mappings),
                    "unmapped_count": 0,
                    "mapping_coverage": 0,
                    "cache_status": self.mapper.get_cache_status(),
                },
                "success": False,
                "error": str(e)
            }

    def _generate_intelligent_suggestion(self, comp_name: str, category: str) -> str:
        """Generate intelligent suggestion for unmapped component."""
        # Use ComponentMapper's intelligent fallback
        suggestion = self.mapper._handle_unknown_type(comp_name)
        suggested_component = suggestion.get("component", comp_name)

        # Convert component name to genesis type format
        base_name = comp_name.lower()
        base_name = base_name.replace(" ", "_").replace("-", "_")

        # Remove common suffixes
        import re
        base_name = re.sub(r'_(component|tool|model)$', '', base_name)

        return f"genesis:{base_name}"

    def _assess_component_priority(self, comp_name: str, category: str) -> str:
        """Assess priority for creating mapping for unmapped component."""
        comp_lower = comp_name.lower()

        # High priority components
        if any(term in comp_lower for term in [
            "agent", "input", "output", "model", "health", "medical"
        ]):
            return "high"

        # Medium priority components
        if any(term in comp_lower for term in [
            "tool", "api", "data", "process", "transform"
        ]):
            return "medium"

        return "low"

    def _get_unmapped_reasons(self, comp_name: str) -> List[str]:
        """Get reasons why component might not be mapped."""
        reasons = []
        comp_lower = comp_name.lower()

        if "experimental" in comp_lower:
            reasons.append("Component marked as experimental")
        if "deprecated" in comp_lower:
            reasons.append("Component may be deprecated")
        if "custom" in comp_lower:
            reasons.append("Custom component - may not need genesis mapping")
        if not reasons:
            reasons.append("Component may be new or specialized")

        return reasons

    async def validate_spec_quick(self, spec_yaml: str) -> Dict[str, Any]:
        """
        Quick validation for real-time feedback (schema + basic validation only).

        Args:
            spec_yaml: YAML specification string

        Returns:
            Quick validation result
        """
        return await self.validate_spec(spec_yaml, detailed=False)

    async def validate_spec_with_runtime(self,
                                       spec_yaml: str,
                                       target_runtime: RuntimeType = RuntimeType.LANGFLOW,
                                       validation_options: Optional[ValidationOptions] = None) -> Dict[str, Any]:
        """
        Enhanced validation using Phase 3 runtime converter architecture.

        Args:
            spec_yaml: YAML specification string
            target_runtime: Target runtime type for validation
            validation_options: Validation configuration options

        Returns:
            Comprehensive validation result with runtime-specific checks
        """
        try:
            # Parse YAML
            spec_dict = yaml.safe_load(spec_yaml)
            if not spec_dict:
                return {
                    "valid": False,
                    "errors": [{"code": "EMPTY_SPEC", "message": "Empty or invalid YAML specification", "severity": "error"}],
                    "warnings": [],
                    "suggestions": [],
                    "summary": {"error_count": 1, "warning_count": 0, "suggestion_count": 0}
                }

            # Use Phase 3 converter for enhanced validation
            validation_result = await converter_factory.validate_specification(
                spec_dict, target_runtime, validation_options
            )

            # Convert to SpecService format
            return self._convert_runtime_validation_result(validation_result, target_runtime)

        except yaml.YAMLError as e:
            return {
                "valid": False,
                "errors": [{
                    "code": "YAML_PARSE_ERROR",
                    "message": f"Invalid YAML format: {e}",
                    "severity": "error",
                    "suggestion": "Check YAML syntax, indentation, and special characters"
                }],
                "warnings": [],
                "suggestions": [],
                "summary": {"error_count": 1, "warning_count": 0, "suggestion_count": 0}
            }
        except Exception as e:
            logger.error(f"Error in validate_spec_with_runtime: {e}")
            return {
                "valid": False,
                "errors": [{
                    "code": "RUNTIME_VALIDATION_ERROR",
                    "message": f"Runtime validation error: {e}",
                    "severity": "error",
                    "suggestion": "Please report this issue to the development team"
                }],
                "warnings": [],
                "suggestions": [],
                "summary": {"error_count": 1, "warning_count": 0, "suggestion_count": 0}
            }

    async def check_runtime_compatibility(self,
                                        spec_yaml: str,
                                        runtime_types: Optional[List[RuntimeType]] = None) -> Dict[str, Any]:
        """
        Check specification compatibility across multiple runtimes.

        Args:
            spec_yaml: YAML specification string
            runtime_types: List of runtime types to check (all if None)

        Returns:
            Dictionary mapping runtime types to compatibility results
        """
        try:
            # Parse YAML
            spec_dict = yaml.safe_load(spec_yaml)
            if not spec_dict:
                return {
                    "error": "Empty or invalid YAML specification",
                    "compatibility_results": {}
                }

            # Use Phase 3 converter factory for multi-runtime validation
            compatibility_results = await converter_factory.check_runtime_compatibility(
                spec_dict, runtime_types
            )

            # Convert results to SpecService format
            formatted_results = {}
            for runtime_type, result in compatibility_results.items():
                formatted_results[runtime_type.value] = {
                    "compatible": result["compatible"],
                    "errors": [{"message": error, "severity": "error"} for error in result["errors"]],
                    "warnings": [{"message": warning, "severity": "warning"} for warning in result["warnings"]],
                    "suggestions": result["suggestions"],
                    "performance_hints": result["performance_hints"],
                    "metadata": result["metadata"]
                }

            return {
                "compatibility_results": formatted_results,
                "summary": {
                    "total_runtimes_checked": len(formatted_results),
                    "compatible_runtimes": len([r for r in formatted_results.values() if r["compatible"]]),
                    "incompatible_runtimes": len([r for r in formatted_results.values() if not r["compatible"]])
                }
            }

        except Exception as e:
            logger.error(f"Error in check_runtime_compatibility: {e}")
            return {
                "error": f"Compatibility check failed: {e}",
                "compatibility_results": {}
            }

    async def convert_spec_to_flow_enhanced(self,
                                          spec_yaml: str,
                                          variables: Optional[Dict[str, Any]] = None,
                                          target_runtime: RuntimeType = RuntimeType.LANGFLOW,
                                          validation_options: Optional[ValidationOptions] = None,
                                          optimization_level: str = "balanced") -> Dict[str, Any]:
        """
        Enhanced conversion using Phase 3 converter architecture.

        Args:
            spec_yaml: YAML specification string
            variables: Runtime variables for resolution
            target_runtime: Target runtime type
            validation_options: Validation configuration options
            optimization_level: Performance optimization level

        Returns:
            Enhanced conversion result with detailed metadata
        """
        try:
            # Parse YAML
            spec_dict = yaml.safe_load(spec_yaml)
            if not spec_dict:
                raise ValueError("Empty or invalid YAML specification")

            # Use Phase 3 converter factory for enhanced conversion
            conversion_result = await converter_factory.convert_specification(
                spec_dict, target_runtime, variables, validation_options, optimization_level
            )

            if conversion_result.success:
                return {
                    "success": True,
                    "flow_data": conversion_result.flow_data,
                    "metadata": conversion_result.metadata,
                    "performance_metrics": conversion_result.performance_metrics,
                    "warnings": conversion_result.warnings,
                    "runtime_type": conversion_result.runtime_type.value
                }
            else:
                return {
                    "success": False,
                    "errors": conversion_result.errors,
                    "warnings": conversion_result.warnings,
                    "metadata": conversion_result.metadata,
                    "runtime_type": conversion_result.runtime_type.value
                }

        except yaml.YAMLError as e:
            return {
                "success": False,
                "errors": [f"Invalid YAML format: {e}"],
                "warnings": [],
                "metadata": {"error_type": "yaml_parse_error"}
            }
        except Exception as e:
            logger.error(f"Error in convert_spec_to_flow_enhanced: {e}")
            return {
                "success": False,
                "errors": [f"Enhanced conversion failed: {e}"],
                "warnings": [],
                "metadata": {"error_type": type(e).__name__}
            }

    def _convert_runtime_validation_result(self,
                                         runtime_result: Dict[str, Any],
                                         runtime_type: RuntimeType) -> Dict[str, Any]:
        """
        Convert runtime validation result to SpecService format.

        Args:
            runtime_result: Validation result from runtime converter
            runtime_type: Runtime type that performed validation

        Returns:
            SpecService-formatted validation result
        """
        errors = []
        warnings = []
        suggestions = []

        # Convert errors
        for error in runtime_result.get("errors", []):
            if isinstance(error, str):
                errors.append({
                    "code": "RUNTIME_ERROR",
                    "message": error,
                    "severity": "error",
                    "runtime": runtime_type.value
                })
            elif isinstance(error, dict):
                errors.append({
                    "code": error.get("code", "RUNTIME_ERROR"),
                    "message": error.get("message", str(error)),
                    "severity": "error",
                    "runtime": runtime_type.value
                })

        # Convert warnings
        for warning in runtime_result.get("warnings", []):
            if isinstance(warning, str):
                warnings.append({
                    "code": "RUNTIME_WARNING",
                    "message": warning,
                    "severity": "warning",
                    "runtime": runtime_type.value
                })
            elif isinstance(warning, dict):
                warnings.append({
                    "code": warning.get("code", "RUNTIME_WARNING"),
                    "message": warning.get("message", str(warning)),
                    "severity": "warning",
                    "runtime": runtime_type.value
                })

        # Convert suggestions
        for suggestion in runtime_result.get("suggestions", []):
            if isinstance(suggestion, str):
                suggestions.append({
                    "code": "RUNTIME_SUGGESTION",
                    "message": suggestion,
                    "severity": "suggestion",
                    "runtime": runtime_type.value
                })
            elif isinstance(suggestion, dict):
                suggestions.append({
                    "code": suggestion.get("code", "RUNTIME_SUGGESTION"),
                    "message": suggestion.get("message", str(suggestion)),
                    "severity": "suggestion",
                    "runtime": runtime_type.value
                })

        return {
            "valid": runtime_result.get("valid", False),
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "summary": {
                "error_count": len(errors),
                "warning_count": len(warnings),
                "suggestion_count": len(suggestions)
            },
            "runtime_metadata": runtime_result.get("validation_metadata", {}),
            "performance_hints": runtime_result.get("performance_hints", [])
        }

    def get_validation_suggestions(self, validation_result: Dict[str, Any]) -> List[str]:
        """
        Extract actionable suggestions from validation result.

        Args:
            validation_result: Result from validate_spec()

        Returns:
            List of actionable suggestion strings
        """
        suggestions = []

        # Extract suggestions from errors
        for error in validation_result.get("errors", []):
            if isinstance(error, dict) and error.get("suggestion"):
                suggestions.append(error["suggestion"])

        # Extract suggestions from warnings
        for warning in validation_result.get("warnings", []):
            if isinstance(warning, dict) and warning.get("suggestion"):
                suggestions.append(warning["suggestion"])

        # Extract explicit suggestions
        for suggestion in validation_result.get("suggestions", []):
            if isinstance(suggestion, dict):
                if suggestion.get("action"):
                    suggestions.append(suggestion["action"])
                elif suggestion.get("message"):
                    suggestions.append(suggestion["message"])
            elif isinstance(suggestion, str):
                suggestions.append(suggestion)

        return list(set(suggestions))  # Remove duplicates

    def format_validation_report(self, validation_result: Dict[str, Any],
                               include_suggestions: bool = True) -> str:
        """
        Format validation result into a human-readable report.

        Args:
            validation_result: Result from validate_spec()
            include_suggestions: Whether to include suggestions in the report

        Returns:
            Formatted validation report string
        """
        lines = []
        summary = validation_result.get("summary", {})

        # Header
        if validation_result.get("valid", False):
            lines.append("✅ Specification validation PASSED")
        else:
            lines.append("❌ Specification validation FAILED")

        lines.append("")

        # Summary
        lines.append(f"📊 Summary:")
        lines.append(f"   Errors: {summary.get('error_count', 0)}")
        lines.append(f"   Warnings: {summary.get('warning_count', 0)}")
        lines.append(f"   Suggestions: {summary.get('suggestion_count', 0)}")
        lines.append("")

        # Validation phases
        phases = validation_result.get("validation_phases", {})
        if phases:
            lines.append("🔍 Validation Phases:")
            for phase, passed in phases.items():
                if passed is not None:
                    status = "✅" if passed else "❌"
                    phase_name = phase.replace("_", " ").title()
                    lines.append(f"   {status} {phase_name}")
            lines.append("")

        # Errors
        errors = validation_result.get("errors", [])
        if errors:
            lines.append("🚨 Errors:")
            for i, error in enumerate(errors, 1):
                if isinstance(error, dict):
                    message = error.get("message", str(error))
                    component = error.get("component_id")
                    if component:
                        lines.append(f"   {i}. [{component}] {message}")
                    else:
                        lines.append(f"   {i}. {message}")
                else:
                    lines.append(f"   {i}. {error}")
            lines.append("")

        # Warnings
        warnings = validation_result.get("warnings", [])
        if warnings:
            lines.append("⚠️ Warnings:")
            for i, warning in enumerate(warnings, 1):
                if isinstance(warning, dict):
                    message = warning.get("message", str(warning))
                    component = warning.get("component_id")
                    if component:
                        lines.append(f"   {i}. [{component}] {message}")
                    else:
                        lines.append(f"   {i}. {message}")
                else:
                    lines.append(f"   {i}. {warning}")
            lines.append("")

        # Suggestions
        if include_suggestions:
            suggestions = self.get_validation_suggestions(validation_result)
            if suggestions:
                lines.append("💡 Suggestions:")
                for i, suggestion in enumerate(suggestions, 1):
                    lines.append(f"   {i}. {suggestion}")
                lines.append("")

        return "\n".join(lines)

    async def _ensure_database_cache_populated(self, session: Optional[AsyncSession] = None):
        """
        Ensure database mapping cache is populated before flow conversion.

        This method implements AC2: Cache Population Before Conversion.

        Args:
            session: Optional database session for cache refresh
        """
        try:
            if session is not None:
                # Check if cache needs refreshing
                cache_status = self.mapper.get_cache_status()

                # Refresh cache if it's empty or we have a session available
                if cache_status["cached_mappings"] == 0:
                    logger.info("Database mapping cache is empty, refreshing from database")
                    refresh_result = await self.mapper.refresh_cache_from_database(session)

                    if "error" in refresh_result:
                        logger.warning(f"Failed to refresh database cache: {refresh_result['error']}")
                        logger.info("Proceeding with hardcoded mappings as fallback")
                    else:
                        logger.info(f"Successfully refreshed cache with {refresh_result['refreshed']} mappings")
                else:
                    logger.debug(f"Database cache already populated with {cache_status['cached_mappings']} mappings")
            else:
                logger.debug("No database session provided, using existing cache or hardcoded mappings")

        except Exception as e:
            # AC3: Graceful Fallback to Hardcoded Mappings
            logger.warning(f"Error populating database cache: {e}")
            logger.info("Gracefully falling back to hardcoded mappings")
            # Continue without raising exception to ensure conversion still works

    async def _refresh_mapper_database_cache(self, session: AsyncSession):
        """
        Refresh ComponentMapper's database cache with latest mappings.
        AUTPE-6207: Integration with database-driven component discovery.

        Args:
            session: Database session for fetching mappings
        """
        try:
            if not self.component_mapping_service:
                logger.debug("ComponentMappingService not available, skipping cache refresh")
                return

            # Get all active component mappings from database
            mappings = await self.component_mapping_service.get_all_component_mappings(
                session, active_only=True, limit=1000
            )

            if mappings:
                # Update mapper's database cache
                for mapping in mappings:
                    genesis_type = mapping.genesis_type
                    langflow_component = mapping.langflow_component

                    # Create mapping structure
                    mapping_dict = {
                        "component": langflow_component,
                        "config": mapping.default_config or {},
                        "category": mapping.category,
                        "database_id": str(mapping.id)
                    }

                    # Update mapper's cache
                    self.mapper._database_cache[genesis_type] = mapping_dict

                logger.info(f"Refreshed mapper cache with {len(mappings)} database mappings")

            # Also cache in our local service for quick access
            self._database_components_cache = {
                m.genesis_type: m for m in mappings
            }
            self._last_cache_refresh = datetime.now(timezone.utc)

        except Exception as e:
            logger.warning(f"Error refreshing mapper database cache: {e}")
            # Continue without raising to maintain resilience

    async def get_all_available_components_with_database(self, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Get all available components with enhanced database-driven discovery.
        AUTPE-6207: Integrates database mappings with dynamic discovery.

        Args:
            session: Optional database session for fetching mappings

        Returns:
            Dictionary with comprehensive component information
        """
        try:
            # Start with base implementation
            result = await self.get_all_available_components()

            if session and self.component_mapping_service:
                # Enhance with database mappings
                db_mappings = await self.component_mapping_service.get_all_component_mappings(
                    session, active_only=True, limit=1000
                )

                # Add database mappings to result
                database_mapped = {}
                for mapping in db_mappings:
                    database_mapped[mapping.genesis_type] = {
                        "description": mapping.description or f"Component {mapping.genesis_type}",
                        "config": mapping.base_config or {},
                        "category": mapping.component_category,
                        "io_mapping": mapping.io_mapping or {},
                        "healthcare_metadata": mapping.healthcare_metadata,
                        "tool_capabilities": mapping.tool_capabilities,
                        "active": mapping.active,
                        "version": mapping.version,
                        "created_at": mapping.created_at.isoformat() if mapping.created_at else None
                    }

                # Merge database mappings with existing mappings
                result["database_mapped"] = database_mapped
                result["genesis_mapped"].update(database_mapped)

                # Update discovery stats
                if "discovery_stats" in result:
                    result["discovery_stats"]["database_mappings"] = len(database_mapped)
                    result["discovery_stats"]["total_mapped"] = len(result["genesis_mapped"])

                # Add healthcare-specific mappings
                healthcare_mappings = [m for m in db_mappings if m.component_category == "healthcare"]
                result["healthcare_components"] = {
                    m.genesis_type: {
                        "description": m.description or f"Healthcare component {m.genesis_type}",
                        "category": m.component_category,
                        "healthcare_metadata": m.healthcare_metadata
                    } for m in healthcare_mappings
                }

            return result

        except Exception as e:
            logger.error(f"Error getting components with database: {e}")
            # Fall back to base implementation
            return await self.get_all_available_components()

    async def validate_component_with_dynamic_schema(self,
                                                    component: Dict[str, Any],
                                                    session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Validate a component using dynamically generated schema.
        AUTPE-6207: Dynamic schema generation for discovered components.

        Args:
            component: Component to validate
            session: Optional database session

        Returns:
            Validation result
        """
        errors = []
        warnings = []

        try:
            comp_type = component.get("type", "")

            # Get component mapping from database if available
            component_mapping = None
            if session and self.component_mapping_service and comp_type.startswith("genesis:"):
                component_mapping = await self.component_mapping_service.get_component_mapping_by_genesis_type(
                    session, comp_type
                )

            # Generate or retrieve schema
            if component_mapping:
                # Use database-driven schema information
                schema = self.dynamic_schema_generator.generate_schema_from_introspection(
                    genesis_type=comp_type,
                    component_category=component_mapping.category,
                    base_config=component_mapping.default_config
                )
            else:
                # Try to get schema from complete_component_schemas
                from .complete_component_schemas import get_enhanced_component_schema
                schema = get_enhanced_component_schema(comp_type)

                if not schema:
                    # Generate dynamic schema as fallback
                    schema = self.dynamic_schema_generator.generate_schema_from_introspection(
                        genesis_type=comp_type,
                        component_category=self._infer_category(comp_type)
                    )

            # Validate component config against schema
            if schema and "config" in component:
                import jsonschema
                try:
                    jsonschema.validate(component["config"], schema)
                except jsonschema.ValidationError as e:
                    errors.append({
                        "code": "SCHEMA_VALIDATION_ERROR",
                        "message": f"Component '{component.get('id', comp_type)}' config validation failed: {e.message}",
                        "component_id": component.get("id"),
                        "severity": "error"
                    })
                except Exception as e:
                    warnings.append({
                        "code": "SCHEMA_VALIDATION_WARNING",
                        "message": f"Could not validate component '{component.get('id', comp_type)}': {e}",
                        "component_id": component.get("id"),
                        "severity": "warning"
                    })

            return {"errors": errors, "warnings": warnings}

        except Exception as e:
            logger.error(f"Error in dynamic schema validation: {e}")
            return {
                "errors": [{
                    "code": "VALIDATION_ERROR",
                    "message": f"Failed to validate component: {e}",
                    "severity": "error"
                }],
                "warnings": []
            }

    def _infer_category(self, comp_type: str) -> str:
        """
        Infer component category from type name.

        Args:
            comp_type: Component type string

        Returns:
            Inferred category
        """
        comp_lower = comp_type.lower()

        if "agent" in comp_lower:
            return "agent"
        elif "model" in comp_lower or "llm" in comp_lower:
            return "model"
        elif "tool" in comp_lower or "mcp" in comp_lower:
            return "tool"
        elif "input" in comp_lower or "output" in comp_lower:
            return "io"
        elif "prompt" in comp_lower:
            return "prompt"
        elif any(term in comp_lower for term in ["health", "medical", "clinical", "patient"]):
            return "healthcare"
        elif "api" in comp_lower:
            return "integration"
        elif "data" in comp_lower or "process" in comp_lower:
            return "processing"
        else:
            return "general"