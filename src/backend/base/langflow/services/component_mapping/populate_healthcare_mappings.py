"""Script to populate database with healthcare connector mappings."""

import asyncio
import logging
from typing import Dict, Any

from langflow.services.component_mapping.healthcare_mappings import (
    get_healthcare_component_mappings,
    get_healthcare_runtime_adapters,
)
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.component_mapping.model import ComponentMappingCreate
from langflow.services.database.models.component_mapping.runtime_adapter import (
    RuntimeAdapterCreate,
    RuntimeTypeEnum,
)
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service

logger = logging.getLogger(__name__)


async def populate_healthcare_component_mappings(session, overwrite_existing: bool = False) -> Dict[str, Any]:
    """Populate database with healthcare component mappings."""
    service = ComponentMappingService()
    mappings = get_healthcare_component_mappings()

    results = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
    }

    for genesis_type, mapping_data in mappings.items():
        try:
            # Check if mapping already exists
            existing = await service.get_component_mapping_by_genesis_type(
                session, genesis_type, active_only=False
            )

            if existing and not overwrite_existing:
                results["skipped"] += 1
                logger.info(f"Skipping existing mapping: {genesis_type}")
                continue

            # Create mapping data
            mapping_create = ComponentMappingCreate(
                genesis_type=genesis_type,
                base_config=mapping_data.get("config", {}),
                io_mapping=mapping_data.get("io_mapping", {}),
                component_category=mapping_data.get("category"),
                healthcare_metadata=mapping_data.get("healthcare_metadata", {}),
                description=mapping_data.get("description", ""),
                version=mapping_data.get("version", "1.0.0"),
                active=True,
            )

            if existing:
                # Update existing mapping
                from langflow.services.database.models.component_mapping.model import ComponentMappingUpdate
                update_data = ComponentMappingUpdate(**mapping_create.model_dump())
                await service.update_component_mapping(session, existing.id, update_data)
                results["updated"] += 1
                logger.info(f"Updated healthcare mapping: {genesis_type}")
            else:
                # Create new mapping
                await service.create_component_mapping(session, mapping_create)
                results["created"] += 1
                logger.info(f"Created healthcare mapping: {genesis_type}")

        except Exception as e:
            logger.error(f"Error processing healthcare mapping {genesis_type}: {e}")
            results["errors"].append(f"{genesis_type}: {str(e)}")

    return results


async def populate_healthcare_runtime_adapters(session, overwrite_existing: bool = False) -> Dict[str, Any]:
    """Populate database with healthcare runtime adapters."""
    service = ComponentMappingService()
    adapters = get_healthcare_runtime_adapters()

    results = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
    }

    for genesis_type, runtime_adapters in adapters.items():
        for runtime_type, adapter_data in runtime_adapters.items():
            try:
                # Convert runtime type string to enum
                runtime_enum = RuntimeTypeEnum(runtime_type.lower())

                # Check if adapter already exists
                existing = await service.get_runtime_adapter_for_genesis_type(
                    session, genesis_type, runtime_enum, active_only=False
                )

                if existing and not overwrite_existing:
                    results["skipped"] += 1
                    logger.info(f"Skipping existing adapter: {genesis_type} -> {runtime_type}")
                    continue

                # Create adapter data
                adapter_create = RuntimeAdapterCreate(
                    genesis_type=genesis_type,
                    runtime_type=runtime_enum,
                    target_component=adapter_data.get("target_component", ""),
                    adapter_config=adapter_data.get("adapter_config", {}),
                    version=adapter_data.get("version", "1.0.0"),
                    compliance_rules=adapter_data.get("compliance_rules", {}),
                    description=f"Healthcare adapter for {genesis_type} on {runtime_type}",
                    active=True,
                    priority=adapter_data.get("priority", 100),
                )

                if existing:
                    # Update existing adapter
                    from langflow.services.database.models.component_mapping.runtime_adapter import RuntimeAdapterUpdate
                    update_data = RuntimeAdapterUpdate(**adapter_create.model_dump(exclude={"genesis_type", "runtime_type"}))
                    await service.update_runtime_adapter(session, existing.id, update_data)
                    results["updated"] += 1
                    logger.info(f"Updated healthcare adapter: {genesis_type} -> {runtime_type}")
                else:
                    # Create new adapter
                    await service.create_runtime_adapter(session, adapter_create)
                    results["created"] += 1
                    logger.info(f"Created healthcare adapter: {genesis_type} -> {runtime_type}")

            except Exception as e:
                logger.error(f"Error processing healthcare adapter {genesis_type} -> {runtime_type}: {e}")
                results["errors"].append(f"{genesis_type} -> {runtime_type}: {str(e)}")

    return results


async def populate_all_healthcare_mappings(overwrite_existing: bool = False) -> Dict[str, Any]:
    """Populate database with all healthcare mappings and adapters."""
    db_service = get_db_service()

    async with session_getter(db_service) as session:
        # Populate component mappings
        mapping_results = await populate_healthcare_component_mappings(
            session, overwrite_existing
        )

        # Populate runtime adapters
        adapter_results = await populate_healthcare_runtime_adapters(
            session, overwrite_existing
        )

        # Combine results
        combined_results = {
            "component_mappings": mapping_results,
            "runtime_adapters": adapter_results,
            "total_created": mapping_results["created"] + adapter_results["created"],
            "total_updated": mapping_results["updated"] + adapter_results["updated"],
            "total_skipped": mapping_results["skipped"] + adapter_results["skipped"],
            "total_errors": len(mapping_results["errors"]) + len(adapter_results["errors"]),
            "all_errors": mapping_results["errors"] + adapter_results["errors"],
        }

        logger.info(f"Healthcare mapping population completed: {combined_results}")
        return combined_results


def run_healthcare_mapping_population(overwrite_existing: bool = False):
    """Run healthcare mapping population synchronously."""
    return asyncio.run(populate_all_healthcare_mappings(overwrite_existing))


if __name__ == "__main__":
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Check for overwrite flag
    overwrite = "--overwrite" in sys.argv

    print("Starting healthcare mapping population...")
    print(f"Overwrite existing: {overwrite}")

    results = run_healthcare_mapping_population(overwrite)

    print("\nResults:")
    print(f"Component Mappings - Created: {results['component_mappings']['created']}, "
          f"Updated: {results['component_mappings']['updated']}, "
          f"Skipped: {results['component_mappings']['skipped']}")
    print(f"Runtime Adapters - Created: {results['runtime_adapters']['created']}, "
          f"Updated: {results['runtime_adapters']['updated']}, "
          f"Skipped: {results['runtime_adapters']['skipped']}")

    if results["all_errors"]:
        print(f"\nErrors ({len(results['all_errors'])}):")
        for error in results["all_errors"]:
            print(f"  - {error}")
    else:
        print("\nNo errors occurred.")

    print(f"\nTotal: {results['total_created']} created, {results['total_updated']} updated, "
          f"{results['total_skipped']} skipped, {results['total_errors']} errors")