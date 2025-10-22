"""
Component Mapper for Genesis to Langflow components - Refactored for AUTPE-6204.

This mapper now uses a database-first approach with dynamic discovery,
eliminating all hardcoded mappings.
"""

from typing import Dict, Any, Optional
import logging
import copy

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
_component_mapping_service = None
_component_registry = None
_seed_loader = None


class ComponentMapper:
    """Maps Genesis specification types to AI Studio (Langflow) components using database-first approach."""

    def __init__(self):
        """Initialize component mapper with database-driven mappings."""
        self._use_database = True  # Always use database
        self._database_cache = {}  # Cache for database mappings
        self._fallback_mappings = {}  # Emergency fallback only

        # Initialize services
        self._init_services()

    def _init_services(self):
        """Initialize required services lazily."""
        global _component_mapping_service, _component_registry, _seed_loader

        try:
            if _component_mapping_service is None:
                from langflow.services.component_mapping.service import ComponentMappingService
                _component_mapping_service = ComponentMappingService()

            if _component_registry is None:
                from langflow.services.component_mapping.component_registry import ComponentRegistry
                _component_registry = ComponentRegistry()

            if _seed_loader is None:
                from langflow.seed_data.seed_loader import SeedDataLoader
                _seed_loader = SeedDataLoader()

            self.component_mapping_service = _component_mapping_service
            self.component_registry = _component_registry
            self.seed_loader = _seed_loader

            # Initialize registry on first use
            if not self.component_registry.is_initialized():
                logger.info("Initializing component registry for dynamic discovery...")
                self.component_registry.discover_components()

        except ImportError as e:
            logger.warning(f"Could not initialize services: {e}")
            self.component_mapping_service = None
            self.component_registry = None
            self.seed_loader = None

    async def map_component_async(self, spec_type: str, session=None) -> Dict[str, Any]:
        """
        Map a Genesis specification type to Langflow component using database.

        Args:
            spec_type: Component type from specification (e.g., "genesis:rxnorm")
            session: Database session for async operations

        Returns:
            Dictionary with component name and configuration
        """
        logger.info(f"[DATABASE-FIRST] Mapping {spec_type}")

        # 1. Check database cache first
        if spec_type in self._database_cache:
            logger.info(f"✓ Found cached mapping for {spec_type}")
            return self._database_cache[spec_type]

        # 2. Query database for mapping
        if self.component_mapping_service and session:
            try:
                mapping = await self.component_mapping_service.get_component_mapping_by_genesis_type(
                    session, spec_type, active_only=True
                )

                if mapping:
                    result = self._convert_db_mapping_to_dict(mapping)
                    self._database_cache[spec_type] = result
                    logger.info(f"✓ Found database mapping for {spec_type}")
                    return result

            except Exception as e:
                logger.warning(f"Error querying database for {spec_type}: {e}")

        # 3. Check component registry (dynamic discovery)
        if self.component_registry:
            component = self.component_registry.get_component_by_genesis_type(spec_type)
            if component:
                result = {
                    "component": component.name,
                    "config": {},
                    "dataType": self._infer_data_type(component.category)
                }
                logger.info(f"✓ Found dynamically discovered component for {spec_type}")
                return result

        # 4. Generate intelligent fallback
        logger.warning(f"No mapping found for {spec_type}, using intelligent fallback")
        return self._handle_unknown_type(spec_type)

    def map_component(self, spec_type: str) -> Dict[str, Any]:
        """
        Synchronous mapping method for backward compatibility.

        Args:
            spec_type: Component type from specification

        Returns:
            Dictionary with component name and configuration
        """
        # Check cache first
        if spec_type in self._database_cache:
            return copy.deepcopy(self._database_cache[spec_type])

        # Check registry
        if self.component_registry:
            component = self.component_registry.get_component_by_genesis_type(spec_type)
            if component:
                return {
                    "component": component.name,
                    "config": {},
                    "dataType": self._infer_data_type(component.category)
                }

        # Fallback
        return self._handle_unknown_type(spec_type)

    def _convert_db_mapping_to_dict(self, mapping) -> Dict[str, Any]:
        """Convert database mapping object to dictionary format."""
        result = {
            "component": None,
            "config": mapping.base_config or {},
            "dataType": None,
        }

        if mapping.io_mapping:
            result["component"] = mapping.io_mapping.get("component")
            result["dataType"] = mapping.io_mapping.get("dataType")

        return result

    def _handle_unknown_type(self, spec_type: str) -> Dict[str, Any]:
        """Handle unknown component types with intelligent fallbacks."""
        # Remove genesis: prefix if present
        base_type = spec_type.replace("genesis:", "") if spec_type.startswith("genesis:") else spec_type

        # Pattern-based fallbacks
        if "model" in base_type.lower() or "llm" in base_type.lower():
            if any(term in base_type.lower() for term in ["clinical", "rxnorm", "icd", "cpt", "medical"]):
                logger.warning(f"Unknown clinical model type '{spec_type}', using AutonomizeModel")
                return {"component": "AutonomizeModel", "config": {}}
            else:
                logger.warning(f"Unknown LLM type '{spec_type}', using OpenAIModel")
                return {"component": "OpenAIModel", "config": {}}

        elif "agent" in base_type.lower():
            logger.warning(f"Unknown agent type '{spec_type}', using Agent")
            return {"component": "Agent", "config": {}}

        elif "tool" in base_type.lower() or "component" in base_type.lower():
            logger.warning(f"Unknown tool/component type '{spec_type}', using MCPToolsComponent")
            return {"component": "MCPToolsComponent", "config": {}}

        elif "memory" in base_type.lower():
            logger.warning(f"Unknown memory type '{spec_type}', using Memory")
            return {"component": "Memory", "config": {}}

        elif "prompt" in base_type.lower():
            logger.warning(f"Unknown prompt type '{spec_type}', using PromptComponent")
            return {"component": "PromptComponent", "config": {}}

        elif "input" in base_type.lower():
            logger.warning(f"Unknown input type '{spec_type}', using ChatInput")
            return {"component": "ChatInput", "config": {}}

        elif "output" in base_type.lower():
            logger.warning(f"Unknown output type '{spec_type}', using ChatOutput")
            return {"component": "ChatOutput", "config": {}}

        else:
            # Default to MCPToolsComponent for complete unknowns
            logger.warning(f"Completely unknown type '{spec_type}', using MCPToolsComponent as fallback")
            return {"component": "MCPToolsComponent", "config": {}}

    def _infer_data_type(self, category: str) -> str:
        """Infer data type from component category."""
        category_types = {
            "models": "Message",
            "agents": "Message",
            "tools": "Data",
            "memories": "Message",
            "prompts": "Message",
            "io": "Data",
            "data": "Data",
            "vectorstores": "Document",
            "healthcare": "Data",
        }
        return category_types.get(category.lower(), "Any")

    async def populate_database_cache(self, session) -> int:
        """
        Populate the cache from database.

        Args:
            session: Database session

        Returns:
            Number of mappings cached
        """
        if not self.component_mapping_service:
            logger.warning("Component mapping service not available")
            return 0

        try:
            mappings = await self.component_mapping_service.get_all_component_mappings(
                session, active_only=True, limit=1000
            )

            cached_count = 0
            for mapping in mappings:
                mapping_dict = self._convert_db_mapping_to_dict(mapping)
                if mapping_dict["component"]:
                    self._database_cache[mapping.genesis_type] = mapping_dict
                    cached_count += 1

            logger.info(f"Populated cache with {cached_count} mappings from database")
            return cached_count

        except Exception as e:
            logger.error(f"Error populating cache: {e}")
            return 0

    def get_component_io_mapping(self, component_type: str = None) -> Dict[str, Any]:
        """
        Get input/output field mappings for component types.

        Args:
            component_type: Optional specific component type

        Returns:
            Dictionary with component I/O mappings
        """
        if not self.component_registry:
            return {}

        components = self.component_registry.get_all_components()

        if component_type:
            component = components.get(component_type)
            if component:
                return {
                    "input_field": self._get_primary_field(component.input_fields),
                    "output_field": self._get_primary_field(component.output_fields),
                    "input_types": component.input_fields.get("_input_types", ["Any"]),
                    "output_types": component.output_fields.get("_output_types", ["Any"]),
                }
            return {
                "input_field": "input_value",
                "output_field": "output",
                "output_types": ["Any"],
                "input_types": ["any"]
            }

        # Return all mappings
        all_mappings = {}
        for name, component in components.items():
            all_mappings[name] = {
                "input_field": self._get_primary_field(component.input_fields),
                "output_field": self._get_primary_field(component.output_fields),
                "input_types": component.input_fields.get("_input_types", ["Any"]),
                "output_types": component.output_fields.get("_output_types", ["Any"]),
            }

        return all_mappings

    def _get_primary_field(self, fields: Dict[str, Any]) -> Optional[str]:
        """Get the primary field from a field dictionary."""
        if not fields:
            return None

        # Look for common primary field names
        primary_names = ["input_value", "output", "input", "result", "data", "message", "text"]

        for name in primary_names:
            if name in fields:
                return name

        # Return first non-private field
        public_fields = [k for k in fields.keys() if not k.startswith("_")]
        return public_fields[0] if public_fields else None

    def is_tool_component(self, spec_type: str) -> bool:
        """Check if a component type should be used as a tool."""
        # Check registry first
        if self.component_registry:
            component = self.component_registry.get_component_by_genesis_type(spec_type)
            if component and "tool" in component.capabilities:
                return True

        # Check if it's in known tool patterns
        tool_patterns = [
            "tool", "connector", "api", "search", "calculator",
            "mcp", "encoder", "pa_lookup", "eligibility"
        ]

        base_type = spec_type.replace("genesis:", "").lower()
        return any(pattern in base_type for pattern in tool_patterns)

    def get_available_components(self) -> Dict[str, Dict[str, Any]]:
        """Get all available components from registry."""
        if not self.component_registry:
            return {}

        components = self.component_registry.get_all_components()

        result = {
            "discovered": {},
            "healthcare": {},
        }

        for name, metadata in components.items():
            component_info = {
                "name": metadata.name,
                "display_name": metadata.display_name,
                "category": metadata.category,
                "genesis_type": metadata.genesis_type,
                "capabilities": metadata.capabilities,
            }

            if metadata.is_healthcare:
                result["healthcare"][name] = component_info
            else:
                result["discovered"][name] = component_info

        return result

    def clear_cache(self):
        """Clear the mapping cache."""
        self._database_cache.clear()
        logger.info("Mapping cache cleared")

    def get_cache_status(self) -> Dict[str, Any]:
        """Get status of the mapping cache."""
        return {
            "cache_enabled": True,
            "cached_mappings": len(self._database_cache),
            "cached_types": list(self._database_cache.keys()),
            "registry_initialized": self.component_registry.is_initialized() if self.component_registry else False,
        }