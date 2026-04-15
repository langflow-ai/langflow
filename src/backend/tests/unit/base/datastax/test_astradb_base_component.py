from collections import defaultdict
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Assuming the component is imported from the module
# Adjust the import path as needed
from lfx.base.datastax import AstraDBBaseComponent


@pytest.fixture
def mock_component():
    """Create a mock AstraDBBaseComponent instance."""
    component = AstraDBBaseComponent()
    component.token = "test_token"  # noqa: S105
    component.environment = "prod"
    component.database_name = "test_db"
    component.api_endpoint = None
    component.keyspace = None
    component.collection_name = "test_collection"
    component.log = Mock()
    return component


@pytest.fixture
def mock_database_info():
    """Mock database information structure."""
    return {
        "test_db": {
            "api_endpoints": ["https://test-db-id.apps.astra.datastax.com"],
            "keyspaces": ["default_keyspace", "custom_keyspace"],
            "collections": 5,
            "status": "ACTIVE",
            "org_id": "test-org-id",
        },
        "pending_db": {
            "api_endpoints": ["https://pending-db-id.apps.astra.datastax.com"],
            "keyspaces": ["default_keyspace"],
            "collections": 0,
            "status": "PENDING",
            "org_id": "test-org-id",
        },
    }


@pytest.fixture
def mock_build_config():
    """Mock build configuration structure."""
    return {
        "token": {"value": "test_token"},
        "environment": {"value": "prod"},
        "database_name": {
            "value": "test_db",
            "options": [],
            "options_metadata": [],
            "show": False,
            "dialog_inputs": {
                "fields": {
                    "data": {
                        "node": {
                            "template": {
                                "02_cloud_provider": {"options": []},
                                "03_region": {"options": [], "value": None},
                            }
                        }
                    }
                }
            },
        },
        "api_endpoint": {"value": "", "options": []},
        "keyspace": {"value": "", "options": []},
        "collection_name": {
            "value": "",
            "options": [],
            "options_metadata": [],
            "show": False,
            "dialog_inputs": {
                "fields": {
                    "data": {
                        "node": {
                            "template": {
                                "01_new_collection_name": {},
                                "02_embedding_generation_provider": {
                                    "value": None,
                                    "options": [],
                                    "options_metadata": [],
                                    "helper_text": "",
                                },
                                "03_embedding_generation_model": {
                                    "options": [],
                                    "placeholder": None,
                                    "readonly": False,
                                    "required": True,
                                    "value": None,
                                },
                                "04_dimension": {
                                    "placeholder": None,
                                    "value": None,
                                    "readonly": False,
                                    "required": False,
                                },
                            }
                        }
                    }
                }
            },
        },
        "embedding_model": {"show": True, "required": False},
        "autodetect_collection": {"value": True},
        "search_method": {"value": "Vector Search", "show": False, "options": []},
        "search_type": {"value": "Similarity", "show": True},
        "search_score_threshold": {"show": True},
        "reranker": {
            "value": "",
            "options": [],
            "options_metadata": [],
            "show": False,
            "toggle_disable": False,
            "toggle_value": True,
        },
        "lexical_terms": {"value": "", "show": False},
    }


