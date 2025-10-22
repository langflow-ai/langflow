"""
Component Mapper for Genesis to Langflow components - AUTPE-6205 Simplified Version.

This mapper now primarily uses database-driven mappings with minimal hardcoded fallbacks.
All component discovery is handled by the enhanced discovery service.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Import for database-driven mappings
try:
    from langflow.services.component_mapping.service import ComponentMappingService
    _database_mapping_available = True
except ImportError as e:
    logger.warning(f"Database mapping service not available: {e}")
    _database_mapping_available = False


class ComponentMapper:
    """Maps Genesis specification types to AI Studio (Langflow) components using database-first approach."""

    def __init__(self):
        """Initialize component mapper with database-driven mappings."""
        self._database_cache = {}  # Cache for database mappings

        # Initialize database service
        self.component_mapping_service = ComponentMappingService() if _database_mapping_available else None

        # Minimal fallback mappings for critical components only
        self._init_minimal_fallback_mappings()

    def _init_minimal_fallback_mappings(self):
        """Initialize minimal fallback mappings for critical components only."""
        # Only keep absolutely essential mappings that must work even without database
        self.FALLBACK_MAPPINGS = {
            # Core I/O components
            "genesis:chat_input": {"component": "ChatInput", "config": {}},
            "genesis:chat_output": {"component": "ChatOutput", "config": {}},
            "genesis:text_input": {"component": "TextInput", "config": {}},
            "genesis:text_output": {"component": "TextOutput", "config": {}},

            # Core agent
            "genesis:agent": {"component": "Agent", "config": {}},

            # Core prompt
            "genesis:prompt": {"component": "PromptComponent", "config": {}},
        }

        # Empty dicts for backward compatibility (to be removed in future)
        self.AUTONOMIZE_MODELS = {}
        self.MCP_MAPPINGS = {}
        self.STANDARD_MAPPINGS = {}

    async def map_component_async(self, spec_type: str, session=None) -> Dict[str, Any]:
        """
        Map a Genesis specification type to Langflow component using database-first approach.

        Args:
            spec_type: Component type from specification (e.g., "genesis:rxnorm")
            session: Database session for async operations

        Returns:
            Dictionary with component name and configuration
        """
        # 1. Check database mappings first (primary source)
        if self.component_mapping_service and session:
            try:
                db_mapping = await self.get_mapping_from_database_async(session, spec_type)
                if db_mapping:
                    # Cache the result
                    self._database_cache[spec_type] = db_mapping
                    logger.info(f"✓ Found database mapping for {spec_type}")
                    return db_mapping
            except Exception as e:
                logger.warning(f"Error getting database mapping for {spec_type}: {e}")

        # 2. Check cache
        if spec_type in self._database_cache:
            return self._database_cache[spec_type]

        # 3. Fallback to minimal mappings
        if spec_type in self.FALLBACK_MAPPINGS:
            logger.info(f"Using fallback mapping for {spec_type}")
            return self.FALLBACK_MAPPINGS[spec_type]

        # 4. Return generic unknown component
        logger.warning(f"No mapping found for {spec_type}, using generic component")
        return {
            "component": "Component",
            "config": {},
            "warning": f"No mapping found for {spec_type}"
        }

    def map_component(self, spec_type: str) -> Dict[str, Any]:
        """
        Synchronous wrapper for component mapping.

        Args:
            spec_type: Component type from specification

        Returns:
            Dictionary with component name and configuration
        """
        # Check cache first
        if spec_type in self._database_cache:
            return self._database_cache[spec_type]

        # Check fallback mappings
        if spec_type in self.FALLBACK_MAPPINGS:
            return self.FALLBACK_MAPPINGS[spec_type]

        # Return generic
        logger.warning(f"Sync mapping: No mapping found for {spec_type}")
        return {
            "component": "Component",
            "config": {},
            "warning": f"No mapping found for {spec_type}"
        }

    async def get_mapping_from_database_async(self, session, genesis_type: str) -> Optional[Dict[str, Any]]:
        """
        Get component mapping from database.

        Args:
            session: Database session
            genesis_type: Genesis component type

        Returns:
            Mapping dictionary or None
        """
        if not self.component_mapping_service:
            return None

        try:
            # Get the component mapping from database
            mapping = await self.component_mapping_service.get_component_mapping_by_genesis_type(
                session, genesis_type, active_only=True
            )

            if not mapping:
                return None

            # Get the runtime adapter for Langflow
            adapter = await self.component_mapping_service.get_runtime_adapter_for_genesis_type(
                session, genesis_type, runtime_type="langflow"
            )

            if adapter:
                return {
                    "component": adapter.target_component,
                    "config": adapter.adapter_config or mapping.base_config or {},
                    "dataType": mapping.io_mapping.get("dataType") if mapping.io_mapping else None
                }
            else:
                # Fallback to basic mapping info
                return {
                    "component": mapping.io_mapping.get("component") if mapping.io_mapping else "Component",
                    "config": mapping.base_config or {},
                    "dataType": mapping.io_mapping.get("dataType") if mapping.io_mapping else None
                }

        except Exception as e:
            logger.error(f"Error getting database mapping for {genesis_type}: {e}")
            return None

    async def populate_database_cache(self, session=None) -> int:
        """
        Populate the database cache with all available mappings.

        Args:
            session: Database session

        Returns:
            Number of mappings cached
        """
        if not self.component_mapping_service or not session:
            logger.warning("Cannot populate database cache - service or session unavailable")
            return 0

        try:
            # Get all component mappings from database
            mappings = await self.component_mapping_service.get_all_component_mappings(
                session, active_only=True, limit=10000
            )

            cached_count = 0
            for mapping in mappings:
                try:
                    # Get runtime adapter
                    adapter = await self.component_mapping_service.get_runtime_adapter_for_genesis_type(
                        session, mapping.genesis_type, runtime_type="langflow"
                    )

                    if adapter:
                        mapping_dict = {
                            "component": adapter.target_component,
                            "config": adapter.adapter_config or mapping.base_config or {},
                            "dataType": mapping.io_mapping.get("dataType") if mapping.io_mapping else None
                        }
                    else:
                        mapping_dict = {
                            "component": mapping.io_mapping.get("component") if mapping.io_mapping else "Component",
                            "config": mapping.base_config or {},
                            "dataType": mapping.io_mapping.get("dataType") if mapping.io_mapping else None
                        }

                    self._database_cache[mapping.genesis_type] = mapping_dict
                    cached_count += 1

                except Exception as e:
                    logger.debug(f"Error caching mapping for {mapping.genesis_type}: {e}")

            logger.info(f"✅ Populated database cache with {cached_count} mappings")
            return cached_count

        except Exception as e:
            logger.error(f"Error populating database cache: {e}")
            return 0

    def get_all_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all available mappings (database cache + fallbacks).

        Returns:
            Dictionary of all mappings
        """
        all_mappings = {}

        # Add database cache
        all_mappings.update(self._database_cache)

        # Add fallback mappings
        all_mappings.update(self.FALLBACK_MAPPINGS)

        return all_mappings

    def clear_cache(self):
        """Clear the database cache."""
        self._database_cache.clear()
        logger.info("Database cache cleared")

    def get_mapping_statistics(self) -> Dict[str, int]:
        """Get statistics about available mappings."""
        return {
            "database_cached": len(self._database_cache),
            "fallback_mappings": len(self.FALLBACK_MAPPINGS),
            "total": len(self._database_cache) + len(self.FALLBACK_MAPPINGS)
        }

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status for database mappings."""
        return {
            "cached_mappings": len(self._database_cache),
            "cached_types": list(self._database_cache.keys()),
            "fallback_mappings": len(self.FALLBACK_MAPPINGS),
            "has_database_service": self.component_mapping_service is not None
        }

    async def refresh_cache_from_database(self, session) -> Dict[str, Any]:
        """Refresh cache from database."""
        try:
            refreshed = await self.populate_database_cache(session)
            return {
                "success": True,
                "refreshed": refreshed,
                "total_cached": len(self._database_cache)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "total_cached": len(self._database_cache)
            }

    def _get_mapping_from_database(self, genesis_type: str) -> Optional[Dict[str, Any]]:
        """Get mapping from database cache."""
        return self._database_cache.get(genesis_type)

    def get_available_components(self) -> Dict[str, Any]:
        """Get available components from cache and fallbacks."""
        return {
            "discovered_components": self._database_cache,
            "fallback_components": self.FALLBACK_MAPPINGS,
            "total_components": len(self._database_cache) + len(self.FALLBACK_MAPPINGS)
        }

    def get_component_io_mapping(self, component_type: str = None) -> Dict[str, Any]:
        """
        Get input/output field mappings for component types from database.

        This method dynamically retrieves I/O mapping information from the database
        to support connection validation and field mapping in specifications.

        Args:
            component_type: Optional specific component type to get mapping for

        Returns:
            Dictionary with component I/O mappings from database:
            - If component_type provided: mapping for that specific component
            - If no component_type: all available I/O mappings from database cache
        """
        # Default mapping for unknown components
        default_mapping = {
            "input_field": "input_value",
            "output_field": "output",
            "input_types": ["Any"],
            "output_types": ["Any"]
        }

        if component_type:
            # Check database cache first
            if component_type in self._database_cache:
                db_mapping = self._database_cache[component_type]
                io_mapping = db_mapping.get("config", {}).get("io_mapping", {})

                if io_mapping:
                    return io_mapping

                # Fallback: derive from dataType if available
                data_type = db_mapping.get("dataType")
                if data_type:
                    return self._derive_io_mapping_from_datatype(data_type)

            # Check fallback mappings only for critical components
            if component_type in self.FALLBACK_MAPPINGS:
                fallback = self.FALLBACK_MAPPINGS[component_type]
                io_mapping = fallback.get("config", {}).get("io_mapping", {})
                if io_mapping:
                    return io_mapping

            # Return default for unknown components
            logger.debug(f"No I/O mapping found for {component_type}, using default")
            return default_mapping

        # Return all I/O mappings from database cache
        all_mappings = {}

        # Extract I/O mappings from database cache
        for genesis_type, mapping_data in self._database_cache.items():
            io_mapping = mapping_data.get("config", {}).get("io_mapping", {})
            if io_mapping:
                all_mappings[genesis_type] = io_mapping
            else:
                # Derive from dataType if available
                data_type = mapping_data.get("dataType")
                if data_type:
                    all_mappings[genesis_type] = self._derive_io_mapping_from_datatype(data_type)
                else:
                    all_mappings[genesis_type] = default_mapping

        return all_mappings

    def is_tool_component(self, spec_type: str) -> bool:
        """
        Check if a component type should be used as a tool using database-driven approach.

        This method determines whether a Genesis specification component type
        can be used as a tool by agents or other components based on database information.

        Args:
            spec_type: Genesis component type (e.g., "genesis:rxnorm")

        Returns:
            True if component can be used as a tool, False otherwise
        """
        if not spec_type:
            return False

        # Primary: Check database cache for explicit tool capability
        if spec_type in self._database_cache:
            db_mapping = self._database_cache[spec_type]

            # Check explicit dataType marking in database
            data_type = db_mapping.get("dataType")
            if data_type == "tool":
                logger.debug(f"✓ {spec_type} marked as tool in database")
                return True
            elif data_type in ["input", "output", "agent", "prompt"]:
                logger.debug(f"✗ {spec_type} marked as {data_type} in database")
                return False

            # Check component configuration for tool indicators
            config = db_mapping.get("config", {})
            if config.get("asTools") is True:
                logger.debug(f"✓ {spec_type} has asTools=true in database config")
                return True

            # Check component category in database
            component_category = config.get("component_category")
            if component_category in ["healthcare", "connector", "api", "tool"]:
                logger.debug(f"✓ {spec_type} in tool category '{component_category}'")
                return True

            # Get target component name and check capability
            component_name = db_mapping.get("component", "")
            if component_name and self._is_component_tool_capable_from_db(component_name, db_mapping):
                return True

        # Secondary: Check minimal fallback mappings only for critical components
        if spec_type in self.FALLBACK_MAPPINGS:
            fallback_mapping = self.FALLBACK_MAPPINGS[spec_type]
            component_name = fallback_mapping.get("component", "")
            # Only basic check for fallback
            if "tool" in component_name.lower() or "api" in component_name.lower():
                return True

        # Tertiary: Database-informed pattern detection
        logger.debug(f"Using pattern detection for {spec_type}")
        return self._detect_tool_capability_by_pattern(spec_type)

    def _derive_io_mapping_from_datatype(self, data_type: str) -> Dict[str, Any]:
        """Derive I/O mapping from component dataType."""
        type_mappings = {
            "input": {
                "input_field": None,
                "output_field": "output",
                "input_types": [],
                "output_types": ["str", "Any"]
            },
            "output": {
                "input_field": "input_value",
                "output_field": "output",
                "input_types": ["Any"],
                "output_types": ["str"]
            },
            "tool": {
                "input_field": "input_value",
                "output_field": "output",
                "input_types": ["Any"],
                "output_types": ["Any"]
            },
            "agent": {
                "input_field": "input_value",
                "output_field": "response",
                "input_types": ["str", "Message", "Any"],
                "output_types": ["str", "Message"]
            }
        }
        return type_mappings.get(data_type, {
            "input_field": "input_value",
            "output_field": "output",
            "input_types": ["Any"],
            "output_types": ["Any"]
        })

    def _is_component_tool_capable_from_db(self, component_name: str, db_mapping: Dict[str, Any]) -> bool:
        """Check if a component is tool-capable using database information."""
        if not component_name:
            return False

        # Check explicit config flags from database
        config = db_mapping.get("config", {})
        if config.get("is_tool") is True:
            return True
        if config.get("is_tool") is False:
            return False

        # Check component category from database
        category = config.get("component_category", "").lower()
        if category in ["healthcare", "connector", "api", "tool", "utility"]:
            return True
        if category in ["input", "output", "agent", "prompt"]:
            return False

        # Fallback to name pattern check
        component_lower = component_name.lower()
        tool_indicators = [
            "tool", "api", "request", "search", "calculator", "connector",
            "mcp", "function", "custom", "autonomize", "model"
        ]
        non_tool_indicators = [
            "input", "output", "chat", "text", "agent", "prompt"
        ]

        if any(indicator in component_lower for indicator in non_tool_indicators):
            return False
        if any(indicator in component_lower for indicator in tool_indicators):
            return True
        return False

    def _detect_tool_capability_by_pattern(self, spec_type: str) -> bool:
        """Detect tool capability based on Genesis type patterns."""
        if not spec_type.startswith("genesis:"):
            return False

        base_type = spec_type.replace("genesis:", "").lower()

        # Known tool patterns in Genesis types
        tool_patterns = [
            "tool", "connector", "api", "search", "calculator", "mcp",
            "encoder", "lookup", "eligibility", "rxnorm", "icd", "cpt",
            "claims", "prior_auth", "pa_lookup", "autonomize"
        ]

        # Known non-tool patterns
        non_tool_patterns = [
            "input", "output", "chat", "text", "agent", "prompt", "crew"
        ]

        # Check non-tool patterns first (higher precedence)
        if any(pattern in base_type for pattern in non_tool_patterns):
            return False

        # Check tool patterns
        if any(pattern in base_type for pattern in tool_patterns):
            return True

        # Default to False for unknown patterns
        return False