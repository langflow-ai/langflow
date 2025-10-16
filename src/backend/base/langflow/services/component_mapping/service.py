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
    ) -> ComponentMapping:
        """Create a new component mapping."""
        return await ComponentMappingCRUD.create(session, mapping_data)

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
    ) -> Optional[ComponentMapping]:
        """Update a component mapping."""
        return await ComponentMappingCRUD.update(session, mapping_id, mapping_data)

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
    ) -> RuntimeAdapter:
        """Create a new runtime adapter."""
        return await RuntimeAdapterCRUD.create(session, adapter_data)

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
    ) -> Optional[RuntimeAdapter]:
        """Update a runtime adapter."""
        return await RuntimeAdapterCRUD.update(session, adapter_id, adapter_data)

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
        """Migrate hardcoded mappings to database."""
        results = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }

        for genesis_type, mapping_info in hardcoded_mappings.items():
            try:
                existing = await self.get_component_mapping_by_genesis_type(
                    session, genesis_type, active_only=False
                )

                if existing and not overwrite_existing:
                    results["skipped"] += 1
                    continue

                # Determine category based on genesis type
                category = self._determine_category_from_genesis_type(genesis_type)

                mapping_data = ComponentMappingCreate(
                    genesis_type=genesis_type,
                    base_config=mapping_info.get("config", {}),
                    io_mapping=self._extract_io_mapping(mapping_info),
                    component_category=category,
                    description=f"Migrated from hardcoded mapping for {genesis_type}",
                    version="1.0.0",
                    active=True,
                )

                if existing:
                    await self.update_component_mapping(
                        session, existing.id, ComponentMappingUpdate(**mapping_data.model_dump())
                    )
                    results["updated"] += 1
                else:
                    await self.create_component_mapping(session, mapping_data)
                    results["created"] += 1

                # Create Langflow runtime adapter
                adapter_data = RuntimeAdapterCreate(
                    genesis_type=genesis_type,
                    runtime_type=RuntimeTypeEnum.LANGFLOW,
                    target_component=mapping_info.get("component", "CustomComponent"),
                    adapter_config=mapping_info.get("config", {}),
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
                            session, existing_adapter.id, RuntimeAdapterUpdate(**adapter_data.model_dump())
                        )
                    else:
                        await self.create_runtime_adapter(session, adapter_data)

            except Exception as e:
                logger.error(f"Error migrating mapping for {genesis_type}: {e}")
                results["errors"].append(f"{genesis_type}: {str(e)}")

        return results

    def _determine_category_from_genesis_type(self, genesis_type: str) -> ComponentCategoryEnum:
        """Determine component category from genesis type."""
        type_lower = genesis_type.lower()

        if any(term in type_lower for term in ["healthcare", "ehr", "claims", "eligibility", "pharmacy"]):
            return ComponentCategoryEnum.HEALTHCARE
        elif any(term in type_lower for term in ["agent", "crew"]):
            return ComponentCategoryEnum.AGENT
        elif any(term in type_lower for term in ["tool", "calculator", "search", "api"]):
            return ComponentCategoryEnum.TOOL
        elif any(term in type_lower for term in ["input", "output", "chat"]):
            return ComponentCategoryEnum.IO
        elif any(term in type_lower for term in ["prompt", "template"]):
            return ComponentCategoryEnum.PROMPT
        elif any(term in type_lower for term in ["memory", "conversation"]):
            return ComponentCategoryEnum.MEMORY
        elif any(term in type_lower for term in ["llm", "model", "openai", "anthropic"]):
            return ComponentCategoryEnum.LLM
        elif any(term in type_lower for term in ["embedding", "embed"]):
            return ComponentCategoryEnum.EMBEDDING
        elif any(term in type_lower for term in ["vector", "store", "qdrant", "chroma"]):
            return ComponentCategoryEnum.VECTOR_STORE
        elif any(term in type_lower for term in ["data", "csv", "json", "parse"]):
            return ComponentCategoryEnum.DATA
        else:
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