class TestCloudProviderMapping:
    """Tests for cloud provider mapping."""

    @patch("lfx.base.datastax.astradb_base.DataAPIClient")
    def test_map_cloud_providers_structure(self, mock_client_class):
        """Test that map_cloud_providers returns correct structure."""
        # Mock the admin client and its methods
        mock_admin = Mock()
        # Mock find_available_regions to return a list of region objects
        mock_region1 = Mock()
        mock_region1.cloud_provider = "AWS"
        mock_region1.name = "us-east-2"
        mock_region2 = Mock()
        mock_region2.cloud_provider = "GCP"
        mock_region2.name = "us-central1"
        mock_region3 = Mock()
        mock_region3.cloud_provider = "Azure"
        mock_region3.name = "eastus"

        mock_admin.find_available_regions.return_value = [mock_region1, mock_region2, mock_region3]

        mock_client = mock_client_class.return_value
        mock_client.get_admin.return_value = mock_admin

        providers = AstraDBBaseComponent.map_cloud_providers(token="test_token")  # noqa: S106

        assert "Amazon Web Services" in providers
        assert "Google Cloud Platform" in providers
        assert "Microsoft Azure" in providers

    @patch("lfx.base.datastax.astradb_base.DataAPIClient")
    def test_map_cloud_providers_prod_content(self, mock_client_class):
        """Test production environment cloud providers."""
        # Mock the admin client and its methods
        mock_admin = Mock()
        # Mock find_available_regions to return a list of region objects
        mock_region1 = Mock()
        mock_region1.cloud_provider = "AWS"
        mock_region1.name = "us-east-2"
        mock_region2 = Mock()
        mock_region2.cloud_provider = "AWS"
        mock_region2.name = "us-west-2"
        mock_region3 = Mock()
        mock_region3.cloud_provider = "GCP"
        mock_region3.name = "us-central1"
        mock_region4 = Mock()
        mock_region4.cloud_provider = "Azure"
        mock_region4.name = "eastus"

        mock_admin.find_available_regions.return_value = [mock_region1, mock_region2, mock_region3, mock_region4]

        mock_client = mock_client_class.return_value
        mock_client.get_admin.return_value = mock_admin

        providers = AstraDBBaseComponent.map_cloud_providers(token="test_token")  # noqa: S106

        assert "Amazon Web Services" in providers
        assert "Google Cloud Platform" in providers
        assert "Microsoft Azure" in providers

        assert providers["Amazon Web Services"]["id"] == "aws"
        assert "us-east-2" in providers["Amazon Web Services"]["regions"]
        assert "us-west-2" in providers["Amazon Web Services"]["regions"]

    @patch("lfx.base.datastax.astradb_base.DataAPIClient")
    def test_map_cloud_providers_dev_content(self, mock_client_class):
        """Test development environment cloud providers."""
        # Mock the admin client and its methods
        mock_admin = Mock()
        # Mock find_available_regions to return a list of region objects
        mock_region1 = Mock()
        mock_region1.cloud_provider = "AWS"
        mock_region1.name = "us-east-2"
        mock_region2 = Mock()
        mock_region2.cloud_provider = "GCP"
        mock_region2.name = "us-central1"

        mock_admin.find_available_regions.return_value = [mock_region1, mock_region2]

        mock_client = mock_client_class.return_value
        mock_client.get_admin.return_value = mock_admin

        providers = AstraDBBaseComponent.map_cloud_providers(token="test_token")  # noqa: S106

        assert "Amazon Web Services" in providers
        assert "Google Cloud Platform" in providers
        assert providers["Amazon Web Services"]["id"] == "aws"


class TestDatabaseIdExtraction:
    """Tests for database ID extraction from API endpoints."""

    def test_get_database_id_static_valid_uuid(self):
        """Test extracting valid UUID from API endpoint."""
        api_endpoint = "https://12345678-1234-1234-1234-123456789abc.apps.astra.datastax.com"
        db_id = AstraDBBaseComponent.get_database_id_static(api_endpoint)

        assert db_id == "12345678-1234-1234-1234-123456789abc"

    def test_get_database_id_static_no_uuid(self):
        """Test extraction returns None when no UUID present."""
        api_endpoint = "https://invalid.endpoint.com"
        db_id = AstraDBBaseComponent.get_database_id_static(api_endpoint)

        assert db_id is None

    def test_get_database_id_static_case_insensitive(self):
        """Test UUID extraction is case insensitive."""
        api_endpoint = "https://ABCDEF12-ABCD-ABCD-ABCD-ABCDEFABCDEF.apps.astra.datastax.com"
        db_id = AstraDBBaseComponent.get_database_id_static(api_endpoint)

        assert db_id == "ABCDEF12-ABCD-ABCD-ABCD-ABCDEFABCDEF"

    def test_get_database_id_instance_method(self, mock_component):
        """Test instance method for getting database ID."""
        with patch.object(
            mock_component,
            "get_api_endpoint",
            return_value="https://12345678-1234-1234-1234-123456789abc.apps.astra.datastax.com",
        ):
            db_id = mock_component.get_database_id()
            assert db_id == "12345678-1234-1234-1234-123456789abc"


