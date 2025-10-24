"""Component mapping service for managing runtime-agnostic component mappings."""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.base import Service
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentMappingUpdate,
    ComponentCategoryEnum,
)
from langflow.services.database.models.component_mapping.runtime_adapter import (
    RuntimeAdapter,
    RuntimeAdapterCreate,
    RuntimeAdapterUpdate,
    RuntimeTypeEnum,
)
from langflow.services.database.models.component_mapping.crud import (
    ComponentMappingCRUD,
    RuntimeAdapterCRUD,
)

logger = logging.getLogger(__name__)


class ComponentMappingService(Service):
    """Service for managing component mappings and runtime adapters."""

    name = "component_mapping_service"

    def __init__(self):
        """Initialize the component mapping service."""
        super().__init__()

    # Component Mapping Operations

    async def create_component_mapping(
        self,
        session: AsyncSession,
        mapping_data: ComponentMappingCreate,
        commit: bool = True,
    ) -> ComponentMapping:
        """Create a new component mapping."""
        return await ComponentMappingCRUD.create(session, mapping_data, commit=commit)

    async def get_component_mapping_by_genesis_type(
        self,
        session: AsyncSession,
        genesis_type: str,
        active_only: bool = True,
    ) -> Optional[ComponentMapping]:
        """Get component mapping by genesis type."""
        return await ComponentMappingCRUD.get_by_genesis_type(
            session, genesis_type, active_only
        )

    async def get_all_component_mappings(
        self,
        session: AsyncSession,
        active_only: bool = True,
        category: Optional[ComponentCategoryEnum] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComponentMapping]:
        """Get all component mappings with optional filtering."""
        return await ComponentMappingCRUD.get_all(
            session, active_only, category, skip, limit
        )

    async def get_healthcare_component_mappings(
        self,
        session: AsyncSession,
    ) -> List[ComponentMapping]:
        """Get all healthcare-related component mappings."""
        return await ComponentMappingCRUD.get_healthcare_mappings(session)

    async def update_component_mapping(
        self,
        session: AsyncSession,
        mapping_id: UUID,
        mapping_data: ComponentMappingUpdate,
        commit: bool = True,
    ) -> Optional[ComponentMapping]:
        """Update a component mapping."""
        return await ComponentMappingCRUD.update(session, mapping_id, mapping_data, commit=commit)

    async def delete_component_mapping(
        self,
        session: AsyncSession,
        mapping_id: UUID,
        soft_delete: bool = True,
    ) -> bool:
        """Delete a component mapping (soft or hard delete)."""
        if soft_delete:
            result = await ComponentMappingCRUD.deactivate(session, mapping_id)
            return result is not None
        else:
            return await ComponentMappingCRUD.delete(session, mapping_id)

    async def search_component_mappings(
        self,
        session: AsyncSession,
        search_term: str,
        active_only: bool = True,
    ) -> List[ComponentMapping]:
        """Search component mappings by genesis type or description."""
        return await ComponentMappingCRUD.search(session, search_term, active_only)

    async def get_mappings_by_category(
        self,
        session: AsyncSession,
        category: ComponentCategoryEnum,
        active_only: bool = True,
    ) -> List[ComponentMapping]:
        """Get all component mappings for a specific category."""
        return await ComponentMappingCRUD.get_by_category(
            session, category, active_only
        )

    # Runtime Adapter Operations

    async def create_runtime_adapter(
        self,
        session: AsyncSession,
        adapter_data: RuntimeAdapterCreate,
        commit: bool = True,
    ) -> RuntimeAdapter:
        """Create a new runtime adapter."""
        return await RuntimeAdapterCRUD.create(session, adapter_data, commit=commit)

    async def get_runtime_adapter_for_genesis_type(
        self,
        session: AsyncSession,
        genesis_type: str,
        runtime_type: RuntimeTypeEnum,
        active_only: bool = True,
    ) -> Optional[RuntimeAdapter]:
        """Get runtime adapter for specific genesis type and runtime."""
        return await RuntimeAdapterCRUD.get_for_genesis_type(
            session, genesis_type, runtime_type, active_only
        )

    async def get_all_adapters_for_runtime(
        self,
        session: AsyncSession,
        runtime_type: RuntimeTypeEnum,
        active_only: bool = True,
    ) -> List[RuntimeAdapter]:
        """Get all adapters for a specific runtime."""
        return await RuntimeAdapterCRUD.get_all_for_runtime(
            session, runtime_type, active_only
        )

    async def get_all_adapters_for_genesis_type(
        self,
        session: AsyncSession,
        genesis_type: str,
        active_only: bool = True,
    ) -> List[RuntimeAdapter]:
        """Get all adapters for a specific genesis type."""
        return await RuntimeAdapterCRUD.get_all_for_genesis_type(
            session, genesis_type, active_only
        )

    async def update_runtime_adapter(
        self,
        session: AsyncSession,
        adapter_id: UUID,
        adapter_data: RuntimeAdapterUpdate,
        commit: bool = True,
    ) -> Optional[RuntimeAdapter]:
        """Update a runtime adapter."""
        return await RuntimeAdapterCRUD.update(session, adapter_id, adapter_data, commit=commit)

    async def delete_runtime_adapter(
        self,
        session: AsyncSession,
        adapter_id: UUID,
    ) -> bool:
        """Delete a runtime adapter."""
        return await RuntimeAdapterCRUD.delete(session, adapter_id)

    # Advanced Operations

    async def get_component_mapping_with_adapters(
        self,
        session: AsyncSession,
        genesis_type: str,
        runtime_type: Optional[RuntimeTypeEnum] = None,
    ) -> Dict:
        """Get component mapping along with its runtime adapters."""
        mapping = await self.get_component_mapping_by_genesis_type(
            session, genesis_type
        )

        if not mapping:
            return {}

        adapters = await self.get_all_adapters_for_genesis_type(
            session, genesis_type
        )

        if runtime_type:
            adapters = [a for a in adapters if a.runtime_type == runtime_type]

        return {
            "mapping": mapping,
            "adapters": adapters,
            "supported_runtimes": list(set(a.runtime_type for a in adapters)),
        }

    async def validate_mapping_consistency(
        self,
        session: AsyncSession,
        genesis_type: str,
    ) -> Dict:
        """Validate mapping consistency across runtimes."""
        mapping = await self.get_component_mapping_by_genesis_type(
            session, genesis_type
        )

        if not mapping:
            return {"valid": False, "errors": ["Mapping not found"]}

        adapters = await self.get_all_adapters_for_genesis_type(
            session, genesis_type
        )

        errors = []
        warnings = []

        # Check if mapping has required fields
        if not mapping.base_config:
            warnings.append("No base configuration defined")

        if not mapping.io_mapping:
            warnings.append("No I/O mapping defined")

        # Check adapters consistency
        runtime_targets = {}
        for adapter in adapters:
            if adapter.runtime_type in runtime_targets:
                if runtime_targets[adapter.runtime_type] != adapter.target_component:
                    errors.append(
                        f"Inconsistent target components for {adapter.runtime_type}: "
                        f"{runtime_targets[adapter.runtime_type]} vs {adapter.target_component}"
                    )
            else:
                runtime_targets[adapter.runtime_type] = adapter.target_component

        # Check healthcare compliance if applicable
        if mapping.component_category == ComponentCategoryEnum.HEALTHCARE:
            if not mapping.healthcare_metadata:
                warnings.append("Healthcare component missing HIPAA compliance metadata")

            for adapter in adapters:
                if not adapter.compliance_rules:
                    warnings.append(
                        f"Healthcare adapter for {adapter.runtime_type} missing compliance rules"
                    )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "supported_runtimes": list(runtime_targets.keys()),
            "runtime_targets": runtime_targets,
        }

    async def get_statistics(self, session: AsyncSession) -> Dict:
        """Get statistics about component mappings and runtime adapters."""
        mapping_counts = await ComponentMappingCRUD.count_by_category(session)
        adapter_counts = await RuntimeAdapterCRUD.count_by_runtime(session)
        supported_runtimes = await RuntimeAdapterCRUD.get_supported_runtimes(session)

        return {
            "component_mappings": {
                "total": sum(mapping_counts.values()),
                "by_category": mapping_counts,
            },
            "runtime_adapters": {
                "total": sum(adapter_counts.values()),
                "by_runtime": adapter_counts,
            },
            "supported_runtimes": supported_runtimes,
        }

    async def migrate_hardcoded_mappings(
        self,
        session: AsyncSession,
        hardcoded_mappings: Dict,
        overwrite_existing: bool = False,
    ) -> Dict:
        """Migrate hardcoded mappings to database with transaction isolation."""
        results = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }

        # Validate input parameters
        if not hardcoded_mappings:
            logger.warning("No hardcoded mappings provided for migration")
            return results

        logger.info(f"Starting migration of {len(hardcoded_mappings)} hardcoded mappings")

        for genesis_type, mapping_info in hardcoded_mappings.items():
            # Use savepoint for transaction isolation
            savepoint = await session.begin_nested()
            try:
                # Validate mapping_info structure
                if not isinstance(mapping_info, dict):
                    logger.error(f"Invalid mapping_info type for {genesis_type}: {type(mapping_info)}")
                    results["errors"].append(f"{genesis_type}: Invalid mapping_info type")
                    await savepoint.rollback()
                    continue
                existing = await self.get_component_mapping_by_genesis_type(
                    session, genesis_type, active_only=False
                )

                if existing and not overwrite_existing:
                    results["skipped"] += 1
                    await savepoint.commit()
                    continue

                # Validate genesis_type format before proceeding
                if not genesis_type.startswith("genesis:"):
                    corrected_genesis_type = f"genesis:{genesis_type}" if not genesis_type.startswith("genesis:") else genesis_type
                    logger.warning(f"Invalid genesis_type format '{genesis_type}', correcting to '{corrected_genesis_type}'")
                    genesis_type = corrected_genesis_type

                # Determine category based on genesis type
                category = self._determine_category_from_genesis_type(genesis_type)

                # Safe enum value extraction - handle both enum instances and strings
                if isinstance(category, ComponentCategoryEnum):
                    category_value = category.value
                elif isinstance(category, str):
                    # If it's already a string, validate it's a valid enum value
                    try:
                        ComponentCategoryEnum(category)
                        category_value = category
                    except ValueError:
                        logger.warning(f"Invalid category string '{category}' for {genesis_type}, using default")
                        category_value = ComponentCategoryEnum.TOOL.value
                else:
                    logger.warning(f"Unexpected category type {type(category)} for {genesis_type}, using default")
                    category_value = ComponentCategoryEnum.TOOL.value

                logger.debug(f"Genesis type: {genesis_type}, Category: {category}, Category value: {category_value}")

                # Create mapping data with safe enum handling and validation
                # Fix for ISSUE: Include component name in base_config for proper mapping
                base_config = mapping_info.get("config", {}).copy() if mapping_info.get("config") else {}

                # CRITICAL: Add the component name to base_config so langflow_component property works
                if "component" in mapping_info:
                    base_config["component"] = mapping_info["component"]

                mapping_dict = {
                    "genesis_type": genesis_type,
                    "base_config": base_config,
                    "io_mapping": self._extract_io_mapping(mapping_info),
                    "component_category": category_value,  # Use safely extracted string value
                    "description": f"Migrated from hardcoded mapping for {genesis_type}",
                    "version": "1.0.0",
                    "active": True,
                }

                logger.debug(f"Creating mapping with category value: {mapping_dict['component_category']}")

                # Validate the mapping data before creating
                try:
                    mapping_data = ComponentMappingCreate(**mapping_dict)
                except Exception as validation_error:
                    logger.error(f"Validation error for {genesis_type}: {validation_error}")
                    results["errors"].append(f"{genesis_type}: Validation error - {str(validation_error)}")
                    await savepoint.rollback()
                    continue

                if existing:
                    # Create update data with proper enum value handling
                    update_dict = mapping_dict.copy()
                    del update_dict["genesis_type"]  # Remove immutable field for update
                    update_data = ComponentMappingUpdate(**update_dict)
                    await self.update_component_mapping(session, existing.id, update_data, commit=False)
                    results["updated"] += 1
                else:
                    await self.create_component_mapping(session, mapping_data, commit=False)
                    results["created"] += 1

                # Create Langflow runtime adapter
                adapter_data = RuntimeAdapterCreate(
                    genesis_type=genesis_type,
                    runtime_type=RuntimeTypeEnum.LANGFLOW,
                    target_component=mapping_info.get("component", "CustomComponent"),
                    adapter_config=mapping_info.get("config", {}) if mapping_info.get("config") else {},
                    version="1.0.0",
                    description=f"Langflow adapter for {genesis_type}",
                    active=True,
                    priority=100,
                )

                existing_adapter = await self.get_runtime_adapter_for_genesis_type(
                    session, genesis_type, RuntimeTypeEnum.LANGFLOW, active_only=False
                )

                if not existing_adapter or overwrite_existing:
                    if existing_adapter:
                        await self.update_runtime_adapter(
                            session, existing_adapter.id, RuntimeAdapterUpdate(**adapter_data.model_dump()), commit=False
                        )
                    else:
                        await self.create_runtime_adapter(session, adapter_data, commit=False)

                # Commit the savepoint on success
                await savepoint.commit()

            except Exception as e:
                # Rollback the savepoint on any error to prevent transaction abort
                await savepoint.rollback()

                logger.error(f"Error migrating mapping for {genesis_type}: {e}")
                results["errors"].append(f"{genesis_type}: {str(e)}")

                # Log the specific error details for debugging
                import traceback
                logger.debug(f"Full traceback for {genesis_type}: {traceback.format_exc()}")

                # Continue processing other mappings - savepoint rollback prevents cascade failures

        logger.info(f"Migration completed: {results['created']} created, {results['updated']} updated, {results['skipped']} skipped, {len(results['errors'])} errors")
        return results

    def _determine_category_from_genesis_type(self, genesis_type: str) -> ComponentCategoryEnum:
        """
        Determine component category from genesis type.

        This is a FALLBACK method only used for legacy/hardcoded mappings.
        New components should have their category determined through introspection.
        """
        # NOTE: This method is deprecated and only kept for backward compatibility
        # All new components use data-driven introspection in discovery.py

        logger.warning(f"Using deprecated pattern matching for category determination of {genesis_type}")

        # Default to TOOL for any unknown category
        # The unified discovery service will properly categorize through introspection
        return ComponentCategoryEnum.TOOL

    def _extract_io_mapping(self, mapping_info: Dict) -> Dict:
        """Extract I/O mapping information from hardcoded mapping."""
        return {
            "component": mapping_info.get("component"),
            "dataType": mapping_info.get("dataType"),
            "input_field": None,  # Will be filled by ComponentMapper introspection
            "output_field": None,  # Will be filled by ComponentMapper introspection
            "input_types": [],    # Will be filled by ComponentMapper introspection
            "output_types": [],   # Will be filled by ComponentMapper introspection
        }

    async def get_component_mapping(self, genesis_type: str, session: AsyncSession) -> Optional[ComponentMapping]:
        """
        Get component mapping by genesis type.

        This method was identified as missing in AUTPE-6237 critical gaps.

        Args:
            genesis_type: Genesis component type
            session: Database session

        Returns:
            Component mapping if found
        """
        return await self.get_component_mapping_by_genesis_type(session, genesis_type, active_only=True)

    async def get_all_mappings(self, session: AsyncSession) -> List[ComponentMapping]:
        """
        Get all available component mappings.

        This method was identified as missing in AUTPE-6237 critical gaps.

        Args:
            session: Database session

        Returns:
            List of all component mappings
        """
        return await self.get_all_component_mappings(session, active_only=True, limit=1000)

    async def get_tool_components(self, session: AsyncSession) -> List[ComponentMapping]:
        """
        Get components that support tool mode.

        This method was identified as missing in AUTPE-6237 critical gaps.

        Args:
            session: Database session

        Returns:
            List of tool-capable component mappings
        """
        return await self.get_components_with_tool_capabilities(session, provides_tools=True)

    async def get_components_with_tool_capabilities(
        self,
        session: AsyncSession,
        accepts_tools: Optional[bool] = None,
        provides_tools: Optional[bool] = None,
    ) -> List[ComponentMapping]:
        """
        Get components filtered by tool capabilities.

        Args:
            session: Database session
            accepts_tools: Filter by accepts_tools capability (None to ignore)
            provides_tools: Filter by provides_tools capability (None to ignore)

        Returns:
            List of component mappings matching the criteria
        """
        mappings = await self.get_all_component_mappings(session, active_only=True, limit=1000)

        filtered_mappings = []
        for mapping in mappings:
            if mapping.tool_capabilities:
                match = True

                if accepts_tools is not None:
                    if mapping.tool_capabilities.get("accepts_tools", False) != accepts_tools:
                        match = False

                if provides_tools is not None:
                    if mapping.tool_capabilities.get("provides_tools", False) != provides_tools:
                        match = False

                if match:
                    filtered_mappings.append(mapping)

        return filtered_mappings

    async def populate_tool_capabilities_from_introspection(
        self,
        session: AsyncSession,
        genesis_type: str,
        force_update: bool = False,
    ) -> bool:
        """
        Populate tool capabilities for a component based on introspection.

        Args:
            session: Database session
            genesis_type: Genesis component type
            force_update: Whether to force update existing capabilities

        Returns:
            True if capabilities were updated
        """
        mapping = await self.get_component_mapping_by_genesis_type(
            session, genesis_type, active_only=False
        )

        if not mapping:
            logger.warning(f"No mapping found for {genesis_type}")
            return False

        # Skip if capabilities already exist and not forcing update
        if mapping.tool_capabilities and not force_update:
            logger.debug(f"Tool capabilities already exist for {genesis_type}, skipping")
            return False

        # Determine capabilities based on component type and category
        capabilities = self._determine_tool_capabilities(genesis_type, mapping)

        # Update the mapping
        update_data = ComponentMappingUpdate(
            tool_capabilities=capabilities
        )

        updated_mapping = await self.update_component_mapping(
            session, mapping.id, update_data
        )

        if updated_mapping:
            logger.info(f"Populated tool capabilities for {genesis_type}: {capabilities}")
            return True

        return False

    def _determine_tool_capabilities(self, genesis_type: str, mapping: ComponentMapping) -> Dict:
        """
        Determine tool capabilities for legacy/hardcoded components.

        This is a FALLBACK method. All new components should have their capabilities
        determined through actual code introspection in the unified discovery service.

        Args:
            genesis_type: Genesis component type
            mapping: Component mapping

        Returns:
            Tool capabilities dictionary
        """
        logger.warning(f"Using deprecated pattern matching for tool capabilities of {genesis_type}")

        # Return minimal capabilities for legacy support
        # The unified discovery service will properly determine capabilities through introspection
        capabilities = {
            "accepts_tools": False,
            "provides_tools": False,
            "discovery_method": "legacy_fallback",
            "populated_at": None,
        }

        from datetime import datetime, timezone
        capabilities["populated_at"] = datetime.now(timezone.utc).isoformat()

        return capabilities