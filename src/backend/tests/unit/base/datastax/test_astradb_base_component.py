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

    def test_map_cloud_providers_structure(self):
        """Test that map_cloud_providers returns correct structure."""
        providers = AstraDBBaseComponent.map_cloud_providers()

        assert "prod" in providers
        assert "dev" in providers
        assert "test" in providers

    def test_map_cloud_providers_prod_content(self):
        """Test production environment cloud providers."""
        providers = AstraDBBaseComponent.map_cloud_providers()
        prod = providers["prod"]

        assert "Amazon Web Services" in prod
        assert "Google Cloud Platform" in prod
        assert "Microsoft Azure" in prod

        assert prod["Amazon Web Services"]["id"] == "aws"
        assert "us-east-2" in prod["Amazon Web Services"]["regions"]

    def test_map_cloud_providers_dev_content(self):
        """Test development environment cloud providers."""
        providers = AstraDBBaseComponent.map_cloud_providers()
        dev = providers["dev"]

        assert "Amazon Web Services" in dev
        assert "Google Cloud Platform" in dev
        assert dev["Amazon Web Services"]["id"] == "aws"


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

    def test_get_keyspace_strips_whitespace(self, mock_component):
        """Test that keyspace value is stripped of whitespace."""
        mock_component.keyspace = "  custom_keyspace  "
        assert mock_component.get_keyspace() == "custom_keyspace"

    def test_get_keyspace_empty_string_returns_default(self, mock_component):
        """Test that empty string returns default keyspace."""
        mock_component.keyspace = ""
        assert mock_component.get_keyspace() == "default_keyspace"


class TestApiEndpointRetrieval:
    """Tests for API endpoint retrieval."""

    def test_get_api_endpoint_static_direct_value(self):
        """Test getting API endpoint when directly provided."""
        endpoint = "https://direct.endpoint.com"
        result = AstraDBBaseComponent.get_api_endpoint_static(
            token="test_token",  # noqa: S106
            api_endpoint=endpoint,
            database_name="test_db",
        )
        assert result == endpoint

    def test_get_api_endpoint_static_database_name_is_url(self):
        """Test when database_name is actually a URL."""
        url = "https://database.endpoint.com"
        result = AstraDBBaseComponent.get_api_endpoint_static(
            token="test_token",  # noqa: S106
            database_name=url,
        )
        assert result == url

    def test_get_api_endpoint_static_no_database_name(self):
        """Test when no database name provided."""
        result = AstraDBBaseComponent.get_api_endpoint_static(
            token="test_token",  # noqa: S106
            database_name=None,
        )
        assert result is None

    @patch.object(AstraDBBaseComponent, "get_database_list_static")
    def test_get_api_endpoint_static_from_database_list(self, mock_get_db_list):
        """Test getting API endpoint from database list."""
        mock_get_db_list.return_value = {
            "test_db": {
                "api_endpoints": ["https://test.endpoint.com"],
            }
        }

        result = AstraDBBaseComponent.get_api_endpoint_static(
            token="test_token",  # noqa: S106
            database_name="test_db",
        )
        assert result == "https://test.endpoint.com"

    @patch.object(AstraDBBaseComponent, "get_database_list_static")
    def test_get_api_endpoint_static_database_not_found(self, mock_get_db_list):
        """Test when database not found in list."""
        mock_get_db_list.return_value = {}

        result = AstraDBBaseComponent.get_api_endpoint_static(
            token="test_token",  # noqa: S106
            database_name="nonexistent_db",
        )
        assert result is None


class TestProviderIcon:
    """Tests for provider icon mapping."""

    def test_get_provider_icon_no_provider(self):
        """Test icon when no provider specified."""
        icon = AstraDBBaseComponent.get_provider_icon()
        assert icon == "vectorstores"

    def test_get_provider_icon_bring_your_own(self):
        """Test icon for 'bring your own' provider."""
        icon = AstraDBBaseComponent.get_provider_icon(provider_name="Bring your own")
        assert icon == "vectorstores"

    def test_get_provider_icon_nvidia(self):
        """Test icon for NVIDIA provider."""
        icon = AstraDBBaseComponent.get_provider_icon(provider_name="nvidia")
        assert icon == "NVIDIA"

    def test_get_provider_icon_openai(self):
        """Test icon for OpenAI provider."""
        icon = AstraDBBaseComponent.get_provider_icon(provider_name="openai")
        assert icon == "OpenAI"

    def test_get_provider_icon_cohere(self):
        """Test icon for Cohere provider."""
        icon = AstraDBBaseComponent.get_provider_icon(provider_name="cohere")
        assert icon == "Cohere"

    def test_get_provider_icon_unknown_provider(self):
        """Test icon for unknown provider uses title case."""
        icon = AstraDBBaseComponent.get_provider_icon(provider_name="unknown provider")
        assert icon == "Unknown Provider"

    def test_get_provider_icon_from_collection(self):
        """Test getting icon from collection object."""
        mock_collection = Mock()
        mock_collection.definition.vector.service.provider = "nvidia"

        icon = AstraDBBaseComponent.get_provider_icon(collection=mock_collection)
        assert icon == "NVIDIA"


