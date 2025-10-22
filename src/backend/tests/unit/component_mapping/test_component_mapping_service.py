"""Tests for component mapping service."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.database.models.component_mapping.model import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentMappingUpdate,
    ComponentCategoryEnum,
)
from langflow.services.database.models.component_mapping.runtime_adapter import (
    RuntimeAdapter,
    RuntimeAdapterCreate,
    RuntimeTypeEnum,
)


class TestComponentMappingService:
    """Test ComponentMappingService functionality."""

    @pytest.fixture
    def service(self):
        """Create ComponentMappingService instance."""
        return ComponentMappingService()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def sample_mapping(self):
        """Create sample component mapping."""
        return ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:test_component",
            base_config={"key": "value"},
            io_mapping={"input": "test", "output": "result"},
            component_category=ComponentCategoryEnum.TOOL,
            description="Test component mapping",
            version="1.0.0",
            active=True,
        )

    @pytest.fixture
    def sample_adapter(self):
        """Create sample runtime adapter."""
        return RuntimeAdapter(
            id=uuid4(),
            genesis_type="genesis:test_component",
            runtime_type=RuntimeTypeEnum.LANGFLOW.value,
            target_component="TestComponent",
            adapter_config={"key": "value"},
            version="1.0.0",
            active=True,
            priority=100,
        )

    @pytest.mark.asyncio
    async def test_create_component_mapping(self, service, mock_session, sample_mapping):
        """Test creating a component mapping."""
        mapping_data = ComponentMappingCreate(
            genesis_type="genesis:test_component",
            base_config={"key": "value"},
            component_category=ComponentCategoryEnum.TOOL,
        )

        with patch('langflow.services.database.models.component_mapping.crud.ComponentMappingCRUD.create') as mock_create:
            mock_create.return_value = sample_mapping

            result = await service.create_component_mapping(mock_session, mapping_data)

            assert result.genesis_type == "genesis:test_component"
            mock_create.assert_called_once_with(mock_session, mapping_data)

    @pytest.mark.asyncio
    async def test_get_component_mapping_by_genesis_type(self, service, mock_session, sample_mapping):
        """Test getting component mapping by genesis type."""
        with patch('langflow.services.database.models.component_mapping.crud.ComponentMappingCRUD.get_by_genesis_type') as mock_get:
            mock_get.return_value = sample_mapping

            result = await service.get_component_mapping_by_genesis_type(
                mock_session, "genesis:test_component"
            )

            assert result.genesis_type == "genesis:test_component"
            mock_get.assert_called_once_with(mock_session, "genesis:test_component", True)

    @pytest.mark.asyncio
    async def test_get_healthcare_component_mappings(self, service, mock_session):
        """Test getting healthcare component mappings."""
        healthcare_mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:ehr_connector",
            component_category=ComponentCategoryEnum.HEALTHCARE,
            healthcare_metadata={"hipaa_compliant": True},
            version="1.0.0",
            active=True,
        )

        with patch('langflow.services.database.models.component_mapping.crud.ComponentMappingCRUD.get_healthcare_mappings') as mock_get:
            mock_get.return_value = [healthcare_mapping]

            result = await service.get_healthcare_component_mappings(mock_session)

            assert len(result) == 1
            assert result[0].component_category == ComponentCategoryEnum.HEALTHCARE
            assert result[0].healthcare_metadata["hipaa_compliant"] is True

    @pytest.mark.asyncio
    async def test_update_component_mapping(self, service, mock_session, sample_mapping):
        """Test updating a component mapping."""
        mapping_id = uuid4()
        update_data = ComponentMappingUpdate(
            base_config={"updated": True},
            version="1.1.0",
        )

        updated_mapping = ComponentMapping(**sample_mapping.model_dump())
        updated_mapping.base_config = {"updated": True}
        updated_mapping.version = "1.1.0"

        with patch('langflow.services.database.models.component_mapping.crud.ComponentMappingCRUD.update') as mock_update:
            mock_update.return_value = updated_mapping

            result = await service.update_component_mapping(
                mock_session, mapping_id, update_data
            )

            assert result.base_config["updated"] is True
            assert result.version == "1.1.0"
            mock_update.assert_called_once_with(mock_session, mapping_id, update_data)

    @pytest.mark.asyncio
    async def test_delete_component_mapping_soft(self, service, mock_session):
        """Test soft deleting a component mapping."""
        mapping_id = uuid4()

        with patch('langflow.services.database.models.component_mapping.crud.ComponentMappingCRUD.deactivate') as mock_deactivate:
            mock_deactivate.return_value = AsyncMock()

            result = await service.delete_component_mapping(
                mock_session, mapping_id, soft_delete=True
            )

            assert result is True
            mock_deactivate.assert_called_once_with(mock_session, mapping_id)

    @pytest.mark.asyncio
    async def test_delete_component_mapping_hard(self, service, mock_session):
        """Test hard deleting a component mapping."""
        mapping_id = uuid4()

        with patch('langflow.services.database.models.component_mapping.crud.ComponentMappingCRUD.delete') as mock_delete:
            mock_delete.return_value = True

            result = await service.delete_component_mapping(
                mock_session, mapping_id, soft_delete=False
            )

            assert result is True
            mock_delete.assert_called_once_with(mock_session, mapping_id)

    @pytest.mark.asyncio
    async def test_search_component_mappings(self, service, mock_session, sample_mapping):
        """Test searching component mappings."""
        with patch('langflow.services.database.models.component_mapping.crud.ComponentMappingCRUD.search') as mock_search:
            mock_search.return_value = [sample_mapping]

            result = await service.search_component_mappings(
                mock_session, "test", active_only=True
            )

            assert len(result) == 1
            assert result[0].genesis_type == "genesis:test_component"
            mock_search.assert_called_once_with(mock_session, "test", True)

    @pytest.mark.asyncio
    async def test_create_runtime_adapter(self, service, mock_session, sample_adapter):
        """Test creating a runtime adapter."""
        adapter_data = RuntimeAdapterCreate(
            genesis_type="genesis:test_component",
            runtime_type=RuntimeTypeEnum.LANGFLOW.value,
            target_component="TestComponent",
        )

        with patch('langflow.services.database.models.component_mapping.crud.RuntimeAdapterCRUD.create') as mock_create:
            mock_create.return_value = sample_adapter

            result = await service.create_runtime_adapter(mock_session, adapter_data)

            assert result.genesis_type == "genesis:test_component"
            assert result.runtime_type == RuntimeTypeEnum.LANGFLOW.value
            mock_create.assert_called_once_with(mock_session, adapter_data)

    @pytest.mark.asyncio
    async def test_get_runtime_adapter_for_genesis_type(self, service, mock_session, sample_adapter):
        """Test getting runtime adapter for genesis type."""
        with patch('langflow.services.database.models.component_mapping.crud.RuntimeAdapterCRUD.get_for_genesis_type') as mock_get:
            mock_get.return_value = sample_adapter

            result = await service.get_runtime_adapter_for_genesis_type(
                mock_session, "genesis:test_component", RuntimeTypeEnum.LANGFLOW.value
            )

            assert result.genesis_type == "genesis:test_component"
            assert result.runtime_type == RuntimeTypeEnum.LANGFLOW.value
            mock_get.assert_called_once_with(
                mock_session, "genesis:test_component", RuntimeTypeEnum.LANGFLOW.value, True
            )

    @pytest.mark.asyncio
    async def test_validate_mapping_consistency(self, service, mock_session, sample_mapping):
        """Test mapping consistency validation."""
        sample_adapter = RuntimeAdapter(
            id=uuid4(),
            genesis_type="genesis:test_component",
            runtime_type=RuntimeTypeEnum.LANGFLOW.value,
            target_component="TestComponent",
            version="1.0.0",
            active=True,
            priority=100,
        )

        with patch.multiple(
            'langflow.services.component_mapping.service.ComponentMappingService',
            get_component_mapping_by_genesis_type=AsyncMock(return_value=sample_mapping),
            get_all_adapters_for_genesis_type=AsyncMock(return_value=[sample_adapter]),
        ):
            result = await service.validate_mapping_consistency(
                mock_session, "genesis:test_component"
            )

            assert result["valid"] is True
            assert len(result["errors"]) == 0
            assert "langflow" in result["supported_runtimes"]

    @pytest.mark.asyncio
    async def test_validate_mapping_consistency_healthcare(self, service, mock_session):
        """Test healthcare mapping consistency validation."""
        healthcare_mapping = ComponentMapping(
            id=uuid4(),
            genesis_type="genesis:ehr_connector",
            component_category=ComponentCategoryEnum.HEALTHCARE,
            healthcare_metadata=None,  # Missing metadata
            version="1.0.0",
            active=True,
        )

        healthcare_adapter = RuntimeAdapter(
            id=uuid4(),
            genesis_type="genesis:ehr_connector",
            runtime_type=RuntimeTypeEnum.LANGFLOW.value,
            target_component="EHRConnector",
            compliance_rules=None,  # Missing compliance rules
            version="1.0.0",
            active=True,
            priority=100,
        )

        with patch.multiple(
            'langflow.services.component_mapping.service.ComponentMappingService',
            get_component_mapping_by_genesis_type=AsyncMock(return_value=healthcare_mapping),
            get_all_adapters_for_genesis_type=AsyncMock(return_value=[healthcare_adapter]),
        ):
            result = await service.validate_mapping_consistency(
                mock_session, "genesis:ehr_connector"
            )

            assert result["valid"] is True  # Only warnings, not errors
            assert "Healthcare component missing HIPAA compliance metadata" in result["warnings"]
            assert "Healthcare adapter for langflow missing compliance rules" in result["warnings"]

    @pytest.mark.asyncio
    async def test_get_component_mapping_with_adapters(self, service, mock_session, sample_mapping, sample_adapter):
        """Test getting component mapping with adapters."""
        with patch.multiple(
            'langflow.services.component_mapping.service.ComponentMappingService',
            get_component_mapping_by_genesis_type=AsyncMock(return_value=sample_mapping),
            get_all_adapters_for_genesis_type=AsyncMock(return_value=[sample_adapter]),
        ):
            result = await service.get_component_mapping_with_adapters(
                mock_session, "genesis:test_component"
            )

            assert result["mapping"].genesis_type == "genesis:test_component"
            assert len(result["adapters"]) == 1
            assert RuntimeTypeEnum.LANGFLOW.value in result["supported_runtimes"]

    @pytest.mark.asyncio
    async def test_get_statistics(self, service, mock_session):
        """Test getting mapping statistics."""
        mapping_counts = {"tool": 5, "healthcare": 3, "agent": 2}
        adapter_counts = {"langflow": 8, "temporal": 2}
        supported_runtimes = [RuntimeTypeEnum.LANGFLOW.value, RuntimeTypeEnum.TEMPORAL]

        with patch.multiple(
            'langflow.services.database.models.component_mapping.crud.ComponentMappingCRUD',
            count_by_category=AsyncMock(return_value=mapping_counts),
        ), patch.multiple(
            'langflow.services.database.models.component_mapping.crud.RuntimeAdapterCRUD',
            count_by_runtime=AsyncMock(return_value=adapter_counts),
            get_supported_runtimes=AsyncMock(return_value=supported_runtimes),
        ):
            result = await service.get_statistics(mock_session)

            assert result["component_mappings"]["total"] == 10
            assert result["component_mappings"]["by_category"] == mapping_counts
            assert result["runtime_adapters"]["total"] == 10
            assert result["runtime_adapters"]["by_runtime"] == adapter_counts
            assert result["supported_runtimes"] == supported_runtimes

    @pytest.mark.asyncio
    async def test_migrate_hardcoded_mappings(self, service, mock_session):
        """Test migrating hardcoded mappings."""
        hardcoded_mappings = {
            "genesis:test_component": {
                "component": "TestComponent",
                "config": {"key": "value"},
            }
        }

        with patch.multiple(
            'langflow.services.component_mapping.service.ComponentMappingService',
            get_component_mapping_by_genesis_type=AsyncMock(return_value=None),
            create_component_mapping=AsyncMock(return_value=AsyncMock()),
            get_runtime_adapter_for_genesis_type=AsyncMock(return_value=None),
            create_runtime_adapter=AsyncMock(return_value=AsyncMock()),
        ):
            result = await service.migrate_hardcoded_mappings(
                mock_session, hardcoded_mappings
            )

            assert result["created"] == 1
            assert result["updated"] == 0
            assert result["skipped"] == 0
            assert len(result["errors"]) == 0