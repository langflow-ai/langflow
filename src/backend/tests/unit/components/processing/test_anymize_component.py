import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import pytest

from lfx.components.processing.anymize import AnymizeComponent
from lfx.schema import Message
from tests.base import ComponentTestBaseWithoutClient


class TestAnymizeComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return AnymizeComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "anymize_api": "test_api_key_123",
            "operation": "anonymize_text",
            "text": "John Doe lives at 123 Main St",
            "language": "en",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_update_build_config_anonymize_text(self):
        """Test build config updates for anonymize_text operation."""
        component = AnymizeComponent()
        build_config = {}

        updated_config = component.update_build_config(build_config, "anonymize_text", "operation")

        assert updated_config["text"]["show"] is True
        assert updated_config["language"]["show"] is True
        assert updated_config["file"]["show"] is False

    def test_update_build_config_deanonymize_text(self):
        """Test build config updates for deanonymize_text operation."""
        component = AnymizeComponent()
        build_config = {}

        updated_config = component.update_build_config(build_config, "deanonymize_text", "operation")

        assert updated_config["text"]["show"] is True
        assert updated_config["language"]["show"] is False
        assert updated_config["file"]["show"] is False

    def test_update_build_config_file_anonymization(self):
        """Test build config updates for file_anonymization operation."""
        component = AnymizeComponent()
        build_config = {}

        updated_config = component.update_build_config(build_config, "file_anonymization", "operation")

        assert updated_config["text"]["show"] is False
        assert updated_config["language"]["show"] is False
        assert updated_config["file"]["show"] is True

    def test_pre_run_setup(self):
        """Test pre-run setup initialization."""
        component = AnymizeComponent()
        component._pre_run_setup()

        assert component.operation == "anonymize_text"
        assert hasattr(component, "_build_config")
        assert component._build_config["text"]["show"] is True
        assert component._build_config["language"]["show"] is True
        assert component._build_config["file"]["show"] is False

    @pytest.mark.asyncio
    async def test_anonymize_text_success(self):
        """Test successful text anonymization."""
        component = AnymizeComponent(
            anymize_api="test_api_key", operation="anonymize_text", text="John Doe lives at 123 Main St", language="en"
        )

        # Mock the API calls
        with (
            patch.object(component, "_anonymize_text", new_callable=AsyncMock) as mock_anonymize,
            patch.object(component, "_poll_status", new_callable=AsyncMock) as mock_poll,
        ):
            mock_anonymize.return_value = {"job_id": "job123"}
            mock_poll.return_value = {
                "status": "completed",
                "anonymized_text_raw": "[[Name-abc123]] lives at [[Address-def456]]",
            }

            result = await component.process()

            assert isinstance(result, Message)
            assert result.text == "[[Name-abc123]] lives at [[Address-def456]]"
            mock_anonymize.assert_called_once_with("John Doe lives at 123 Main St", "en")
            mock_poll.assert_called_once_with("job123")

    @pytest.mark.asyncio
    async def test_anonymize_text_no_text_provided(self):
        """Test anonymize_text operation without text."""
        component = AnymizeComponent(anymize_api="test_api_key", operation="anonymize_text", text="", language="en")

        result = await component.process()

        assert isinstance(result, Message)
        assert result.text == "Error: No text provided for anonymization."

    @pytest.mark.asyncio
    async def test_anonymize_text_job_creation_failure(self):
        """Test anonymize_text when job creation fails."""
        component = AnymizeComponent(
            anymize_api="test_api_key", operation="anonymize_text", text="Test text", language="en"
        )

        with patch.object(component, "_anonymize_text", new_callable=AsyncMock) as mock_anonymize:
            mock_anonymize.return_value = {"error": "API key invalid"}

            result = await component.process()

            assert isinstance(result, Message)
            assert "Error: Failed to start anonymization job" in result.text

    @pytest.mark.asyncio
    async def test_deanonymize_text_success(self):
        """Test successful text deanonymization."""
        component = AnymizeComponent(
            anymize_api="test_api_key", operation="deanonymize_text", text="[[Name-abc123]] lives at [[Address-def456]]"
        )

        with patch.object(component, "_deanonymize_text", new_callable=AsyncMock) as mock_deanonymize:
            mock_deanonymize.return_value = {"text": "John Doe lives at 123 Main St"}

            result = await component.process()

            assert isinstance(result, Message)
            assert result.text == "John Doe lives at 123 Main St"
            mock_deanonymize.assert_called_once_with("[[Name-abc123]] lives at [[Address-def456]]")

    @pytest.mark.asyncio
    async def test_deanonymize_text_no_text_provided(self):
        """Test deanonymize_text operation without text."""
        component = AnymizeComponent(anymize_api="test_api_key", operation="deanonymize_text", text="")

        result = await component.process()

        assert isinstance(result, Message)
        assert result.text == "Error: No text provided for deanonymization."

    @pytest.mark.asyncio
    async def test_deanonymize_text_failure(self):
        """Test deanonymize_text when API returns error."""
        component = AnymizeComponent(anymize_api="test_api_key", operation="deanonymize_text", text="[[Name-abc123]]")

        with patch.object(component, "_deanonymize_text", new_callable=AsyncMock) as mock_deanonymize:
            mock_deanonymize.return_value = {"error": "Invalid hash code"}

            result = await component.process()

            assert isinstance(result, Message)
            assert "Deanonymization failed" in result.text

    @pytest.mark.asyncio
    async def test_file_anonymization_success(self):
        """Test successful file anonymization."""
        mock_file = MagicMock()
        mock_file.path = "/path/to/test.pdf"
        mock_file.name = "test.pdf"

        component = AnymizeComponent(anymize_api="test_api_key", operation="file_anonymization", file=mock_file)

        with (
            patch.object(component, "_anonymize_file", new_callable=AsyncMock) as mock_anonymize_file,
            patch.object(component, "_poll_status", new_callable=AsyncMock) as mock_poll,
        ):
            mock_anonymize_file.return_value = {"job_id": "file_job123"}
            mock_poll.return_value = {"status": "completed", "anonymized_text_raw": "Anonymized content from file"}

            result = await component.process()

            assert isinstance(result, Message)
            assert result.text == "Anonymized content from file"
            mock_anonymize_file.assert_called_once_with(mock_file)
            mock_poll.assert_called_once_with("file_job123")

    @pytest.mark.asyncio
    async def test_file_anonymization_no_file(self):
        """Test file_anonymization operation without file."""
        component = AnymizeComponent(anymize_api="test_api_key", operation="file_anonymization", file=None)

        result = await component.process()

        assert isinstance(result, Message)
        assert result.text == "Error: No file provided for anonymization."

    @pytest.mark.asyncio
    async def test_file_anonymization_string_path(self):
        """Test file anonymization with string path."""
        component = AnymizeComponent(
            anymize_api="test_api_key", operation="file_anonymization", file="/path/to/test.pdf"
        )

        with (
            patch.object(component, "_anonymize_file", new_callable=AsyncMock) as mock_anonymize_file,
            patch.object(component, "_poll_status", new_callable=AsyncMock) as mock_poll,
        ):
            mock_anonymize_file.return_value = {"job_id": "file_job456"}
            mock_poll.return_value = {"status": "completed", "anonymized_text_raw": "File content anonymized"}

            result = await component.process()

            assert isinstance(result, Message)
            assert result.text == "File content anonymized"
            mock_anonymize_file.assert_called_once_with("/path/to/test.pdf")

    @pytest.mark.asyncio
    async def test_file_anonymization_api_error(self):
        """Test file anonymization with API error response."""
        mock_file = MagicMock()
        mock_file.path = "/path/to/test.pdf"
        mock_file.name = "test.pdf"

        component = AnymizeComponent(anymize_api="test_api_key", operation="file_anonymization", file=mock_file)

        # Mock the _anonymize_file method to raise RuntimeError (simulating API error)
        with patch.object(component, "_anonymize_file", new_callable=AsyncMock) as mock_anonymize_file:
            mock_anonymize_file.side_effect = RuntimeError(
                "anymize API error 400 for /api/ocr: Bad Request - Invalid file format"
            )

            result = await component.process()

            assert isinstance(result, Message)
            assert "Error during processing:" in result.text
            assert "anymize API error 400 for /api/ocr: Bad Request - Invalid file format" in result.text

    @pytest.mark.asyncio
    async def test_file_anonymization_timeout(self):
        """Test file anonymization with timeout error."""
        mock_file = MagicMock()
        mock_file.path = "/path/to/test.pdf"
        mock_file.name = "test.pdf"

        component = AnymizeComponent(anymize_api="test_api_key", operation="file_anonymization", file=mock_file)

        # Mock the _anonymize_file method to raise asyncio.TimeoutError
        with patch.object(component, "_anonymize_file", new_callable=AsyncMock) as mock_anonymize_file:
            mock_anonymize_file.side_effect = asyncio.TimeoutError("Request timed out after 300 seconds")

            result = await component.process()

            assert isinstance(result, Message)
            assert "Error during processing:" in result.text
            assert "Request timed out" in result.text

    @pytest.mark.asyncio
    async def test_anonymize_file_http_error_handling(self):
        """Test _anonymize_file method with HTTP error responses."""
        mock_file = MagicMock()
        mock_file.path = "/path/to/test.pdf"
        mock_file.name = "test.pdf"

        component = AnymizeComponent(anymize_api="test_api_key", operation="file_anonymization", file=mock_file)

        # Mock aiohttp components
        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized: Invalid API key")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response

            with patch("builtins.open", mock_open(read_data=b"fake pdf content")):
                with pytest.raises(RuntimeError) as exc_info:
                    await component._anonymize_file(mock_file)

                assert "anymize API error 401 for /api/ocr" in str(exc_info.value)
                assert "Unauthorized: Invalid API key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_anonymize_file_timeout_configuration(self):
        """Test that _anonymize_file configures timeout correctly."""
        mock_file = MagicMock()
        mock_file.path = "/path/to/test.pdf"
        mock_file.name = "test.pdf"

        component = AnymizeComponent(anymize_api="test_api_key", operation="file_anonymization", file=mock_file)

        # Mock aiohttp components
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"job_id": "test123"})

        with patch("aiohttp.ClientSession") as mock_session_class:
            with patch("aiohttp.ClientTimeout") as mock_timeout:
                mock_session = MagicMock()
                mock_session_class.return_value.__aenter__.return_value = mock_session
                mock_session.post.return_value.__aenter__.return_value = mock_response

                with patch("builtins.open", mock_open(read_data=b"fake pdf content")):
                    result = await component._anonymize_file(mock_file)

                # Verify timeout was configured with 300 seconds
                mock_timeout.assert_called_once_with(total=300)
                # Verify session was created with timeout
                mock_session_class.assert_called_once_with(timeout=mock_timeout.return_value)
                assert result == {"job_id": "test123"}

    @pytest.mark.asyncio
    async def test_unknown_operation(self):
        """Test handling of unknown operation."""
        component = AnymizeComponent(anymize_api="test_api_key", operation="invalid_operation", text="Test")

        result = await component.process()

        assert isinstance(result, Message)
        assert "Error: Unknown operation 'invalid_operation'" in result.text

    @pytest.mark.asyncio
    async def test_process_exception_handling(self):
        """Test exception handling in process method."""
        component = AnymizeComponent(anymize_api="test_api_key", operation="anonymize_text", text="Test text")

        with patch.object(component, "_anonymize_text", new_callable=AsyncMock) as mock_anonymize:
            mock_anonymize.side_effect = Exception("API connection failed")

            result = await component.process()

            assert isinstance(result, Message)
            assert "Error during processing: API connection failed" in result.text

    @pytest.mark.asyncio
    async def test_poll_status_success(self):
        """Test successful status polling."""
        component = AnymizeComponent(anymize_api="test_api_key")

        with patch.object(component, "_get_anonymization_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {"status": "completed", "result": "data"}

            result = await component._poll_status("job123")

            assert result == {"status": "completed", "result": "data"}
            mock_status.assert_called_once_with("job123")

    @pytest.mark.asyncio
    async def test_poll_status_timeout(self):
        """Test status polling timeout."""
        component = AnymizeComponent(anymize_api="test_api_key")

        with patch.object(component, "_get_anonymization_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {"status": "processing"}

            with pytest.raises(Exception, match="Anonymization timeout"):
                await component._poll_status("job123", max_retries=2, retry_interval=1)

    @pytest.mark.asyncio
    async def test_anymize_api_request_post(self):
        """Test POST request to anymize API."""
        component = AnymizeComponent(anymize_api="test_api_key")

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"success": True})

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)

        mock_client_session = Mock()
        mock_client_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_client_session):
            result = await component._anymize_api_request("POST", "/api/test", {"data": "test"})

            assert result == {"success": True}
            mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_anymize_api_request_get(self):
        """Test GET request to anymize API."""
        component = AnymizeComponent(anymize_api="test_api_key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ready"})

        mock_get = AsyncMock()
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_get)

        mock_client_session = Mock()
        mock_client_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_client_session) as mock_session_class:
            with patch("aiohttp.ClientTimeout") as mock_timeout:
                result = await component._anymize_api_request("GET", "/api/status/123")

                assert result == {"status": "ready"}
                # Verify timeout was configured with 60 seconds
                mock_timeout.assert_called_once_with(total=60)
                # Verify session was created with timeout
                mock_session_class.assert_called_once_with(timeout=mock_timeout.return_value)
                mock_session.get.assert_called_once_with(
                    "https://app.anymize.ai/api/status/123",
                    headers={
                        "Authorization": "Bearer test_api_key",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    params={},
                )

    @pytest.mark.asyncio
    async def test_anymize_api_request_post(self):
        """Test POST request to anymize API."""
        component = AnymizeComponent(anymize_api="test_api_key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"job_id": "abc123"})

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)

        mock_client_session = Mock()
        mock_client_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_client_session):
            result = await component._anymize_api_request(
                "POST", "/api/anonymize", body={"text": "test"}, qs={"lang": "en"}
            )

            assert result == {"job_id": "abc123"}
            mock_session.post.assert_called_once_with(
                "https://app.anymize.ai/api/anonymize",
                headers={
                    "Authorization": "Bearer test_api_key",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"text": "test"},
                params={"lang": "en"},
            )

    @pytest.mark.asyncio
    async def test_anymize_api_request_http_error(self):
        """Test API request with HTTP error response."""
        component = AnymizeComponent(anymize_api="test_api_key")

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized: Invalid API key provided")

        mock_get = AsyncMock()
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_get)

        mock_client_session = Mock()
        mock_client_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_client_session):
            with pytest.raises(RuntimeError) as exc_info:
                await component._anymize_api_request("GET", "/api/status/123")

            assert "anymize API error 401 for /api/status/123" in str(exc_info.value)
            assert "Unauthorized: Invalid API key provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_anymize_api_request_unsupported_method(self):
        """Test API request with unsupported HTTP method."""
        component = AnymizeComponent(anymize_api="test_api_key")

        with pytest.raises(ValueError) as exc_info:
            await component._anymize_api_request("PATCH", "/api/test")

        assert "Unsupported HTTP method: PATCH" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_anymize_api_request_default_parameters(self):
        """Test API request with default None parameters."""
        component = AnymizeComponent(anymize_api="test_api_key")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "success"})

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)

        mock_client_session = Mock()
        mock_client_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_client_session):
            result = await component._anymize_api_request("POST", "/api/test")

            assert result == {"result": "success"}
            mock_session.post.assert_called_once_with(
                "https://app.anymize.ai/api/test",
                headers={
                    "Authorization": "Bearer test_api_key",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={},  # Empty dict when body=None
                params={},  # Empty dict when qs=None
            )

    @pytest.mark.asyncio
    async def test_anonymize_file_invalid_input(self):
        """Test _anonymize_file with invalid input type."""
        component = AnymizeComponent(anymize_api="test_api_key")

        with pytest.raises(TypeError, match="file_input must be a path string"):
            await component._anonymize_file(123)  # Invalid type

    def test_component_metadata(self):
        """Test component metadata attributes."""
        component = AnymizeComponent()

        assert component.display_name == "anymize"
        assert component.name == "anymize"
        assert component.icon == "eye-off"
        assert component.priority == 100
        assert "GDPR-compliant" in component.description
        assert component.documentation == "https://explore.anymize.ai/api-docs"

    def test_component_inputs_configuration(self):
        """Test that component inputs are properly configured."""
        component = AnymizeComponent()

        # Check that inputs are defined
        assert hasattr(component, "inputs")
        assert len(component.inputs) == 5

        # Check specific input configurations
        input_names = [inp.name for inp in component.inputs]
        assert "anymize_api" in input_names
        assert "operation" in input_names
        assert "text" in input_names
        assert "file" in input_names
        assert "language" in input_names

    def test_component_outputs_configuration(self):
        """Test that component outputs are properly configured."""
        component = AnymizeComponent()

        assert hasattr(component, "outputs")
        assert len(component.outputs) == 1
        assert component.outputs[0].name == "process"
        assert component.outputs[0].display_name == "Process"
