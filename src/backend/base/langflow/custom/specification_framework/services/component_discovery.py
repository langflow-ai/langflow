"""
Component Discovery Service

Professional service for discovering and mapping agent specification components
to Langflow components using database-driven discovery.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from langflow.services.component_mapping.service import ComponentMappingService
from ..models.processing_context import ProcessingContext

logger = logging.getLogger(__name__)


class ComponentDiscoveryService:
    """
    Professional service for component discovery and mapping.

    This service replaces the poorly named 'mapper' with a comprehensive
    component discovery system that uses database-driven component mappings.
    """

    def __init__(self, component_mapping_service: Optional[ComponentMappingService] = None):
        """
        Initialize component discovery service.

        Args:
            component_mapping_service: Database-driven component mapping service
        """
        self.component_mapping_service = component_mapping_service or ComponentMappingService()

    async def discover_components(self,
                                spec_dict: Dict[str, Any],
                                context: ProcessingContext) -> Dict[str, Dict[str, Any]]:
        """
        Discover and map all components in a specification.

        Args:
            spec_dict: Agent specification dictionary
            context: Processing context

        Returns:
            Dictionary mapping component IDs to their discovery information
        """
        components = spec_dict.get("components", {})

        # Normalize components to consistent format
        component_items = self._normalize_component_format(components)

        discovery_results = {}

        for comp_id, comp_data in component_items:
            try:
                discovery_info = await self._discover_single_component(
                    comp_id, comp_data, context
                )

                if discovery_info:
                    discovery_results[comp_id] = discovery_info
                    logger.debug(f"Discovered component {comp_id}: {discovery_info['langflow_component']}")
                else:
                    logger.warning(f"Failed to discover component {comp_id}")

            except Exception as e:
                logger.error(f"Error discovering component {comp_id}: {e}")
                continue

        logger.info(f"Discovered {len(discovery_results)} components from {len(component_items)} specifications")
        return discovery_results

    def _normalize_component_format(self, components: Any) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Normalize component format to list of (id, data) tuples.

        Args:
            components: Components in dict or list format

        Returns:
            List of (component_id, component_data) tuples
        """
        if isinstance(components, dict):
            # Dict format: {comp_id: comp_data}
            return [(comp_id, comp_data) for comp_id, comp_data in components.items()]
        elif isinstance(components, list):
            # List format: [{id: comp_id, ...comp_data}]
            normalized = []
            for i, comp in enumerate(components):
                comp_id = comp.get("id", f"component_{i}")
                normalized.append((comp_id, comp))
            return normalized
        else:
            logger.error(f"Invalid component format: {type(components)}")
            return []

    async def _discover_single_component(self,
                                       comp_id: str,
                                       comp_data: Dict[str, Any],
                                       context: ProcessingContext) -> Optional[Dict[str, Any]]:
        """
        Discover mapping information for a single component.

        Args:
            comp_id: Component identifier
            comp_data: Component specification data
            context: Processing context

        Returns:
            Component discovery information or None if discovery fails
        """
        comp_type = comp_data.get("type")
        if not comp_type:
            logger.error(f"Component {comp_id} missing required 'type' field")
            return None

        try:
            # Use database-driven component mapping service
            mapping_info = await self.component_mapping_service.get_component_mapping(comp_type)

            if not mapping_info:
                logger.warning(f"No mapping found for component type: {comp_type}")
                return None

            # Extract langflow component name
            langflow_component = mapping_info.get("langflow_component")
            if not langflow_component:
                # Fallback to base_config component name
                base_config = mapping_info.get("base_config", {})
                langflow_component = base_config.get("component")

            if not langflow_component:
                logger.error(f"No Langflow component found for {comp_type}")
                return None

            # Build comprehensive discovery result
            discovery_result = {
                "genesis_type": comp_type,
                "langflow_component": langflow_component,
                "mapping_info": mapping_info,
                "component_data": comp_data,
                "io_mapping": mapping_info.get("io_mapping", {}),
                "tool_capabilities": mapping_info.get("tool_capabilities", {}),
                "healthcare_compliant": self._is_healthcare_compliant(comp_type, mapping_info),
                "discovered_at": context.created_at.isoformat()
            }

            return discovery_result

        except Exception as e:
            logger.error(f"Error in component discovery for {comp_id}: {e}")
            return None

    def _is_healthcare_compliant(self, comp_type: str, mapping_info: Dict[str, Any]) -> bool:
        """
        Determine if a component is healthcare/HIPAA compliant.

        Args:
            comp_type: Genesis component type
            mapping_info: Component mapping information

        Returns:
            True if component is healthcare compliant
        """
        # Check for explicit healthcare compliance markers
        tool_capabilities = mapping_info.get("tool_capabilities", {})
        if tool_capabilities.get("hipaa_compliant"):
            return True

        # Check for healthcare-related component types
        healthcare_types = [
            "ehr", "eligibility", "claims", "medical", "patient", "phi",
            "clinical", "diagnosis", "medication", "treatment"
        ]

        return any(term in comp_type.lower() for term in healthcare_types)

    async def get_component_io_info(self, comp_type: str) -> Dict[str, Any]:
        """
        Get input/output information for a component type.

        Args:
            comp_type: Genesis component type

        Returns:
            IO mapping information
        """
        try:
            mapping_info = await self.component_mapping_service.get_component_mapping(comp_type)
            if mapping_info:
                return mapping_info.get("io_mapping", {})
            return {}

        except Exception as e:
            logger.error(f"Error getting IO info for {comp_type}: {e}")
            return {}

    async def is_tool_component(self, comp_type: str) -> bool:
        """
        Check if a component can be used as a tool.

        Args:
            comp_type: Genesis component type

        Returns:
            True if component can be used as a tool
        """
        try:
            mapping_info = await self.component_mapping_service.get_component_mapping(comp_type)
            if not mapping_info:
                return False

            tool_capabilities = mapping_info.get("tool_capabilities", {})
            return tool_capabilities.get("provides_tools", False)

        except Exception as e:
            logger.error(f"Error checking tool capability for {comp_type}: {e}")
            return False