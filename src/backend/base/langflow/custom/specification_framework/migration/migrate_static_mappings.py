"""
Migration script to move hardcoded component mappings to database.

This script addresses the critical architectural violation where static mappings
were introduced into a system designed for 100% dynamic database-driven discovery.
"""

import asyncio
import logging
from typing import Dict, List

from sqlmodel.ext.asyncio.session import AsyncSession
from langflow.services.deps import get_session
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.component_mapping import (
    ComponentMappingCreate,
    ComponentCategoryEnum
)

logger = logging.getLogger(__name__)

# Extract all hardcoded mappings from component_discovery.py for migration
STATIC_MAPPINGS_TO_MIGRATE = {
    "genesis:agent": {
        "component": "ToolCallingAgent",
        "alternates": ["Tool Calling Agent", "OpenAIToolsAgent"],
        "category": ComponentCategoryEnum.AGENT,
        "tool_capabilities": {
            "accepts_tools": True,
            "provides_tools": False,
            "discovery_method": "migrated_from_static"
        },
        "description": "Generic agent component migrated from static mapping"
    },
    "genesis:crewai_agent": {
        "component": "CrewAIAgentComponent",
        "alternates": ["CrewAI Agent"],
        "category": ComponentCategoryEnum.AGENT,
        "tool_capabilities": {
            "accepts_tools": True,
            "provides_tools": True,
            "discovery_method": "migrated_from_static"
        },
        "description": "CrewAI agent component migrated from static mapping"
    },
    "genesis:simple_agent": {
        "component": "ToolCallingAgent",
        "alternates": ["Tool Calling Agent"],
        "category": ComponentCategoryEnum.AGENT,
        "tool_capabilities": {
            "accepts_tools": True,
            "provides_tools": False,
            "discovery_method": "migrated_from_static"
        },
        "description": "Simple agent component migrated from static mapping"
    },
    "genesis:tool_calling_agent": {
        "component": "ToolCallingAgent",
        "alternates": ["Tool Calling Agent"],
        "category": ComponentCategoryEnum.AGENT,
        "tool_capabilities": {
            "accepts_tools": True,
            "provides_tools": False,
            "discovery_method": "migrated_from_static"
        },
        "description": "Tool calling agent component migrated from static mapping"
    },
    "genesis:api_request": {
        "component": "BingSearchAPI",
        "alternates": ["FirecrawlScrapeApi", "OpenAPIAgent", "APIRequest", "API Request"],
        "category": ComponentCategoryEnum.TOOL,
        "tool_capabilities": {
            "accepts_tools": False,
            "provides_tools": True,
            "discovery_method": "migrated_from_static"
        },
        "description": "API request tool component migrated from static mapping"
    },
    "genesis:calculator": {
        "component": "Calculator",
        "alternates": ["Math Calculator"],
        "category": ComponentCategoryEnum.TOOL,
        "tool_capabilities": {
            "accepts_tools": False,
            "provides_tools": True,
            "discovery_method": "migrated_from_static"
        },
        "description": "Calculator tool component migrated from static mapping"
    },
    "genesis:web_search": {
        "component": "DuckDuckGoSearchComponent",
        "alternates": ["BingSearchAPI", "SearchComponent", "GoogleSerperAPICore", "WebSearch", "Web Search", "Search"],
        "category": ComponentCategoryEnum.TOOL,
        "tool_capabilities": {
            "accepts_tools": False,
            "provides_tools": True,
            "discovery_method": "migrated_from_static"
        },
        "description": "Web search tool component migrated from static mapping"
    }
}


async def migrate_static_mappings(overwrite_existing: bool = False) -> Dict[str, int]:
    """
    Migrate all static mappings from component_discovery.py to database.

    Args:
        overwrite_existing: Whether to overwrite existing database mappings

    Returns:
        Migration results summary
    """
    session_gen = get_session()
    session = await session_gen.__anext__()
    service = ComponentMappingService()

    results = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0
    }

    try:
        logger.info(f"Starting migration of {len(STATIC_MAPPINGS_TO_MIGRATE)} static mappings")

        for genesis_type, mapping_info in STATIC_MAPPINGS_TO_MIGRATE.items():
            try:
                # Check if mapping already exists
                existing = await service.get_component_mapping_by_genesis_type(
                    session, genesis_type, active_only=False
                )

                if existing and not overwrite_existing:
                    logger.info(f"Skipping existing mapping: {genesis_type}")
                    results["skipped"] += 1
                    continue

                # Create mapping data
                mapping_data = ComponentMappingCreate(
                    genesis_type=genesis_type,
                    base_config={
                        "component": mapping_info["component"],
                        "alternates": mapping_info.get("alternates", [])
                    },
                    component_category=mapping_info["category"].value,
                    tool_capabilities=mapping_info["tool_capabilities"],
                    description=mapping_info["description"],
                    version="1.0.0",
                    active=True
                )

                if existing:
                    # Update existing mapping
                    from langflow.services.database.models.component_mapping import ComponentMappingUpdate
                    update_data = ComponentMappingUpdate(
                        base_config=mapping_data.base_config,
                        component_category=mapping_data.component_category,
                        tool_capabilities=mapping_data.tool_capabilities,
                        description=mapping_data.description,
                        version=mapping_data.version,
                        active=mapping_data.active
                    )
                    await service.update_component_mapping(session, existing.id, update_data)
                    results["updated"] += 1
                    logger.info(f"Updated mapping: {genesis_type}")
                else:
                    # Create new mapping
                    await service.create_component_mapping(session, mapping_data)
                    results["created"] += 1
                    logger.info(f"Created mapping: {genesis_type}")

            except Exception as e:
                logger.error(f"Error migrating {genesis_type}: {e}")
                results["errors"] += 1

        logger.info(f"Migration completed: {results}")
        return results

    finally:
        await session_gen.aclose()


async def validate_migration() -> bool:
    """
    Validate that all static mappings have been successfully migrated.

    Returns:
        True if all mappings are present in database
    """
    session_gen = get_session()
    session = await session_gen.__anext__()
    service = ComponentMappingService()

    try:
        all_valid = True

        for genesis_type in STATIC_MAPPINGS_TO_MIGRATE.keys():
            mapping = await service.get_component_mapping_by_genesis_type(
                session, genesis_type, active_only=True
            )

            if not mapping:
                logger.error(f"Missing mapping for {genesis_type}")
                all_valid = False
            elif not mapping.base_config or not mapping.base_config.get("component"):
                logger.error(f"Invalid mapping for {genesis_type}: missing component")
                all_valid = False
            else:
                logger.info(f"Validated mapping: {genesis_type} -> {mapping.base_config['component']}")

        return all_valid

    finally:
        await session_gen.aclose()


async def main():
    """Run the migration process."""
    logger.info("Starting static mapping migration process")

    # Run migration
    results = await migrate_static_mappings(overwrite_existing=True)
    print(f"Migration Results: {results}")

    # Validate migration
    validation_passed = await validate_migration()
    print(f"Migration Validation: {'PASSED' if validation_passed else 'FAILED'}")

    if validation_passed:
        print("\n✅ Static mappings successfully migrated to database")
        print("⚠️  Next step: Remove static mappings from component_discovery.py")
    else:
        print("\n❌ Migration validation failed - check logs for details")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())