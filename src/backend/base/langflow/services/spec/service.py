"""Specification Service for business logic."""

import yaml
from typing import Dict, Any, Optional, List
import logging

from langflow.custom.genesis.spec import FlowConverter, ComponentMapper, VariableResolver
from langflow.services.spec.component_template_service import component_template_service
from langflow.services.database.models.flow import Flow, FlowCreate
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.deps import get_session
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

    def validate_spec(self, spec_yaml: str) -> Dict[str, Any]:
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

            # Validate components
            component_validation = self._validate_components(spec_dict.get("components", []))
            validation["warnings"].extend(component_validation["warnings"])

            return validation

        except yaml.YAMLError as e:
            return {
                "valid": False,
                "errors": [f"Invalid YAML format: {e}"],
                "warnings": []
            }
        except Exception as e:
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