"""CRUD operations for component mappings and runtime adapters."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .model import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentMappingUpdate,
    ComponentCategoryEnum,
)
from .runtime_adapter import (
    RuntimeAdapter,
    RuntimeAdapterCreate,
    RuntimeAdapterUpdate,
    RuntimeTypeEnum,
)


class ComponentMappingCRUD:
    """CRUD operations for component mappings."""

    @staticmethod
    async def create(session: AsyncSession, mapping_data: ComponentMappingCreate) -> ComponentMapping:
        """Create a new component mapping."""
        mapping = ComponentMapping.model_validate(mapping_data.model_dump())
        session.add(mapping)
        await session.commit()
        await session.refresh(mapping)
        return mapping

    @staticmethod
    async def get_by_id(session: AsyncSession, mapping_id: UUID) -> Optional[ComponentMapping]:
        """Get component mapping by ID."""
        statement = select(ComponentMapping).where(ComponentMapping.id == mapping_id)
        result = await session.exec(statement)
        return result.first()

    @staticmethod
    async def get_by_genesis_type(
        session: AsyncSession,
        genesis_type: str,
        active_only: bool = True
    ) -> Optional[ComponentMapping]:
        """Get component mapping by genesis type."""
        statement = select(ComponentMapping).where(ComponentMapping.genesis_type == genesis_type)
        if active_only:
            statement = statement.where(ComponentMapping.active == True)

        # Order by version descending to get the latest version first
        statement = statement.order_by(ComponentMapping.version.desc())

        result = await session.exec(statement)
        return result.first()

    @staticmethod
    async def get_all(
        session: AsyncSession,
        active_only: bool = True,
        category: Optional[ComponentCategoryEnum] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComponentMapping]:
        """Get all component mappings with optional filtering."""
        statement = select(ComponentMapping)

        if active_only:
            statement = statement.where(ComponentMapping.active == True)

        if category:
            statement = statement.where(ComponentMapping.component_category == category)

        statement = statement.offset(skip).limit(limit).order_by(ComponentMapping.created_at.desc())

        result = await session.exec(statement)
        return list(result.all())

    @staticmethod
    async def get_by_category(
        session: AsyncSession,
        category: ComponentCategoryEnum,
        active_only: bool = True,
    ) -> List[ComponentMapping]:
        """Get all component mappings for a specific category."""
        statement = select(ComponentMapping).where(ComponentMapping.component_category == category)

        if active_only:
            statement = statement.where(ComponentMapping.active == True)

        statement = statement.order_by(ComponentMapping.genesis_type)

        result = await session.exec(statement)
        return list(result.all())

    @staticmethod
    async def get_healthcare_mappings(session: AsyncSession) -> List[ComponentMapping]:
        """Get all healthcare-related component mappings."""
        statement = select(ComponentMapping).where(
            ComponentMapping.component_category == ComponentCategoryEnum.HEALTHCARE,
            ComponentMapping.active == True
        ).order_by(ComponentMapping.genesis_type)

        result = await session.exec(statement)
        return list(result.all())

    @staticmethod
    async def search(
        session: AsyncSession,
        search_term: str,
        active_only: bool = True,
    ) -> List[ComponentMapping]:
        """Search component mappings by genesis type or description."""
        statement = select(ComponentMapping).where(
            ComponentMapping.genesis_type.contains(search_term) |
            ComponentMapping.description.contains(search_term)
        )

        if active_only:
            statement = statement.where(ComponentMapping.active == True)

        statement = statement.order_by(ComponentMapping.genesis_type)

        result = await session.exec(statement)
        return list(result.all())

    @staticmethod
    async def update(
        session: AsyncSession,
        mapping_id: UUID,
        mapping_data: ComponentMappingUpdate,
    ) -> Optional[ComponentMapping]:
        """Update a component mapping."""
        statement = select(ComponentMapping).where(ComponentMapping.id == mapping_id)
        result = await session.exec(statement)
        mapping = result.first()

        if not mapping:
            return None

        update_data = mapping_data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now(timezone.utc)

        for field, value in update_data.items():
            setattr(mapping, field, value)

        await session.commit()
        await session.refresh(mapping)
        return mapping

    @staticmethod
    async def delete(session: AsyncSession, mapping_id: UUID) -> bool:
        """Delete a component mapping (hard delete)."""
        statement = select(ComponentMapping).where(ComponentMapping.id == mapping_id)
        result = await session.exec(statement)
        mapping = result.first()

        if not mapping:
            return False

        await session.delete(mapping)
        await session.commit()
        return True

    @staticmethod
    async def deactivate(session: AsyncSession, mapping_id: UUID) -> Optional[ComponentMapping]:
        """Deactivate a component mapping (soft delete)."""
        return await ComponentMappingCRUD.update(
            session,
            mapping_id,
            ComponentMappingUpdate(active=False)
        )

    @staticmethod
    async def count_by_category(session: AsyncSession) -> dict:
        """Get count of mappings by category."""
        from sqlalchemy import func

        statement = select(
            ComponentMapping.component_category,
            func.count(ComponentMapping.id).label("count")
        ).where(
            ComponentMapping.active == True
        ).group_by(ComponentMapping.component_category)

        result = await session.exec(statement)
        return {row[0]: row[1] for row in result.all()}


class RuntimeAdapterCRUD:
    """CRUD operations for runtime adapters."""

    @staticmethod
    async def create(session: AsyncSession, adapter_data: RuntimeAdapterCreate) -> RuntimeAdapter:
        """Create a new runtime adapter."""
        adapter = RuntimeAdapter.model_validate(adapter_data.model_dump())
        session.add(adapter)
        await session.commit()
        await session.refresh(adapter)
        return adapter

    @staticmethod
    async def get_by_id(session: AsyncSession, adapter_id: UUID) -> Optional[RuntimeAdapter]:
        """Get runtime adapter by ID."""
        statement = select(RuntimeAdapter).where(RuntimeAdapter.id == adapter_id)
        result = await session.exec(statement)
        return result.first()

    @staticmethod
    async def get_for_genesis_type(
        session: AsyncSession,
        genesis_type: str,
        runtime_type: RuntimeTypeEnum,
        active_only: bool = True,
    ) -> Optional[RuntimeAdapter]:
        """Get runtime adapter for specific genesis type and runtime."""
        statement = select(RuntimeAdapter).where(
            RuntimeAdapter.genesis_type == genesis_type,
            RuntimeAdapter.runtime_type == runtime_type
        )

        if active_only:
            statement = statement.where(RuntimeAdapter.active == True)

        # Order by priority (lower = higher priority) and version
        statement = statement.order_by(
            RuntimeAdapter.priority,
            RuntimeAdapter.version.desc()
        )

        result = await session.exec(statement)
        return result.first()

    @staticmethod
    async def get_all_for_runtime(
        session: AsyncSession,
        runtime_type: RuntimeTypeEnum,
        active_only: bool = True,
    ) -> List[RuntimeAdapter]:
        """Get all adapters for a specific runtime."""
        statement = select(RuntimeAdapter).where(RuntimeAdapter.runtime_type == runtime_type)

        if active_only:
            statement = statement.where(RuntimeAdapter.active == True)

        statement = statement.order_by(RuntimeAdapter.genesis_type, RuntimeAdapter.priority)

        result = await session.exec(statement)
        return list(result.all())

    @staticmethod
    async def get_all_for_genesis_type(
        session: AsyncSession,
        genesis_type: str,
        active_only: bool = True,
    ) -> List[RuntimeAdapter]:
        """Get all adapters for a specific genesis type."""
        statement = select(RuntimeAdapter).where(RuntimeAdapter.genesis_type == genesis_type)

        if active_only:
            statement = statement.where(RuntimeAdapter.active == True)

        statement = statement.order_by(RuntimeAdapter.runtime_type, RuntimeAdapter.priority)

        result = await session.exec(statement)
        return list(result.all())

    @staticmethod
    async def update(
        session: AsyncSession,
        adapter_id: UUID,
        adapter_data: RuntimeAdapterUpdate,
    ) -> Optional[RuntimeAdapter]:
        """Update a runtime adapter."""
        statement = select(RuntimeAdapter).where(RuntimeAdapter.id == adapter_id)
        result = await session.exec(statement)
        adapter = result.first()

        if not adapter:
            return None

        update_data = adapter_data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now(timezone.utc)

        for field, value in update_data.items():
            setattr(adapter, field, value)

        await session.commit()
        await session.refresh(adapter)
        return adapter

    @staticmethod
    async def delete(session: AsyncSession, adapter_id: UUID) -> bool:
        """Delete a runtime adapter."""
        statement = select(RuntimeAdapter).where(RuntimeAdapter.id == adapter_id)
        result = await session.exec(statement)
        adapter = result.first()

        if not adapter:
            return False

        await session.delete(adapter)
        await session.commit()
        return True

    @staticmethod
    async def get_supported_runtimes(session: AsyncSession) -> List[RuntimeTypeEnum]:
        """Get list of all supported runtime types."""
        from sqlalchemy import func, distinct

        statement = select(distinct(RuntimeAdapter.runtime_type)).where(
            RuntimeAdapter.active == True
        )

        result = await session.exec(statement)
        return list(result.all())

    @staticmethod
    async def count_by_runtime(session: AsyncSession) -> dict:
        """Get count of adapters by runtime type."""
        from sqlalchemy import func

        statement = select(
            RuntimeAdapter.runtime_type,
            func.count(RuntimeAdapter.id).label("count")
        ).where(
            RuntimeAdapter.active == True
        ).group_by(RuntimeAdapter.runtime_type)

        result = await session.exec(statement)
        return {row[0]: row[1] for row in result.all()}