class TestResetBuildConfig:
    """Tests for resetting build configuration."""

    def test_reset_build_config(self, mock_component, mock_build_config):
        """Test reset_build_config clears all options."""
        result = mock_component.reset_build_config(mock_build_config)

        assert result["database_name"]["options"] == []
        assert result["database_name"]["options_metadata"] == []
        assert result["database_name"]["value"] == ""
        assert result["database_name"]["show"] is False

        assert result["collection_name"]["options"] == []
        assert result["collection_name"]["options_metadata"] == []
        assert result["collection_name"]["value"] == ""
        assert result["collection_name"]["show"] is False

    def test_reset_build_config_with_hybrid_fields(self, mock_component, mock_build_config):
        """Test reset includes hybrid search fields if present."""
        result = mock_component.reset_build_config(mock_build_config)

        assert result["reranker"]["options"] == []
        assert result["reranker"]["value"] == ""
        assert result["reranker"]["show"] is False

        assert result["lexical_terms"]["value"] == ""
        assert result["lexical_terms"]["show"] is False


class TestResetDimensionField:
    """Tests for resetting dimension field."""

    def test_reset_dimension_field_bring_your_own(self, mock_component, mock_build_config):
        """Test dimension field reset for 'bring your own' provider."""
        template = mock_build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"]
        template["02_embedding_generation_provider"]["value"] = "Bring your own"

        result = mock_component.reset_dimension_field(mock_build_config)
        dimension_field = result["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"][
            "04_dimension"
        ]

        assert dimension_field["value"] is None
        assert dimension_field["readonly"] is False
        assert dimension_field["required"] is True

    def test_reset_dimension_field_with_provider(self, mock_component, mock_build_config):
        """Test dimension field reset with embedding provider."""
        template = mock_build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"]
        template["02_embedding_generation_provider"]["value"] = "nvidia"

        result = mock_component.reset_dimension_field(mock_build_config)
        dimension_field = result["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"][
            "04_dimension"
        ]

        assert dimension_field["value"] == 1024
        assert dimension_field["readonly"] is True
        assert dimension_field["required"] is False


class TestCollectionData:
    """Tests for collection data retrieval."""

    @patch("astrapy.DataAPIClient")
    def test_collection_data_success(self, mock_client_class, mock_component):
        """Test successful collection data retrieval."""
        mock_database = Mock()
        mock_collection = Mock()
        mock_collection.estimated_document_count.return_value = 100

        mock_database.get_collection.return_value = mock_collection
        mock_client = mock_client_class.return_value
        mock_client.get_database.return_value = mock_database

        with patch.object(mock_component, "get_api_endpoint", return_value="https://test.endpoint.com"), \
             patch.object(mock_component, "get_keyspace", return_value="default_keyspace"):
            count = mock_component.collection_data("test_collection")
            assert count == 100

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
    @patch("astrapy.DataAPIClient")
    async def test_create_database_api_success(self, mock_client_class):
        """Test successful database creation."""
        mock_admin = Mock()
        mock_admin.async_create_database = AsyncMock(return_value={"id": "new-db-id"})

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
    @patch("langchain_astradb.utils.astradb._AstraDBCollectionEnvironment")
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
            embedding_generation_provider="NVIDIA",
            embedding_generation_model="model1",
        )

        mock_env_class.assert_called_once()
        call_kwargs = mock_env_class.call_args[1]
        assert call_kwargs["collection_name"] == "new_collection"
        assert call_kwargs["collection_vector_service_options"] is not None

    @pytest.mark.asyncio
    @patch("langchain_astradb.utils.astradb._AstraDBCollectionEnvironment")
    async def test_create_collection_api_with_dimension(self, mock_env_class):
        """Test collection creation with explicit dimension."""
        await AstraDBBaseComponent.create_collection_api(
            new_collection_name="new_collection",
            token="test_token",  # noqa: S106
            api_endpoint="https://test.endpoint.com",
            dimension=1536,
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
    async def test_update_build_config_first_run(self, mock_init_db, mock_component, mock_build_config):
        """Test update_build_config on first run."""
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
        """Test changing search method to Hybrid Search."""
        mock_build_config["reranker"]["options"] = ["provider/model"]
        result = await mock_component.update_build_config(mock_build_config, "Hybrid Search", "search_method")

        assert result["lexical_terms"]["show"] is True
        assert result["reranker"]["show"] is True
        assert result["reranker"]["toggle_value"] is True
        assert result["search_type"]["show"] is False


class TestGetDatabaseObject:
    """Tests for getting database object."""

    @patch("astrapy.DataAPIClient")
    def test_get_database_object_success(self, mock_client_class, mock_component):
        """Test successful database object retrieval."""
        mock_database = Mock()
        mock_client = mock_client_class.return_value
        mock_client.get_database.return_value = mock_database

        with patch.object(mock_component, "get_api_endpoint", return_value="https://test.endpoint.com"), \
             patch.object(mock_component, "get_keyspace", return_value="default_keyspace"):
            db = mock_component.get_database_object()
            assert db == mock_database

    @patch("astrapy.DataAPIClient")
    def test_get_database_object_with_custom_endpoint(self, mock_client_class, mock_component):
        """Test database object retrieval with custom endpoint."""
        mock_database = Mock()
        mock_client = mock_client_class.return_value
        mock_client.get_database.return_value = mock_database

        with patch.object(mock_component, "get_keyspace", return_value="default_keyspace"):
            db = mock_component.get_database_object(api_endpoint="https://custom.endpoint.com")
            assert db == mock_database

    @patch("astrapy.DataAPIClient")
    def test_get_database_object_error(self, mock_client_class, mock_component):
        """Test database object retrieval error handling."""
        mock_client_class.side_effect = Exception("Connection error")

        with patch.object(mock_component, "get_api_endpoint", return_value="https://test.endpoint.com"), \
             pytest.raises(ValueError, match="Error fetching database object"):
            mock_component.get_database_object()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
