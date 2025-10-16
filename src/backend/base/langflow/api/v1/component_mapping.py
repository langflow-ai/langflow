"""API endpoints for component mapping management."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.v1.schemas import ComponentMappingResponse
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentMappingRead,
    ComponentMappingUpdate,
    ComponentCategoryEnum,
)
from langflow.services.database.models.component_mapping.runtime_adapter import (
    RuntimeAdapter,
    RuntimeAdapterCreate,
    RuntimeAdapterRead,
    RuntimeAdapterUpdate,
    RuntimeTypeEnum,
)
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service

router = APIRouter(prefix="/component-mappings", tags=["Component Mappings"])
component_mapping_service = ComponentMappingService()


# Component Mapping Endpoints

@router.post("/", response_model=ComponentMappingRead)
async def create_component_mapping(
    mapping_data: ComponentMappingCreate,
    session: AsyncSession = Depends(session_getter),
):
    """Create a new component mapping."""
    try:
        mapping = await component_mapping_service.create_component_mapping(
            session, mapping_data
        )
        return mapping
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[ComponentMappingRead])
async def get_component_mappings(
    session: AsyncSession = Depends(session_getter),
    active_only: bool = Query(True, description="Only return active mappings"),
    category: Optional[ComponentCategoryEnum] = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of items to return"),
):
    """Get all component mappings with optional filtering."""
    mappings = await component_mapping_service.get_all_component_mappings(
        session, active_only, category, skip, limit
    )
    return mappings


@router.get("/genesis-type/{genesis_type}", response_model=ComponentMappingRead)
async def get_component_mapping_by_genesis_type(
    genesis_type: str,
    session: AsyncSession = Depends(session_getter),
    active_only: bool = Query(True, description="Only return active mappings"),
):
    """Get component mapping by genesis type."""
    mapping = await component_mapping_service.get_component_mapping_by_genesis_type(
        session, genesis_type, active_only
    )
    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"Component mapping not found for genesis type: {genesis_type}"
        )
    return mapping


@router.get("/healthcare", response_model=List[ComponentMappingRead])
async def get_healthcare_component_mappings(
    session: AsyncSession = Depends(session_getter),
):
    """Get all healthcare-related component mappings."""
    mappings = await component_mapping_service.get_healthcare_component_mappings(session)
    return mappings


@router.get("/category/{category}", response_model=List[ComponentMappingRead])
async def get_mappings_by_category(
    category: ComponentCategoryEnum,
    session: AsyncSession = Depends(session_getter),
    active_only: bool = Query(True, description="Only return active mappings"),
):
    """Get all component mappings for a specific category."""
    mappings = await component_mapping_service.get_mappings_by_category(
        session, category, active_only
    )
    return mappings


@router.get("/search", response_model=List[ComponentMappingRead])
async def search_component_mappings(
    session: AsyncSession = Depends(session_getter),
    q: str = Query(..., description="Search term for genesis type or description"),
    active_only: bool = Query(True, description="Only return active mappings"),
):
    """Search component mappings by genesis type or description."""
    mappings = await component_mapping_service.search_component_mappings(
        session, q, active_only
    )
    return mappings


@router.put("/{mapping_id}", response_model=ComponentMappingRead)
async def update_component_mapping(
    mapping_id: UUID,
    mapping_data: ComponentMappingUpdate,
    session: AsyncSession = Depends(session_getter),
):
    """Update a component mapping."""
    mapping = await component_mapping_service.update_component_mapping(
        session, mapping_id, mapping_data
    )
    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"Component mapping not found with ID: {mapping_id}"
        )
    return mapping


@router.delete("/{mapping_id}")
async def delete_component_mapping(
    mapping_id: UUID,
    session: AsyncSession = Depends(session_getter),
    soft_delete: bool = Query(True, description="Perform soft delete (deactivate)"),
):
    """Delete a component mapping."""
    success = await component_mapping_service.delete_component_mapping(
        session, mapping_id, soft_delete
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Component mapping not found with ID: {mapping_id}"
        )
    return {"message": "Component mapping deleted successfully"}


@router.get("/{mapping_id}", response_model=ComponentMappingRead)
async def get_component_mapping_by_id(
    mapping_id: UUID,
    session: AsyncSession = Depends(session_getter),
):
    """Get component mapping by ID."""
    from langflow.services.database.models.component_mapping.crud import ComponentMappingCRUD

    mapping = await ComponentMappingCRUD.get_by_id(session, mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"Component mapping not found with ID: {mapping_id}"
        )
    return mapping


# Runtime Adapter Endpoints

@router.post("/runtime-adapters/", response_model=RuntimeAdapterRead)
async def create_runtime_adapter(
    adapter_data: RuntimeAdapterCreate,
    session: AsyncSession = Depends(session_getter),
):
    """Create a new runtime adapter."""
    try:
        adapter = await component_mapping_service.create_runtime_adapter(
            session, adapter_data
        )
        return adapter
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runtime-adapters/genesis-type/{genesis_type}", response_model=List[RuntimeAdapterRead])
async def get_adapters_for_genesis_type(
    genesis_type: str,
    session: AsyncSession = Depends(session_getter),
    active_only: bool = Query(True, description="Only return active adapters"),
):
    """Get all runtime adapters for a specific genesis type."""
    adapters = await component_mapping_service.get_all_adapters_for_genesis_type(
        session, genesis_type, active_only
    )
    return adapters


@router.get("/runtime-adapters/runtime/{runtime_type}", response_model=List[RuntimeAdapterRead])
async def get_adapters_for_runtime(
    runtime_type: RuntimeTypeEnum,
    session: AsyncSession = Depends(session_getter),
    active_only: bool = Query(True, description="Only return active adapters"),
):
    """Get all runtime adapters for a specific runtime."""
    adapters = await component_mapping_service.get_all_adapters_for_runtime(
        session, runtime_type, active_only
    )
    return adapters


@router.get("/runtime-adapters/{genesis_type}/{runtime_type}", response_model=RuntimeAdapterRead)
async def get_runtime_adapter(
    genesis_type: str,
    runtime_type: RuntimeTypeEnum,
    session: AsyncSession = Depends(session_getter),
    active_only: bool = Query(True, description="Only return active adapters"),
):
    """Get runtime adapter for specific genesis type and runtime."""
    adapter = await component_mapping_service.get_runtime_adapter_for_genesis_type(
        session, genesis_type, runtime_type, active_only
    )
    if not adapter:
        raise HTTPException(
            status_code=404,
            detail=f"Runtime adapter not found for {genesis_type} on {runtime_type}"
        )
    return adapter


@router.put("/runtime-adapters/{adapter_id}", response_model=RuntimeAdapterRead)
async def update_runtime_adapter(
    adapter_id: UUID,
    adapter_data: RuntimeAdapterUpdate,
    session: AsyncSession = Depends(session_getter),
):
    """Update a runtime adapter."""
    adapter = await component_mapping_service.update_runtime_adapter(
        session, adapter_id, adapter_data
    )
    if not adapter:
        raise HTTPException(
            status_code=404,
            detail=f"Runtime adapter not found with ID: {adapter_id}"
        )
    return adapter


@router.delete("/runtime-adapters/{adapter_id}")
async def delete_runtime_adapter(
    adapter_id: UUID,
    session: AsyncSession = Depends(session_getter),
):
    """Delete a runtime adapter."""
    success = await component_mapping_service.delete_runtime_adapter(
        session, adapter_id
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Runtime adapter not found with ID: {adapter_id}"
        )
    return {"message": "Runtime adapter deleted successfully"}


# Advanced Operations

@router.get("/mapping-with-adapters/{genesis_type}")
async def get_component_mapping_with_adapters(
    genesis_type: str,
    session: AsyncSession = Depends(session_getter),
    runtime_type: Optional[RuntimeTypeEnum] = Query(None, description="Filter by runtime type"),
):
    """Get component mapping along with its runtime adapters."""
    result = await component_mapping_service.get_component_mapping_with_adapters(
        session, genesis_type, runtime_type
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Component mapping not found for genesis type: {genesis_type}"
        )
    return result


@router.get("/validate/{genesis_type}")
async def validate_mapping_consistency(
    genesis_type: str,
    session: AsyncSession = Depends(session_getter),
):
    """Validate mapping consistency across runtimes."""
    result = await component_mapping_service.validate_mapping_consistency(
        session, genesis_type
    )
    return result


@router.get("/statistics")
async def get_mapping_statistics(
    session: AsyncSession = Depends(session_getter),
):
    """Get statistics about component mappings and runtime adapters."""
    stats = await component_mapping_service.get_statistics(session)
    return stats


@router.post("/migrate-hardcoded")
async def migrate_hardcoded_mappings(
    session: AsyncSession = Depends(session_getter),
    overwrite_existing: bool = Query(False, description="Overwrite existing mappings"),
):
    """Migrate hardcoded mappings to database."""
    from langflow.custom.genesis.spec.mapper import ComponentMapper

    mapper = ComponentMapper()
    results = await mapper.migrate_hardcoded_mappings_to_database(session)
    return results