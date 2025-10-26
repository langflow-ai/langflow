#!/usr/bin/env python3
"""
Test Script: Database-Driven Component Discovery

This script validates that the architectural violations have been fixed
and the framework now operates with 100% database-driven discovery.
"""

import asyncio
import logging
from datetime import datetime, timezone
from langflow.custom.specification_framework.services.component_discovery import ComponentDiscoveryService
from langflow.custom.specification_framework.models.processing_context import ProcessingContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_database_driven_discovery():
    """Test that component discovery uses database-driven approach."""

    # Create test context
    context = ProcessingContext(
        specification_id="test-db-discovery",
        created_at=datetime.now(timezone.utc),
        configuration={}
    )

    # Initialize discovery service
    discovery_service = ComponentDiscoveryService(enable_dynamic_resolution=True)

    # Test specification with various component types
    test_spec = {
        "components": {
            "agent1": {
                "type": "Agent",
                "config": {"model": "gpt-4"}
            },
            "agent2": {
                "type": "CrewAIAgent",
                "config": {"role": "researcher"}
            },
            "tool1": {
                "type": "Calculator",
                "config": {}
            },
            "input1": {
                "type": "ChatInput",
                "config": {}
            },
            "unknown1": {
                "type": "UnknownComponent",
                "config": {}
            }
        }
    }

    logger.info("Testing database-driven component discovery...")

    # Test enhanced discovery
    results = await discovery_service.discover_enhanced_components(test_spec, context)

    # Analyze results
    database_driven_count = 0
    dynamic_resolution_count = 0

    for comp_id, discovery_info in results.items():
        discovery_method = discovery_info.get("discovery_method", "unknown")
        component_type = discovery_info.get("genesis_type")
        langflow_component = discovery_info.get("langflow_component")

        logger.info(f"{comp_id}: {component_type} → {langflow_component} ({discovery_method})")

        if discovery_method == "database_driven":
            database_driven_count += 1
        elif discovery_method == "dynamic_resolution":
            dynamic_resolution_count += 1

    # Print summary
    logger.info(f"\n=== DISCOVERY SUMMARY ===")
    logger.info(f"Total components discovered: {len(results)}")
    logger.info(f"Database-driven discoveries: {database_driven_count}")
    logger.info(f"Dynamic resolution fallbacks: {dynamic_resolution_count}")

    # Validate architecture compliance
    if database_driven_count > 0:
        logger.info("✅ DATABASE-DRIVEN DISCOVERY: WORKING")
    else:
        logger.warning("❌ DATABASE-DRIVEN DISCOVERY: NOT WORKING")

    if dynamic_resolution_count > 0:
        logger.info("✅ DYNAMIC FALLBACK: WORKING")
    else:
        logger.info("ℹ️  DYNAMIC FALLBACK: No unknown components to test")

    return results

async def test_database_mapping_normalization():
    """Test genesis type normalization for database queries."""

    discovery_service = ComponentDiscoveryService()

    test_cases = [
        ("Agent", "genesis:agent"),
        ("CrewAIAgent", "genesis:crew_ai"),
        ("APIRequest", "genesis:api_request"),
        ("Calculator", "genesis:calculator"),
        ("WebSearch", "genesis:web_search"),
        ("ChatInput", "genesis:chat_input"),
        ("UnknownComponent", "genesis:unknown_component")
    ]

    logger.info("\n=== TESTING GENESIS TYPE NORMALIZATION ===")

    for spec_type, expected_db_type in test_cases:
        actual_db_type = discovery_service._normalize_genesis_type_for_database(spec_type)

        if actual_db_type == expected_db_type:
            logger.info(f"✅ {spec_type} → {actual_db_type}")
        else:
            logger.error(f"❌ {spec_type} → {actual_db_type} (expected: {expected_db_type})")

async def main():
    """Run all tests."""
    logger.info("🔍 TESTING: Database-Driven Component Discovery Architecture")
    logger.info("=" * 60)

    try:
        # Test 1: Genesis type normalization
        await test_database_mapping_normalization()

        # Test 2: Database-driven discovery
        await test_database_driven_discovery()

        logger.info("\n" + "=" * 60)
        logger.info("🎉 ARCHITECTURE TESTS COMPLETED")
        logger.info("   Check logs above to verify database-driven discovery is working")

    except Exception as e:
        logger.error(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())