#!/usr/bin/env python3
"""
Missing Database Mappings Migration Script

This script creates the database entries that were previously hardcoded in
component_discovery.py static mappings. This migration is CRITICAL for the
100% database-driven architecture to work.

ARCHITECTURAL PRINCIPLE: ALL component mappings must exist in the database.
NO STATIC MAPPINGS are allowed in the codebase.
"""

import asyncio
import logging
from sqlmodel.ext.asyncio.session import AsyncSession
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.component_mapping import ComponentMappingCreate, ComponentCategoryEnum
from langflow.services.deps import get_session

logger = logging.getLogger(__name__)

# CRITICAL: These are the mappings that were extracted from static code
# Each entry maps a genesis type to its Langflow component
REQUIRED_DATABASE_MAPPINGS = {
    # Agent Components (from removed agent_mappings)
    "genesis:agent": {
        "component": "ToolCallingAgent",  # Primary mapping for generic "Agent"
        "category": ComponentCategoryEnum.AGENT,
        "description": "Generic agent component mapping",
        "tool_capabilities": {
            "accepts_tools": True,
            "provides_tools": False,
            "discovery_method": "database_migration"
        }
    },
    "genesis:crew_ai": {
        "component": "CrewAIAgentComponent",
        "category": ComponentCategoryEnum.AGENT,
        "description": "CrewAI agent component mapping",
        "tool_capabilities": {
            "accepts_tools": True,
            "provides_tools": True,  # CrewAI agents can provide tools
            "discovery_method": "database_migration"
        }
    },
    "genesis:simple_agent": {
        "component": "ToolCallingAgent",
        "category": ComponentCategoryEnum.AGENT,
        "description": "Simple agent component mapping",
        "tool_capabilities": {
            "accepts_tools": True,
            "provides_tools": False,
            "discovery_method": "database_migration"
        }
    },
    "genesis:tool_calling_agent": {
        "component": "ToolCallingAgent",
        "category": ComponentCategoryEnum.AGENT,
        "description": "Tool calling agent component mapping",
        "tool_capabilities": {
            "accepts_tools": True,
            "provides_tools": False,
            "discovery_method": "database_migration"
        }
    },

    # Tool Components (from removed tool_mappings)
    "genesis:api_request": {
        "component": "APIRequest",  # Primary mapping for API requests
        "category": ComponentCategoryEnum.TOOL,
        "description": "API request tool component mapping",
        "tool_capabilities": {
            "accepts_tools": False,
            "provides_tools": True,
            "discovery_method": "database_migration"
        }
    },
    "genesis:calculator": {
        "component": "Calculator",
        "category": ComponentCategoryEnum.TOOL,
        "description": "Calculator tool component mapping",
        "tool_capabilities": {
            "accepts_tools": False,
            "provides_tools": True,
            "discovery_method": "database_migration"
        }
    },
    "genesis:web_search": {
        "component": "DuckDuckGoSearchComponent",  # Primary search component
        "category": ComponentCategoryEnum.TOOL,
        "description": "Web search tool component mapping",
        "tool_capabilities": {
            "accepts_tools": False,
            "provides_tools": True,
            "discovery_method": "database_migration"
        }
    },

    # I/O Components (from test data)
    "genesis:chat_input": {
        "component": "ChatInput",
        "category": ComponentCategoryEnum.IO,
        "description": "Chat input component mapping",
        "tool_capabilities": {
            "accepts_tools": False,
            "provides_tools": False,
            "discovery_method": "database_migration"
        }
    },
    "genesis:chat_output": {
        "component": "ChatOutput",
        "category": ComponentCategoryEnum.IO,
        "description": "Chat output component mapping",
        "tool_capabilities": {
            "accepts_tools": False,
            "provides_tools": False,
            "discovery_method": "database_migration"
        }
    },

    # MCP Tools (from test data)
    "genesis:mcp_tool": {
        "component": "MCPTools",
        "category": ComponentCategoryEnum.TOOL,
        "description": "MCP tools component mapping",
        "tool_capabilities": {
            "accepts_tools": False,
            "provides_tools": True,
            "discovery_method": "database_migration"
        }
    }
}

async def migrate_missing_database_mappings():
    """
    Migrate missing database mappings that were previously hardcoded.

    This function ensures the database contains all necessary mappings
    for the 100% database-driven component discovery to work.
    """
    service = ComponentMappingService()

    async for session in get_session():
        try:
            logger.info(f"Starting migration of {len(REQUIRED_DATABASE_MAPPINGS)} component mappings")

            created_count = 0
            updated_count = 0
            skipped_count = 0
            errors = []

            for genesis_type, mapping_info in REQUIRED_DATABASE_MAPPINGS.items():
                try:
                    # Check if mapping already exists
                    existing = await service.get_component_mapping_by_genesis_type(
                        session, genesis_type, active_only=False
                    )

                    # Prepare mapping data
                    base_config = {
                        "component": mapping_info["component"],
                        "migrated_from": "static_mappings",
                        "migration_timestamp": "2025-01-25T00:00:00Z"
                    }

                    mapping_data = ComponentMappingCreate(
                        genesis_type=genesis_type,
                        base_config=base_config,
                        component_category=mapping_info["category"].value,
                        description=mapping_info["description"],
                        tool_capabilities=mapping_info["tool_capabilities"],
                        version="1.0.0",
                        active=True
                    )

                    if existing:
                        logger.info(f"Mapping exists for {genesis_type}, skipping")
                        skipped_count += 1
                    else:
                        # Create new mapping
                        await service.create_component_mapping(session, mapping_data)
                        logger.info(f"Created mapping: {genesis_type} → {mapping_info['component']}")
                        created_count += 1

                except Exception as e:
                    error_msg = f"Failed to migrate {genesis_type}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Commit all changes
            await session.commit()

            logger.info(f"Migration completed: {created_count} created, {updated_count} updated, {skipped_count} skipped")
            if errors:
                logger.error(f"Errors encountered: {errors}")

            return {
                "created": created_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "errors": errors
            }

        except Exception as e:
            await session.rollback()
            logger.error(f"Migration failed: {e}")
            raise

async def validate_database_mappings():
    """
    Validate that all required database mappings exist and are correct.

    Returns:
        Dict with validation results
    """
    service = ComponentMappingService()

    async for session in get_session():
        validation_results = {
            "valid": True,
            "missing_mappings": [],
            "incorrect_mappings": [],
            "total_checked": len(REQUIRED_DATABASE_MAPPINGS)
        }

        for genesis_type, expected_mapping in REQUIRED_DATABASE_MAPPINGS.items():
            try:
                mapping = await service.get_component_mapping_by_genesis_type(
                    session, genesis_type, active_only=True
                )

                if not mapping:
                    validation_results["missing_mappings"].append(genesis_type)
                    validation_results["valid"] = False
                    continue

                # Check if component matches expected
                actual_component = mapping.base_config.get("component") if mapping.base_config else None
                expected_component = expected_mapping["component"]

                if actual_component != expected_component:
                    validation_results["incorrect_mappings"].append({
                        "genesis_type": genesis_type,
                        "expected": expected_component,
                        "actual": actual_component
                    })
                    validation_results["valid"] = False

            except Exception as e:
                logger.error(f"Error validating {genesis_type}: {e}")
                validation_results["missing_mappings"].append(genesis_type)
                validation_results["valid"] = False

        return validation_results

if __name__ == "__main__":
    # Run migration
    asyncio.run(migrate_missing_database_mappings())

    # Validate results
    validation = asyncio.run(validate_database_mappings())
    print("Validation Results:", validation)