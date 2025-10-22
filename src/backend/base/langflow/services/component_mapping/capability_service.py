"""Component capability service for dynamic tool capability validation."""

import logging
from typing import Dict, List, Optional, Set, Any
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.base import Service
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingUpdate,
    ComponentCategoryEnum,
)

logger = logging.getLogger(__name__)


class ComponentCapabilityService(Service):
    """Service for managing and validating component tool capabilities dynamically."""

    name = "component_capability_service"

    def __init__(self):
        """Initialize the component capability service."""
        super().__init__()
        self.component_mapping_service = ComponentMappingService()
        # In-memory cache for frequently accessed capabilities
        self._capability_cache: Dict[str, Dict] = {}

    async def get_tool_capabilities(
        self,
        session: AsyncSession,
        genesis_type: str,
        use_cache: bool = True,
    ) -> Optional[Dict]:
        """
        Get tool capabilities for a specific genesis component type.

        Args:
            session: Database session
            genesis_type: Genesis component type (e.g., 'genesis:agent')
            use_cache: Whether to use in-memory cache

        Returns:
            Tool capabilities dictionary or None if not found
        """
        # Check cache first
        if use_cache and genesis_type in self._capability_cache:
            logger.debug(f"Using cached capabilities for {genesis_type}")
            return self._capability_cache[genesis_type]

        # Query database
        mapping = await self.component_mapping_service.get_component_mapping_by_genesis_type(
            session, genesis_type, active_only=True
        )

        if not mapping or not mapping.tool_capabilities:
            logger.debug(f"No tool capabilities found for {genesis_type}")
            return None

        capabilities = mapping.tool_capabilities

        # Cache the result
        if use_cache:
            self._capability_cache[genesis_type] = capabilities

        return capabilities

    async def component_accepts_tools(
        self,
        session: AsyncSession,
        target_type: str,
    ) -> bool:
        """
        Check if a component can accept tools based on database capabilities.

        This replaces the static validation logic from converter.py.

        Args:
            session: Database session
            target_type: Component type to check

        Returns:
            True if component can accept tools, False otherwise
        """
        if not target_type or target_type == "None":
            logger.warning(f"Target type is None or invalid: {repr(target_type)}")
            return False

        # Get capabilities from database
        capabilities = await self.get_tool_capabilities(session, target_type)

        if capabilities:
            accepts_tools = capabilities.get("accepts_tools", False)
            logger.debug(f"Database lookup: '{target_type}' accepts tools: {accepts_tools}")
            return accepts_tools

        # Fallback: check if component is inherently tool-accepting based on category
        mapping = await self.component_mapping_service.get_component_mapping_by_genesis_type(
            session, target_type, active_only=True
        )

        if mapping:
            # Agent components can typically accept tools
            if mapping.component_category == ComponentCategoryEnum.AGENT.value:
                logger.debug(f"Agent component '{target_type}' can accept tools by category")
                return True

            # Check runtime introspection data
            if mapping.runtime_introspection:
                introspected_accepts = mapping.runtime_introspection.get("accepts_tools", False)
                logger.debug(f"Runtime introspection: '{target_type}' accepts tools: {introspected_accepts}")
                return introspected_accepts

        logger.debug(f"Component '{target_type}' cannot accept tools")
        return False

    async def component_provides_tools(
        self,
        session: AsyncSession,
        source_type: str,
    ) -> bool:
        """
        Check if a component can provide tools based on database capabilities.

        This replaces the static validation logic from converter.py.

        Args:
            session: Database session
            source_type: Component type to check

        Returns:
            True if component can provide tools, False otherwise
        """
        if not source_type:
            logger.warning(f"Source type is None or invalid: {repr(source_type)}")
            return False

        # Get capabilities from database
        capabilities = await self.get_tool_capabilities(session, source_type)

        if capabilities:
            provides_tools = capabilities.get("provides_tools", False)
            logger.debug(f"Database lookup: '{source_type}' provides tools: {provides_tools}")
            return provides_tools

        # Fallback: check if component is inherently tool-providing based on category
        mapping = await self.component_mapping_service.get_component_mapping_by_genesis_type(
            session, source_type, active_only=True
        )

        if mapping:
            # Tool components can typically provide tools
            if mapping.component_category == ComponentCategoryEnum.TOOL.value:
                logger.debug(f"Tool component '{source_type}' can provide tools by category")
                return True

            # Check runtime introspection data
            if mapping.runtime_introspection:
                introspected_provides = mapping.runtime_introspection.get("provides_tools", False)
                logger.debug(f"Runtime introspection: '{source_type}' provides tools: {introspected_provides}")
                return introspected_provides

        logger.debug(f"Component '{source_type}' cannot provide tools")
        return False

    async def update_tool_capabilities(
        self,
        session: AsyncSession,
        genesis_type: str,
        capabilities: Dict[str, Any],
        overwrite: bool = False,
    ) -> bool:
        """
        Update tool capabilities for a component.

        Args:
            session: Database session
            genesis_type: Genesis component type
            capabilities: Tool capabilities dictionary
            overwrite: Whether to overwrite existing capabilities

        Returns:
            True if update was successful
        """
        mapping = await self.component_mapping_service.get_component_mapping_by_genesis_type(
            session, genesis_type, active_only=False
        )

        if not mapping:
            logger.warning(f"No mapping found for {genesis_type}")
            return False

        # Merge or overwrite capabilities
        if overwrite or not mapping.tool_capabilities:
            new_capabilities = capabilities
        else:
            new_capabilities = mapping.tool_capabilities.copy()
            new_capabilities.update(capabilities)

        # Update the mapping
        update_data = ComponentMappingUpdate(
            tool_capabilities=new_capabilities
        )

        updated_mapping = await self.component_mapping_service.update_component_mapping(
            session, mapping.id, update_data
        )

        if updated_mapping:
            # Invalidate cache
            self._capability_cache.pop(genesis_type, None)
            logger.info(f"Updated tool capabilities for {genesis_type}")
            return True

        return False

    async def update_runtime_introspection(
        self,
        session: AsyncSession,
        genesis_type: str,
        introspection_data: Dict[str, Any],
        overwrite: bool = False,
    ) -> bool:
        """
        Update runtime introspection data for a component.

        Args:
            session: Database session
            genesis_type: Genesis component type
            introspection_data: Runtime introspection data
            overwrite: Whether to overwrite existing data

        Returns:
            True if update was successful
        """
        mapping = await self.component_mapping_service.get_component_mapping_by_genesis_type(
            session, genesis_type, active_only=False
        )

        if not mapping:
            logger.warning(f"No mapping found for {genesis_type}")
            return False

        # Merge or overwrite introspection data
        if overwrite or not mapping.runtime_introspection:
            new_introspection = introspection_data
        else:
            new_introspection = mapping.runtime_introspection.copy()
            new_introspection.update(introspection_data)

        # Update the mapping
        update_data = ComponentMappingUpdate(
            runtime_introspection=new_introspection
        )

        updated_mapping = await self.component_mapping_service.update_component_mapping(
            session, mapping.id, update_data
        )

        if updated_mapping:
            # Invalidate cache
            self._capability_cache.pop(genesis_type, None)
            logger.info(f"Updated runtime introspection for {genesis_type}")
            return True

        return False

    async def introspect_component_capabilities(
        self,
        session: AsyncSession,
        genesis_type: str,
        component_class: Any = None,
    ) -> Dict[str, Any]:
        """
        Introspect component capabilities using data-driven discovery.

        Args:
            session: Database session
            genesis_type: Genesis component type
            component_class: Component class for introspection (optional)

        Returns:
            Dictionary with discovered capabilities
        """
        from datetime import datetime, timezone

        capabilities = {
            "accepts_tools": False,
            "provides_tools": False,
            "tool_methods": [],
            "discovery_method": "unified_introspection",
            "introspection_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # If we have the actual component class, introspect it directly
        if component_class:
            capabilities.update(self._introspect_component_class(component_class))
            capabilities["discovery_method"] = "class_introspection"
        else:
            # Use unified discovery service for data-driven introspection
            try:
                from langflow.services.component_mapping.discovery import UnifiedComponentDiscovery

                discovery = UnifiedComponentDiscovery()
                # This would ideally discover just the specific component, but for now we use the cached data

                # Check if we have introspection data in the database
                mapping = await self.component_mapping_service.get_component_mapping_by_genesis_type(
                    session, genesis_type, active_only=False
                )

                if mapping:
                    if mapping.introspection_data:
                        # Use introspection data from database
                        capabilities["discovery_method"] = "database_introspection"

                        # Extract capabilities from introspection data
                        if mapping.tool_capabilities:
                            capabilities["accepts_tools"] = mapping.tool_capabilities.get("accepts_tools", False)
                            capabilities["provides_tools"] = mapping.tool_capabilities.get("provides_tools", False)
                            capabilities["tool_methods"] = mapping.tool_capabilities.get("tool_methods", [])

                        # Special case: Agents are BOTH tool acceptors AND providers
                        if mapping.component_category == ComponentCategoryEnum.AGENT.value:
                            capabilities["accepts_tools"] = True
                            capabilities["provides_tools"] = True

                    elif mapping.runtime_introspection:
                        # Fallback to runtime introspection
                        capabilities["accepts_tools"] = mapping.runtime_introspection.get("accepts_tools", False)
                        capabilities["provides_tools"] = mapping.runtime_introspection.get("provides_tools", False)
                        capabilities["discovery_method"] = "runtime_introspection"

            except Exception as e:
                logger.warning(f"Error during unified introspection for {genesis_type}: {e}")
                capabilities["discovery_method"] = "fallback_minimal"

        return capabilities

    def _introspect_component_class(self, component_class: Any) -> Dict[str, Any]:
        """
        Introspect a component class for tool capabilities.

        Args:
            component_class: Component class to introspect

        Returns:
            Dictionary with discovered capabilities from class
        """
        capabilities = {
            "accepts_tools": False,
            "provides_tools": False,
            "tool_methods": [],
        }

        if not component_class:
            return capabilities

        try:
            # Check for tool-related attributes
            if hasattr(component_class, 'asTools'):
                capabilities["provides_tools"] = True

            if hasattr(component_class, 'tools') or hasattr(component_class, 'tool_list'):
                capabilities["accepts_tools"] = True

            # Check for tool-related methods
            tool_methods = []
            for attr_name in dir(component_class):
                if attr_name.startswith('tool_') or 'tool' in attr_name.lower():
                    tool_methods.append(attr_name)

            capabilities["tool_methods"] = tool_methods

            if tool_methods:
                capabilities["provides_tools"] = True

        except Exception as e:
            logger.warning(f"Error introspecting component class: {e}")

        return capabilities

    async def get_components_by_capability(
        self,
        session: AsyncSession,
        capability: str,
        value: bool = True,
    ) -> List[ComponentMapping]:
        """
        Get all components that have a specific capability.

        Args:
            session: Database session
            capability: Capability name (e.g., 'accepts_tools', 'provides_tools')
            value: Capability value to match

        Returns:
            List of component mappings with the specified capability
        """
        all_mappings = await self.component_mapping_service.get_all_component_mappings(
            session, active_only=True, limit=1000
        )

        matching_components = []

        for mapping in all_mappings:
            if mapping.tool_capabilities:
                if mapping.tool_capabilities.get(capability) == value:
                    matching_components.append(mapping)
            elif mapping.runtime_introspection:
                if mapping.runtime_introspection.get(capability) == value:
                    matching_components.append(mapping)

        return matching_components

    async def validate_tool_connection(
        self,
        session: AsyncSession,
        source_type: str,
        target_type: str,
    ) -> Dict[str, Any]:
        """
        Validate if a tool connection between two components is valid.

        Args:
            session: Database session
            source_type: Source component type (tool provider)
            target_type: Target component type (tool acceptor)

        Returns:
            Validation result dictionary
        """
        result = {
            "valid": False,
            "source_provides": False,
            "target_accepts": False,
            "warnings": [],
            "errors": [],
        }

        # Check if source can provide tools
        source_provides = await self.component_provides_tools(session, source_type)
        result["source_provides"] = source_provides

        # Check if target can accept tools
        target_accepts = await self.component_accepts_tools(session, target_type)
        result["target_accepts"] = target_accepts

        # Determine validity
        if source_provides and target_accepts:
            result["valid"] = True
        else:
            if not source_provides:
                result["errors"].append(f"Source component '{source_type}' cannot provide tools")
            if not target_accepts:
                result["errors"].append(f"Target component '{target_type}' cannot accept tools")

        return result

    def clear_capability_cache(self) -> None:
        """Clear the in-memory capability cache."""
        self._capability_cache.clear()
        logger.info("Cleared component capability cache")

    async def get_capability_statistics(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Get statistics about component capabilities in the database.

        Args:
            session: Database session

        Returns:
            Statistics dictionary
        """
        all_mappings = await self.component_mapping_service.get_all_component_mappings(
            session, active_only=True, limit=1000
        )

        stats = {
            "total_components": len(all_mappings),
            "components_with_capabilities": 0,
            "components_with_introspection": 0,
            "accepts_tools_count": 0,
            "provides_tools_count": 0,
            "capability_coverage": 0.0,
        }

        for mapping in all_mappings:
            if mapping.tool_capabilities:
                stats["components_with_capabilities"] += 1
                if mapping.tool_capabilities.get("accepts_tools", False):
                    stats["accepts_tools_count"] += 1
                if mapping.tool_capabilities.get("provides_tools", False):
                    stats["provides_tools_count"] += 1

            if mapping.runtime_introspection:
                stats["components_with_introspection"] += 1

        if stats["total_components"] > 0:
            stats["capability_coverage"] = (
                stats["components_with_capabilities"] / stats["total_components"]
            ) * 100.0

        return stats