class TestKeyspaceHandling:
    """Tests for keyspace handling."""

    def test_get_keyspace_default(self, mock_component):
        """Test getting default keyspace when none set."""
        mock_component.keyspace = None
        assert mock_component.get_keyspace() == "default_keyspace"

    def test_get_keyspace_with_value(self, mock_component):
        """Test getting keyspace when value is set."""
        mock_component.keyspace = "custom_keyspace"
        assert mock_component.get_keyspace() == "custom_keyspace"

    def test_get_keyspace_with_empty_string(self, mock_component):
        """Test getting keyspace with empty string returns default."""
        mock_component.keyspace = ""
        assert mock_component.get_keyspace() == "default_keyspace"


class TestCollectionDataRetrieval:
    """Tests for collection data retrieval."""

    def test_collection_data_success(self, mock_component):
        """Test successful collection data retrieval."""
        mock_database = Mock()
        mock_collection = Mock()
        mock_collection.estimated_document_count.return_value = 100
        mock_database.get_collection.return_value = mock_collection

        count = mock_component.collection_data("test_collection", database=mock_database)
        assert count == 100
        mock_database.get_collection.assert_called_once_with("test_collection")
        mock_collection.estimated_document_count.assert_called_once()

    def test_collection_data_with_provided_database(self, mock_component):
        """Test collection data retrieval with provided database object."""
        mock_database = Mock()
        mock_collection = Mock()
        mock_collection.estimated_document_count.return_value = 50

        mock_database.get_collection.return_value = mock_collection

        count = mock_component.collection_data("test_collection", database=mock_database)
        assert count == 50

    def test_collection_data_error_handling(self, mock_component):
        """Test collection data error handling."""
        mock_database = Mock()
        mock_database.get_collection.side_effect = Exception("Connection error")

        result = mock_component.collection_data("test_collection", database=mock_database)
        assert result is None
        mock_component.log.assert_called_once()


class TestDatabaseCreation:
    """Tests for database creation."""

    @pytest.mark.asyncio
    @patch("lfx.base.datastax.astradb_base.DataAPIClient")
    async def test_create_database_api_success(self, mock_client_class):
        """Test successful database creation."""
        mock_admin = Mock()
        # Fix: Make async_create_database return a proper awaitable that yields a dict
        mock_admin.async_create_database = AsyncMock(return_value={"id": "new-db-id"})

        # Mock find_available_regions to return a list of region objects
        mock_region = Mock()
        mock_region.cloud_provider = "AWS"
        mock_region.name = "us-east-2"
        mock_admin.find_available_regions.return_value = [mock_region]

        mock_client = mock_client_class.return_value
        mock_client.get_admin.return_value = mock_admin

        result = await AstraDBBaseComponent.create_database_api(
            new_database_name="new_db",
            cloud_provider="Amazon Web Services",
            region="us-east-2",
            token="test_token",  # noqa: S106
            environment="prod",
        )

        assert result == {"id": "new-db-id"}
        mock_admin.async_create_database.assert_called_once()


class TestCollectionCreation:
    """Tests for collection creation."""

    @pytest.mark.asyncio
    @patch("lfx.base.datastax.astradb_base._AstraDBCollectionEnvironment")
    @patch.object(AstraDBBaseComponent, "get_vectorize_providers")
    async def test_create_collection_api_with_vectorize(self, mock_get_providers, mock_env_class):
        """Test collection creation with vectorize options."""
        mock_get_providers.return_value = defaultdict(
            list,
            {
                "NVIDIA": ["nvidia", ["model1", "model2"]],
            },
        )

        await AstraDBBaseComponent.create_collection_api(
            new_collection_name="new_collection",
            token="test_token",  # noqa: S106
            api_endpoint="https://test.endpoint.com",
            keyspace="default_keyspace",
            embedding_generation_provider="NVIDIA",
            embedding_generation_model="model1",
        )

        mock_env_class.assert_called_once()
        call_kwargs = mock_env_class.call_args[1]
        assert call_kwargs["collection_name"] == "new_collection"
        assert call_kwargs["collection_vector_service_options"] is not None

    @pytest.mark.asyncio
    @patch("lfx.base.datastax.astradb_base._AstraDBCollectionEnvironment")
    async def test_create_collection_api_with_dimension(self, mock_env_class):
        """Test collection creation with explicit dimension."""
        await AstraDBBaseComponent.create_collection_api(
            new_collection_name="new_collection",
            token="test_token",  # noqa: S106
            api_endpoint="https://test.endpoint.com",
            dimension=1536,
            keyspace="default_keyspace",
        )

        mock_env_class.assert_called_once()
        call_kwargs = mock_env_class.call_args[1]
        assert call_kwargs["embedding_dimension"] == 1536
        assert call_kwargs["collection_vector_service_options"] is None

    @pytest.mark.asyncio
    async def test_create_collection_api_no_name(self):
        """Test collection creation fails without name."""
        with pytest.raises(ValueError, match="Collection name is required"):
            await AstraDBBaseComponent.create_collection_api(
                new_collection_name="",
                token="test_token",  # noqa: S106
                api_endpoint="https://test.endpoint.com",
                keyspace="default_keyspace",
            )


