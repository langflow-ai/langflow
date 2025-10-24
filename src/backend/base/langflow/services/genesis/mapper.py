"""ComponentMapper for Genesis specification framework."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class ComponentMapper:
    """Maps Genesis specification types to Langflow components."""

    def __init__(self):
        """Initialize the ComponentMapper with hardcoded mappings and database cache."""
        self._database_cache = {}
        self._last_cache_refresh = None

        # Core hardcoded mappings for MVP functionality
        self.STANDARD_MAPPINGS = {
            "genesis:agent": {
                "component": "Agent",
                "config": {
                    "input_value": "",
                    "system_message": "You are a helpful assistant specialized in your domain.",
                    "tools": []
                },
                "category": "agent",
                "io_mapping": {
                    "input_field": "input_value",
                    "output_field": "response",
                    "output_types": ["Message"],
                    "input_types": ["Message", "str"]
                }
            },
            "genesis:chat_input": {
                "component": "ChatInput",
                "config": {
                    "input_value": "",
                    "sender_type": "User",
                    "sender_name": "User",
                    "session_id": "",
                    "should_store_message": True
                },
                "category": "input",
                "io_mapping": {
                    "input_field": None,
                    "output_field": "message",
                    "output_types": ["Message"],
                    "input_types": []
                }
            },
            "genesis:chat_output": {
                "component": "ChatOutput",
                "config": {
                    "input_value": "",
                    "sender_type": "Machine",
                    "sender_name": "Assistant",
                    "session_id": "",
                    "should_store_message": True
                },
                "category": "output",
                "io_mapping": {
                    "input_field": "input_value",
                    "output_field": "message",
                    "output_types": ["Message"],
                    "input_types": ["Message", "str"]
                }
            },
            "genesis:api_request": {
                "component": "APIRequest",
                "config": {
                    "url_input": "",
                    "method": "GET",
                    "headers": {},
                    "body": "",
                    "timeout": 30
                },
                "category": "tool",
                "io_mapping": {
                    "input_field": "url_input",
                    "output_field": "response",
                    "output_types": ["Data"],
                    "input_types": ["str"]
                }
            }
        }

        # Healthcare-specific mappings
        self.HEALTHCARE_MAPPINGS = {
            "genesis:ehr_connector": {
                "component": "EHRConnector",
                "config": {
                    "url_input": "",
                    "api_key": "",
                    "patient_id": "",
                    "fhir_version": "R4",
                    "hipaa_compliant": True
                },
                "category": "healthcare",
                "io_mapping": {
                    "input_field": "patient_id",
                    "output_field": "patient_data",
                    "output_types": ["Data"],
                    "input_types": ["str"]
                }
            },
            "genesis:eligibility_connector": {
                "component": "EligibilityConnector",
                "config": {
                    "url_input": "",
                    "api_key": "",
                    "member_id": "",
                    "plan_id": "",
                    "hipaa_compliant": True
                },
                "category": "healthcare",
                "io_mapping": {
                    "input_field": "member_id",
                    "output_field": "eligibility_data",
                    "output_types": ["Data"],
                    "input_types": ["str"]
                }
            },
            "genesis:claims_connector": {
                "component": "ClaimsConnector",
                "config": {
                    "url_input": "",
                    "api_key": "",
                    "claim_id": "",
                    "date_range": "",
                    "hipaa_compliant": True
                },
                "category": "healthcare",
                "io_mapping": {
                    "input_field": "claim_id",
                    "output_field": "claims_data",
                    "output_types": ["Data"],
                    "input_types": ["str"]
                }
            }
        }

        # Model mappings
        self.MODEL_MAPPINGS = {
            "genesis:autonomize_model": {
                "component": "AutonomizeModel",
                "config": {
                    "selected_model": "Clinical LLM",
                    "search_query": "",
                    "temperature": 0.1,
                    "max_tokens": 1000
                },
                "category": "model",
                "io_mapping": {
                    "input_field": "search_query",
                    "output_field": "prediction",
                    "output_types": ["Message"],
                    "input_types": ["str"]
                }
            }
        }

    def map_component(self, genesis_type: str) -> Dict[str, Any]:
        """
        Map Genesis component type to Langflow component.

        Args:
            genesis_type: Genesis component type (e.g., 'genesis:agent')

        Returns:
            Mapping dictionary with component, config, and metadata
        """
        # Check database cache first
        if genesis_type in self._database_cache:
            return self._database_cache[genesis_type]

        # Check hardcoded mappings
        all_mappings = {
            **self.STANDARD_MAPPINGS,
            **self.HEALTHCARE_MAPPINGS,
            **self.MODEL_MAPPINGS
        }

        if genesis_type in all_mappings:
            return all_mappings[genesis_type]

        # Fallback to intelligent mapping
        return self._handle_unknown_type(genesis_type)

    def _handle_unknown_type(self, genesis_type: str) -> Dict[str, Any]:
        """
        Handle unknown Genesis component types with intelligent fallback.

        Args:
            genesis_type: Unknown genesis type

        Returns:
            Fallback mapping
        """
        logger.warning(f"Unknown genesis type: {genesis_type}, using intelligent fallback")

        # Remove genesis: prefix for analysis
        base_type = genesis_type.replace("genesis:", "").lower()

        # Intelligent component mapping based on name patterns
        if "agent" in base_type:
            base_mapping = self.STANDARD_MAPPINGS["genesis:agent"]
        elif "input" in base_type:
            base_mapping = self.STANDARD_MAPPINGS["genesis:chat_input"]
        elif "output" in base_type:
            base_mapping = self.STANDARD_MAPPINGS["genesis:chat_output"]
        elif any(term in base_type for term in ["api", "request", "tool"]):
            base_mapping = self.STANDARD_MAPPINGS["genesis:api_request"]
        elif any(term in base_type for term in ["model", "llm", "ai"]):
            base_mapping = self.MODEL_MAPPINGS["genesis:autonomize_model"]
        else:
            # Generic fallback
            base_mapping = {
                "component": "CustomComponent",
                "config": {},
                "category": "tool",
                "io_mapping": {
                    "input_field": "input_value",
                    "output_field": "output",
                    "output_types": ["Data"],
                    "input_types": ["str"]
                }
            }

        # Create a copy with updated metadata
        fallback_mapping = base_mapping.copy()
        fallback_mapping["_fallback"] = True
        fallback_mapping["_original_type"] = genesis_type

        return fallback_mapping

    def get_component_io_mapping(self, component_name: str) -> Dict[str, Any]:
        """
        Get I/O mapping for a Langflow component.

        Args:
            component_name: Langflow component name

        Returns:
            I/O mapping information
        """
        # Search through all mappings to find the component
        all_mappings = {
            **self.STANDARD_MAPPINGS,
            **self.HEALTHCARE_MAPPINGS,
            **self.MODEL_MAPPINGS,
            **self._database_cache
        }

        for genesis_type, mapping in all_mappings.items():
            if mapping.get("component") == component_name:
                return mapping.get("io_mapping", {})

        # Default I/O mapping
        return {
            "input_field": "input_value",
            "output_field": "output",
            "output_types": ["Data"],
            "input_types": ["str"]
        }

    def is_tool_component(self, genesis_type: str) -> bool:
        """
        Check if a genesis component can be used as a tool.

        Args:
            genesis_type: Genesis component type

        Returns:
            True if component can be used as a tool
        """
        mapping = self.map_component(genesis_type)
        category = mapping.get("category", "")

        # Tool categories
        tool_categories = ["tool", "healthcare", "integration"]
        if category in tool_categories:
            return True

        # Specific component types that can be tools
        tool_types = [
            "genesis:api_request",
            "genesis:ehr_connector",
            "genesis:eligibility_connector",
            "genesis:claims_connector",
            "genesis:autonomize_model"
        ]

        return genesis_type in tool_types

    def get_available_components(self) -> Dict[str, Any]:
        """
        Get all available Genesis component mappings.

        Returns:
            Dictionary of available components
        """
        all_mappings = {
            **self.STANDARD_MAPPINGS,
            **self.HEALTHCARE_MAPPINGS,
            **self.MODEL_MAPPINGS,
            **self._database_cache
        }

        return {
            "total_mappings": len(all_mappings),
            "hardcoded_mappings": len(self.STANDARD_MAPPINGS) + len(self.HEALTHCARE_MAPPINGS) + len(self.MODEL_MAPPINGS),
            "database_mappings": len(self._database_cache),
            "discovered_components": all_mappings,
            "categories": self._get_category_stats(all_mappings)
        }

    def _get_category_stats(self, mappings: Dict[str, Any]) -> Dict[str, int]:
        """Get statistics by category."""
        stats = {}
        for mapping in mappings.values():
            category = mapping.get("category", "unknown")
            stats[category] = stats.get(category, 0) + 1
        return stats

    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get current cache status.

        Returns:
            Cache status information
        """
        return {
            "cached_mappings": len(self._database_cache),
            "last_refresh": self._last_cache_refresh.isoformat() if self._last_cache_refresh else None,
            "cached_types": list(self._database_cache.keys())
        }

    async def refresh_cache_from_database(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Refresh component mapping cache from database.

        Args:
            session: Database session

        Returns:
            Refresh result
        """
        try:
            from langflow.services.component_mapping.service import ComponentMappingService

            service = ComponentMappingService()
            mappings = await service.get_all_component_mappings(session, active_only=True, limit=1000)

            refreshed_count = 0
            for mapping in mappings:
                try:
                    # Use properties for backward compatibility, with fallbacks
                    langflow_component = getattr(mapping, 'langflow_component', None) or "CustomComponent"
                    default_config = getattr(mapping, 'default_config', None) or mapping.base_config or {}
                    category = getattr(mapping, 'category', None) or mapping.component_category or "tool"

                    mapping_dict = {
                        "component": langflow_component,
                        "config": default_config,
                        "category": category,
                        "io_mapping": mapping.io_mapping or {},
                        "database_id": str(mapping.id)
                    }

                    self._database_cache[mapping.genesis_type] = mapping_dict
                    refreshed_count += 1

                except Exception as mapping_error:
                    logger.warning(f"Error processing mapping {mapping.genesis_type}: {mapping_error}, skipping")
                    continue

            self._last_cache_refresh = datetime.now(timezone.utc)

            logger.info(f"Refreshed cache with {refreshed_count} database mappings")
            return {
                "refreshed": refreshed_count,
                "total_cached": len(self._database_cache),
                "timestamp": self._last_cache_refresh.isoformat()
            }

        except Exception as e:
            logger.error(f"Error refreshing cache from database: {e}")
            return {"error": str(e), "refreshed": 0}

    def _get_mapping_from_database(self, genesis_type: str) -> Optional[Dict[str, Any]]:
        """Get mapping from database cache."""
        return self._database_cache.get(genesis_type)

    # ========================================
    # BACKWARD COMPATIBILITY PROPERTIES
    # ========================================
    # These properties maintain backward compatibility with SpecService
    # while preserving the new consolidated architecture

    @property
    def AUTONOMIZE_MODELS(self) -> Dict[str, Any]:
        """
        Backward compatibility property for AUTONOMIZE_MODELS.

        Returns model mappings from the consolidated MODEL_MAPPINGS.
        This maintains compatibility with SpecService without architectural regression.
        """
        return self.MODEL_MAPPINGS

    @property
    def MCP_MAPPINGS(self) -> Dict[str, Any]:
        """
        Backward compatibility property for MCP_MAPPINGS.

        Returns an empty dict as MCP components have been deprecated.
        This maintains compatibility with SpecService while gracefully handling
        the deprecation of MCP tools.
        """
        # MCP components were deprecated during the MVP implementation
        # Return empty dict to maintain compatibility while indicating deprecation
        logger.debug("MCP_MAPPINGS accessed - MCP components are deprecated, returning empty mappings")
        return {}