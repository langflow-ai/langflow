"""Specification Service for business logic."""

import yaml
from typing import Dict, Any, Optional, List
import logging

from langflow.custom.genesis.spec import FlowConverter, ComponentMapper, VariableResolver
from langflow.services.spec.component_template_service import component_template_service
from langflow.services.database.models.flow import Flow, FlowCreate
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.api.utils import DbSession
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)


class SpecService:
    """Business logic service for agent specification operations."""

    def __init__(self):
        """Initialize the service."""
        self.mapper = ComponentMapper()
        self.converter = FlowConverter(self.mapper)
        self.resolver = VariableResolver()

    async def convert_spec_to_flow(self, spec_yaml: str,
                                  variables: Optional[Dict[str, Any]] = None,
                                  tweaks: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Convert YAML specification to Langflow JSON.

        Args:
            spec_yaml: YAML specification string
            variables: Runtime variables for resolution
            tweaks: Component field tweaks to apply

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

            # Convert to flow
            flow = await self.converter.convert(spec_dict, variables)

            # Apply tweaks if provided
            if tweaks:
                flow = self.resolver.apply_tweaks(flow, tweaks)

            return flow

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}")
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
        # Convert to flow
        flow_data = await self.convert_spec_to_flow(spec_yaml, variables, tweaks)

        # Create flow in database using real Langflow database logic
        flow_id = await self._save_flow_to_database(flow_data, name, session, user_id, folder_id)

        return flow_id

    async def validate_spec(self, spec_yaml: str) -> Dict[str, Any]:
        """
        Validate specification without converting.

        Args:
            spec_yaml: YAML specification string

        Returns:
            Validation result with errors and warnings
        """
        try:
            # Parse YAML
            spec_dict = yaml.safe_load(spec_yaml)
            if not spec_dict:
                return {
                    "valid": False,
                    "errors": ["Empty or invalid YAML"],
                    "warnings": []
                }

            # Validate structure
            validation = self._validate_spec_structure(spec_dict)

            # Get available components for validation
            available_components = await self.get_all_available_components()

            # Validate components with enhanced logic
            component_validation = await self._validate_components_enhanced(
                spec_dict.get("components", []),
                available_components
            )

            # Merge validation results
            validation["errors"].extend(component_validation["errors"])
            validation["warnings"].extend(component_validation["warnings"])

            # Update valid status
            validation["valid"] = len(validation["errors"]) == 0

            return validation

        except yaml.YAMLError as e:
            return {
                "valid": False,
                "errors": [f"Invalid YAML format: {e}"],
                "warnings": []
            }
        except Exception as e:
            logger.error(f"Error in validate_spec: {e}")
            return {
                "valid": False,
                "errors": [f"Validation error: {e}"],
                "warnings": []
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
        This method is for internal use by components, no auth required.

        Returns:
            Dictionary containing:
            - langflow_components: All Langflow components
            - genesis_mapped: Genesis-mapped components
            - unmapped: Components without genesis mappings
        """
        try:
            from langflow.interface.components import get_and_cache_all_types_dict
            from langflow.services.settings.service import get_settings_service

            # Get ALL Langflow components
            all_langflow = await get_and_cache_all_types_dict(get_settings_service())

            # Get genesis mappings
            genesis_mapped = {}
            genesis_mapped.update(self.mapper.AUTONOMIZE_MODELS)
            genesis_mapped.update(self.mapper.MCP_MAPPINGS)
            genesis_mapped.update(self.mapper.STANDARD_MAPPINGS)

            # Find unmapped components
            unmapped = []
            if all_langflow and "components" in all_langflow:
                for category, components in all_langflow["components"].items():
                    for comp_name in components.keys():
                        # Check if this component has a genesis mapping
                        has_mapping = False
                        for genesis_type, mapping in genesis_mapped.items():
                            if mapping.get("component") == comp_name:
                                has_mapping = True
                                break

                        if not has_mapping:
                            unmapped.append({
                                "name": comp_name,
                                "category": category,
                                "suggestion": f"genesis:{comp_name.lower().replace(' ', '_')}"
                            })

            return {
                "langflow_components": all_langflow,
                "genesis_mapped": genesis_mapped,
                "unmapped": unmapped,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error getting all available components: {e}")
            # Return basic fallback with genesis mappings at least
            return {
                "langflow_components": {},
                "genesis_mapped": {
                    **self.mapper.AUTONOMIZE_MODELS,
                    **self.mapper.MCP_MAPPINGS,
                    **self.mapper.STANDARD_MAPPINGS
                },
                "unmapped": [],
                "success": False,
                "error": str(e)
            }