class TestUpdateBuildConfig:
    """Tests for update_build_config method."""

    @pytest.mark.asyncio
    async def test_update_build_config_no_token(self, mock_component, mock_build_config):
        """Test update_build_config with no token resets config."""
        mock_component.token = None
        result = await mock_component.update_build_config(mock_build_config, "", "database_name")

        assert result["database_name"]["options"] == []
        assert result["database_name"]["show"] is False

    @pytest.mark.asyncio
    @patch.object(AstraDBBaseComponent, "_initialize_database_options")
    @patch.object(AstraDBBaseComponent, "map_cloud_providers")
    async def test_update_build_config_first_run(
        self, mock_map_providers, mock_init_db, mock_component, mock_build_config
    ):
        """Test update_build_config on first run."""
        # Mock the cloud providers mapping to avoid API calls
        mock_map_providers.return_value = {
            "prod": {
                "Amazon Web Services": {
                    "id": "aws",
                    "regions": ["us-east-2", "us-west-2"],
                }
            },
            "dev": {},
            "test": {},
        }

        mock_init_db.return_value = [
            {
                "name": "db1",
                "status": None,
                "collections": 5,
                "api_endpoints": ["https://db1.endpoint.com"],
                "keyspaces": ["default_keyspace"],
                "org_id": "org-id",
            }
        ]

        result = await mock_component.update_build_config(mock_build_config, "", "collection_name")

        assert "db1" in result["database_name"]["options"]
        mock_init_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_build_config_search_method_change_to_hybrid(self, mock_component, mock_build_config):
        """Test base update_build_config doesn't handle search_method."""
        # The base AstraDBBaseComponent doesn't handle search_method changes
        # This functionality is in the AstraDBVectorStoreComponent subclass
        result = await mock_component.update_build_config(mock_build_config, "Hybrid Search", "search_method")

        # Base component should return config unchanged for search_method
        assert result["lexical_terms"]["show"] is False  # Default value from fixture
        assert result["reranker"]["show"] is False  # Default value from fixture


class TestGetDatabaseObject:
    """Tests for getting database object."""

    @patch("lfx.base.datastax.astradb_base.DataAPIClient")
    def test_get_database_object_success(self, mock_client_class, mock_component):
        """Test successful database object retrieval."""
        mock_database = Mock()
        mock_client = mock_client_class.return_value
        mock_client.get_database.return_value = mock_database

        with (
            patch.object(mock_component, "get_api_endpoint", return_value="https://test.endpoint.com"),
            patch.object(mock_component, "get_keyspace", return_value="default_keyspace"),
        ):
            db = mock_component.get_database_object()
            assert db == mock_database

    @patch("lfx.base.datastax.astradb_base.DataAPIClient")
    def test_get_database_object_with_custom_endpoint(self, mock_client_class, mock_component):
        """Test database object retrieval with custom endpoint."""
        mock_database = Mock()
        mock_client = mock_client_class.return_value
        mock_client.get_database.return_value = mock_database

        with patch.object(mock_component, "get_keyspace", return_value="default_keyspace"):
            db = mock_component.get_database_object(api_endpoint="https://custom.endpoint.com")
            assert db == mock_database

    @patch("lfx.base.datastax.astradb_base.DataAPIClient")
    def test_get_database_object_error(self, mock_client_class, mock_component):
        """Test database object retrieval error handling."""
        mock_client_class.side_effect = Exception("Connection error")

        with (
            patch.object(mock_component, "get_api_endpoint", return_value="https://test.endpoint.com"),
            pytest.raises(ValueError, match="Error fetching database object"),
        ):
            mock_component.get_database_object()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
