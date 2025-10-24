"""Tests for Genesis Knowledge Service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import aiohttp
from langflow.services.knowledge.service import KnowledgeService
from langflow.services.knowledge.settings import KnowledgeSettings


class TestKnowledgeService:
    """Test KnowledgeService class."""

    @pytest.fixture
    def mock_settings(self):
        """Mock KnowledgeSettings."""
        settings = Mock(spec=KnowledgeSettings)
        settings.ENDPOINT_URL = "http://localhost:3002"
        settings.GENESIS_CLIENT_ID = "test-client-123"
        settings.TIMEOUT = 120
        settings.USER_AGENT = "genesis_studio"
        settings.is_configured.return_value = True
        return settings

    @pytest.fixture
    def service(self, mock_settings):
        """Create KnowledgeService with mocked settings."""
        with patch('langflow.services.knowledge.service.KnowledgeSettings', return_value=mock_settings):
            return KnowledgeService()

    def test_service_initialization(self, service, mock_settings):
        """Test service initialization."""
        assert service.name == "knowledge_service"
        assert service.settings == mock_settings
        assert service._http_client is None
        assert service._hub_cache is None
        assert service._ready is False

    def test_set_ready_with_valid_settings(self, service, mock_settings):
        """Test setting service as ready with valid settings."""
        mock_settings.is_configured.return_value = True

        service.set_ready()

        assert service._ready is True
        assert service.ready is True

    def test_set_ready_with_invalid_settings(self, service, mock_settings):
        """Test setting service as ready with invalid settings."""
        mock_settings.is_configured.return_value = False

        with pytest.raises(ValueError) as exc_info:
            service.set_ready()

        assert "KnowledgeHub settings are not properly configured" in str(exc_info.value)
        assert service._ready is False

    def test_http_client_property(self, service):
        """Test HTTP client property."""
        # First access should create client
        client = service.http_client
        assert isinstance(client, aiohttp.ClientSession)
        assert client is service._http_client

        # Second access should return same client
        client2 = service.http_client
        assert client2 is client

    def test_http_client_recreated_if_closed(self, service):
        """Test HTTP client is recreated if previous one is closed."""
        # Get initial client
        client1 = service.http_client

        # Mock closed client
        service._http_client.closed = True

        # Should create new client
        client2 = service.http_client
        assert client2 is not client1

    @pytest.mark.asyncio
    async def test_cleanup(self, service):
        """Test service cleanup."""
        # Create client
        client = service.http_client
        mock_close = AsyncMock()
        client.close = mock_close
        client.closed = False

        await service.cleanup()

        mock_close.assert_called_once()
        assert service._http_client is None

    @pytest.mark.asyncio
    async def test_cleanup_no_client(self, service):
        """Test cleanup when no client exists."""
        # Should not raise error
        await service.cleanup()
        assert service._http_client is None

    @pytest.mark.asyncio
    async def test_get_knowledge_hubs_success(self, service):
        """Test successful knowledge hubs retrieval."""
        service.set_ready()

        mock_response_data = {
            "data": [
                {"id": "hub1", "name": "Medical Knowledge"},
                {"id": "hub2", "name": "Drug Database"},
                {"id": "hub3", "name": "Clinical Guidelines"}
            ]
        }

        with patch.object(service, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None

            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value.__aenter__.return_value = mock_response
            mock_client.get.return_value.__aexit__.return_value = None

            mock_get_client.return_value = mock_client

            result = await service.get_knowledge_hubs()

        assert len(result) == 3
        assert result[0]["id"] == "hub1"
        assert result[0]["name"] == "Medical Knowledge"
        assert result[1]["id"] == "hub2"
        assert result[1]["name"] == "Drug Database"

        # Result should be cached
        assert service._hub_cache == result

    @pytest.mark.asyncio
    async def test_get_knowledge_hubs_cached(self, service):
        """Test knowledge hubs retrieval from cache."""
        service.set_ready()
        cached_data = [{"id": "cached", "name": "Cached Hub"}]
        service._hub_cache = cached_data

        result = await service.get_knowledge_hubs()

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_get_knowledge_hubs_not_ready(self, service):
        """Test knowledge hubs retrieval when service not ready."""
        # Don't call set_ready()

        result = await service.get_knowledge_hubs()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_knowledge_hubs_http_error(self, service):
        """Test knowledge hubs retrieval with HTTP error."""
        service.set_ready()

        with patch.object(service, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = aiohttp.ClientError("Connection failed")
            mock_get_client.return_value = mock_client

            result = await service.get_knowledge_hubs()

        assert result == []

    @pytest.mark.asyncio
    async def test_query_vector_store_success(self, service):
        """Test successful vector store query."""
        service.set_ready()

        mock_response_data = {
            "data": {
                "result": [
                    {
                        "metadata": {
                            "content": "Medical content about symptoms",
                            "source": "medical_journal.pdf",
                            "score": 0.95
                        }
                    },
                    {
                        "metadata": {
                            "content": "Drug interaction information",
                            "source": "drug_database.txt",
                            "score": 0.87
                        }
                    }
                ]
            }
        }

        with patch.object(service, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None

            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value.__aenter__.return_value = mock_response
            mock_client.post.return_value.__aexit__.return_value = None

            mock_get_client.return_value = mock_client

            result = await service.query_vector_store(
                knowledge_hub_ids=["hub1", "hub2"],
                query="drug interactions",
                embedding_model="bge_base",
                top_k=10
            )

        assert len(result) == 2
        assert result[0]["metadata"]["content"] == "Medical content about symptoms"
        assert result[1]["metadata"]["source"] == "drug_database.txt"

        # Verify the request was made correctly
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "knowledge-hub/query" in call_args[0][0]

        # Verify payload
        json_payload = call_args[1]["json"]
        assert json_payload["knowledgeHubIds"] == ["hub1", "hub2"]
        assert json_payload["query"] == "drug interactions"
        assert json_payload["embeddingModel"] == "bge_base"
        assert json_payload["topK"] == 10

    @pytest.mark.asyncio
    async def test_query_vector_store_not_ready(self, service):
        """Test vector store query when service not ready."""
        # Don't call set_ready()

        result = await service.query_vector_store(
            knowledge_hub_ids=["hub1"],
            query="test query"
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_query_vector_store_http_error(self, service):
        """Test vector store query with HTTP error."""
        service.set_ready()

        with patch.object(service, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = aiohttp.ClientError("Query failed")
            mock_get_client.return_value = mock_client

            result = await service.query_vector_store(
                knowledge_hub_ids=["hub1"],
                query="test query"
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_knowledge_hub_documents_success(self, service):
        """Test successful knowledge hub documents retrieval."""
        service.set_ready()

        mock_response_data = {
            "data": {
                "items": [
                    {
                        "id": "doc1",
                        "name": "medical_guide.pdf",
                        "documentType": "pdf",
                        "documentUUID": "uuid-123",
                        "createdAt": "2023-01-01T00:00:00Z",
                        "updatedAt": "2023-01-02T00:00:00Z",
                        "isDeleted": False
                    },
                    {
                        "id": "doc2",
                        "name": "clinical_notes/patient_records.txt",
                        "documentType": "txt",
                        "documentUUID": "uuid-456",
                        "createdAt": "2023-01-01T00:00:00Z",
                        "updatedAt": "2023-01-02T00:00:00Z",
                        "isDeleted": False
                    }
                ]
            }
        }

        with patch.object(service, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None

            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value.__aenter__.return_value = mock_response
            mock_client.get.return_value.__aexit__.return_value = None

            mock_get_client.return_value = mock_client

            result = await service.get_knowledge_hub_documents("hub1")

        assert len(result) == 2
        assert result[0]["id"] == "doc1"
        assert result[0]["name"] == "medical_guide.pdf"
        assert result[0]["folder"] is None
        assert result[1]["name"] == "clinical_notes/patient_records.txt"
        assert result[1]["folder"] == "clinical_notes"

    @pytest.mark.asyncio
    async def test_get_knowledge_hub_documents_filters_deleted(self, service):
        """Test that deleted documents are filtered out."""
        service.set_ready()

        mock_response_data = {
            "data": {
                "items": [
                    {
                        "id": "doc1",
                        "name": "active_doc.pdf",
                        "isDeleted": False
                    },
                    {
                        "id": "doc2",
                        "name": "deleted_doc.pdf",
                        "isDeleted": True
                    }
                ]
            }
        }

        with patch.object(service, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None

            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value.__aenter__.return_value = mock_response
            mock_client.get.return_value.__aexit__.return_value = None

            mock_get_client.return_value = mock_client

            result = await service.get_knowledge_hub_documents("hub1")

        assert len(result) == 1
        assert result[0]["name"] == "active_doc.pdf"

    @pytest.mark.asyncio
    async def test_get_knowledge_hub_documents_no_hub_id(self, service):
        """Test documents retrieval with no hub ID."""
        service.set_ready()

        result = await service.get_knowledge_hub_documents("")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_document_signed_url_success(self, service):
        """Test successful signed URL retrieval."""
        service.set_ready()

        mock_response_data = {
            "data": {
                "signedUrl": "https://s3.amazonaws.com/bucket/file.pdf?signature=abc123"
            }
        }

        with patch.object(service, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None

            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value.__aenter__.return_value = mock_response
            mock_client.post.return_value.__aexit__.return_value = None

            mock_get_client.return_value = mock_client

            result = await service.get_document_signed_url("hub1", "documents/file.pdf")

        assert result == "https://s3.amazonaws.com/bucket/file.pdf?signature=abc123"

    @pytest.mark.asyncio
    async def test_get_document_signed_url_not_ready(self, service):
        """Test signed URL retrieval when service not ready."""
        # Don't call set_ready()

        result = await service.get_document_signed_url("hub1", "file.pdf")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_document_signed_url_error(self, service):
        """Test signed URL retrieval with error."""
        service.set_ready()

        with patch.object(service, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = aiohttp.ClientError("URL generation failed")
            mock_get_client.return_value = mock_client

            result = await service.get_document_signed_url("hub1", "file.pdf")

        assert result is None

    def test_settings_configuration(self):
        """Test settings configuration validation."""
        # Test configured settings
        settings = KnowledgeSettings()
        settings.ENDPOINT_URL = "http://localhost:3002"
        settings.CLIENT_ID = "test-client"

        assert settings.is_configured() is True

        # Test unconfigured settings
        settings.ENDPOINT_URL = ""
        assert settings.is_configured() is False

        settings.ENDPOINT_URL = "http://localhost:3002"
        settings.CLIENT_ID = ""
        assert settings.is_configured() is False