"""Unit tests for NoveumTracer."""

import os
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from langflow.services.tracing.noveum_trace import NoveumTracer


@pytest.fixture
def sample_trace_id():
    """Generate a sample trace ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def sample_trace_name():
    """Sample trace name for testing."""
    return "Test Flow - flow_123"


@pytest.fixture
def sample_config():
    """Sample configuration dict for testing."""
    return {
        "api_key": "test_api_key",
        "project": "test_project",
        "environment": "test_environment",
        "endpoint": "https://test.endpoint.com",
    }


@pytest.fixture
def mock_noveum_modules():
    """Mock all noveum_trace imports."""
    mock_client_class = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_class.return_value = mock_client_instance

    mock_trace = MagicMock()
    mock_trace.trace_id = "test_trace_id"
    mock_client_instance.start_trace.return_value = mock_trace

    mock_callback_handler = MagicMock()
    mock_register_client = MagicMock()
    mock_set_current_trace = MagicMock()

    mock_noveum_module = MagicMock()
    mock_noveum_module._client = None
    mock_noveum_module._client_lock = MagicMock()

    with (
        patch("langflow.services.tracing.noveum_trace.noveum_trace", mock_noveum_module),
        patch("langflow.services.tracing.noveum_trace.NoveumClient", mock_client_class),
        patch("langflow.services.tracing.noveum_trace._register_client", mock_register_client),
        patch("langflow.services.tracing.noveum_trace.set_current_trace", mock_set_current_trace),
        patch("langflow.services.tracing.noveum_trace.NoveumTraceCallbackHandler", return_value=mock_callback_handler),
    ):
        yield {
            "client_class": mock_client_class,
            "client_instance": mock_client_instance,
            "trace": mock_trace,
            "callback_handler": mock_callback_handler,
            "register_client": mock_register_client,
            "set_current_trace": mock_set_current_trace,
            "noveum_module": mock_noveum_module,
        }


@pytest.fixture
def mock_span():
    """Mock span object with required methods."""
    span = MagicMock()
    span.span_id = "test_span_id"
    span.set_attributes = MagicMock()
    span.set_status = MagicMock()
    span.finish = MagicMock()
    return span


class TestNoveumTracerInit:
    """Test NoveumTracer initialization."""

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_init_successful_with_config(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test successful initialization with valid config."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        assert tracer.trace_name == sample_trace_name
        assert tracer.trace_type == "chain"
        assert tracer.project_name == "test_project"
        assert tracer.trace_id == sample_trace_id
        assert tracer.flow_id == "flow_123"
        assert isinstance(tracer.spans, OrderedDict)
        assert tracer._ready is True

    @patch.dict(os.environ, {}, clear=True)
    def test_init_without_config(self, sample_trace_id, sample_trace_name):
        """Test initialization without config."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        assert tracer._ready is False
        assert tracer.flow_id == "flow_123"

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_init_with_user_id_and_session_id(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test initialization with user_id and session_id."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
            user_id="user_123",
            session_id="session_456",
        )

        assert tracer.user_id == "user_123"
        assert tracer.session_id == "session_456"
        assert tracer._ready is True


class TestNoveumTracerGetConfig:
    """Test _get_config method."""

    def test_get_config_all_env_vars_present(self, sample_trace_id, sample_trace_name):
        """Test _get_config with all environment variables present."""
        with patch.dict(
            os.environ,
            {
                "NOVEUM_API_KEY": "test_key",
                "NOVEUM_PROJECT": "test_project",
                "NOVEUM_ENVIRONMENT": "test_env",
                "NOVEUM_ENDPOINT": "https://test.endpoint.com",
            },
        ):
            tracer = NoveumTracer(
                trace_name=sample_trace_name,
                trace_type="chain",
                project_name="test_project",
                trace_id=sample_trace_id,
            )
            config = tracer._get_config()

            assert config["api_key"] == "test_key"
            assert config["project"] == "test_project"
            assert config["environment"] == "test_env"
            assert config["endpoint"] == "https://test.endpoint.com"

    def test_get_config_missing_api_key(self, sample_trace_id, sample_trace_name):
        """Test _get_config with missing NOVEUM_API_KEY."""
        with patch.dict(os.environ, {"NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"}, clear=True):
            tracer = NoveumTracer(
                trace_name=sample_trace_name,
                trace_type="chain",
                project_name="test_project",
                trace_id=sample_trace_id,
            )
            config = tracer._get_config()

            assert config == {}

    def test_get_config_missing_environment(self, sample_trace_id, sample_trace_name):
        """Test _get_config with missing NOVEUM_ENVIRONMENT."""
        with patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project"}, clear=True):
            tracer = NoveumTracer(
                trace_name=sample_trace_name,
                trace_type="chain",
                project_name="test_project",
                trace_id=sample_trace_id,
            )
            config = tracer._get_config()

            assert config == {}

    def test_get_config_project_fallback(self, sample_trace_id, sample_trace_name):
        """Test _get_config project fallback to instance parameter."""
        with patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_ENVIRONMENT": "test_env"}, clear=True):
            tracer = NoveumTracer(
                trace_name=sample_trace_name,
                trace_type="chain",
                project_name="fallback_project",
                trace_id=sample_trace_id,
            )
            config = tracer._get_config()

            assert config["project"] == "fallback_project"

    def test_get_config_endpoint_optional(self, sample_trace_id, sample_trace_name):
        """Test _get_config with optional endpoint."""
        with patch.dict(
            os.environ,
            {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"},
            clear=True,
        ):
            tracer = NoveumTracer(
                trace_name=sample_trace_name,
                trace_type="chain",
                project_name="test_project",
                trace_id=sample_trace_id,
            )
            config = tracer._get_config()

            assert "endpoint" not in config
            assert config["api_key"] == "test_key"
            assert config["project"] == "test_project"
            assert config["environment"] == "test_env"


class TestNoveumTracerSetupNoveum:
    """Test setup_noveum method."""

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_setup_noveum_successful(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test successful setup_noveum."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_client_class = mock_noveum_modules["client_class"]
        mock_client_instance = mock_noveum_modules["client_instance"]
        mock_register_client = mock_noveum_modules["register_client"]
        mock_set_current_trace = mock_noveum_modules["set_current_trace"]
        mock_noveum_module = mock_noveum_modules["noveum_module"]

        assert tracer._ready is True
        mock_client_class.assert_called_once_with(
            api_key="test_key",
            project="test_project",
            environment="test_env",
            endpoint=None,
        )
        mock_register_client.assert_called_once_with(mock_client_instance)
        mock_set_current_trace.assert_called_once()
        mock_client_instance.start_trace.assert_called_once()
        assert mock_noveum_module._client == mock_client_instance

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_setup_noveum_with_user_id_and_session_id(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test setup_noveum with user_id and session_id."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
            user_id="user_123",
            session_id="session_456",
        )

        mock_client_instance = mock_noveum_modules["client_instance"]
        call_args = mock_client_instance.start_trace.call_args

        assert call_args is not None
        attributes = call_args[1]["attributes"]
        assert attributes["user_id"] == "user_123"
        assert attributes["session_id"] == "session_456"
        assert attributes["trace_type"] == "chain"
        assert attributes["flow_id"] == "flow_123"

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_setup_noveum_without_user_id_and_session_id(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test setup_noveum without user_id and session_id."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_client_instance = mock_noveum_modules["client_instance"]
        call_args = mock_client_instance.start_trace.call_args

        assert call_args is not None
        attributes = call_args[1]["attributes"]
        assert "user_id" not in attributes
        assert "session_id" not in attributes
        assert attributes["trace_type"] == "chain"
        assert attributes["flow_id"] == "flow_123"

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_setup_noveum_import_error(self, sample_trace_id, sample_trace_name):
        """Test setup_noveum with ImportError."""
        with patch("langflow.services.tracing.noveum_trace.noveum_trace", None):
            with patch("langflow.services.tracing.noveum_trace.logger") as mock_logger:
                tracer = NoveumTracer(
                    trace_name=sample_trace_name,
                    trace_type="chain",
                    project_name="test_project",
                    trace_id=sample_trace_id,
                )

                assert tracer._ready is False
                mock_logger.exception.assert_called()

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_setup_noveum_general_exception(self, sample_trace_id, sample_trace_name):
        """Test setup_noveum with general exception."""
        with patch("langflow.services.tracing.noveum_trace.NoveumClient", side_effect=Exception("Test error")):
            with patch("langflow.services.tracing.noveum_trace.logger") as mock_logger:
                tracer = NoveumTracer(
                    trace_name=sample_trace_name,
                    trace_type="chain",
                    project_name="test_project",
                    trace_id=sample_trace_id,
                )

                assert tracer._ready is False
                mock_logger.debug.assert_called()

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_setup_noveum_with_client_lock(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test setup_noveum with _client_lock attribute."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_noveum_module = mock_noveum_modules["noveum_module"]
        assert hasattr(mock_noveum_module, "_client_lock")
        assert mock_noveum_module._client is not None

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_setup_noveum_without_client_lock(self, sample_trace_id, sample_trace_name):
        """Test setup_noveum without _client_lock attribute (fallback path)."""
        mock_noveum_module = MagicMock()
        mock_noveum_module._client = None
        # Don't set _client_lock

        mock_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_trace = MagicMock()
        mock_client_instance.start_trace.return_value = mock_trace
        mock_client_class.return_value = mock_client_instance

        with (
            patch("langflow.services.tracing.noveum_trace.noveum_trace", mock_noveum_module),
            patch("langflow.services.tracing.noveum_trace.NoveumClient", mock_client_class),
            patch("langflow.services.tracing.noveum_trace._register_client", MagicMock()),
            patch("langflow.services.tracing.noveum_trace.set_current_trace", MagicMock()),
            patch("langflow.services.tracing.noveum_trace.NoveumTraceCallbackHandler", return_value=MagicMock()),
        ):
            tracer = NoveumTracer(
                trace_name=sample_trace_name,
                trace_type="chain",
                project_name="test_project",
                trace_id=sample_trace_id,
            )

            assert tracer._ready is True
            assert mock_noveum_module._client == mock_client_instance


class TestNoveumTracerAddTrace:
    """Test add_trace method."""

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_add_trace_successful(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test successful span creation."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_trace = mock_noveum_modules["trace"]
        mock_span = MagicMock()
        mock_span.span_id = "test_span_id"
        mock_trace.create_span.return_value = mock_span

        inputs = {"input_key": "input_value"}
        metadata = {"custom_meta": "value"}

        tracer.add_trace(
            trace_id="component_123",
            trace_name="Test Component (component_123)",
            trace_type="component",
            inputs=inputs,
            metadata=metadata,
        )

        assert "component_123" in tracer.spans
        assert tracer.spans["component_123"] == mock_span
        mock_trace.create_span.assert_called_once()
        call_kwargs = mock_trace.create_span.call_args[1]
        assert call_kwargs["name"] == "Test Component"
        assert call_kwargs["attributes"]["from_langflow_component"] is True
        assert call_kwargs["attributes"]["component_id"] == "component_123"
        assert call_kwargs["attributes"]["trace_type"] == "component"
        assert call_kwargs["attributes"]["custom_meta"] == "value"
        assert "inputs" in call_kwargs["attributes"]

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_add_trace_not_ready(self, sample_trace_id, sample_trace_name):
        """Test add_trace when tracer is not ready."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )
        tracer._ready = False

        tracer.add_trace(
            trace_id="component_123",
            trace_name="Test Component (component_123)",
            trace_type="component",
            inputs={},
        )

        assert len(tracer.spans) == 0

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_add_trace_name_cleanup(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test name cleanup in add_trace."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_trace = mock_noveum_modules["trace"]
        mock_span = MagicMock()
        mock_trace.create_span.return_value = mock_span

        # Test with ID suffix
        tracer.add_trace(
            trace_id="comp_123",
            trace_name="My Component (comp_123)",
            trace_type="component",
            inputs={},
        )

        call_kwargs = mock_trace.create_span.call_args[1]
        assert call_kwargs["name"] == "My Component"

        # Test without ID suffix
        tracer.add_trace(
            trace_id="comp_456",
            trace_name="My Component",
            trace_type="component",
            inputs={},
        )

        call_kwargs = mock_trace.create_span.call_args[1]
        assert call_kwargs["name"] == "My Component"

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_add_trace_metadata_merging(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test metadata merging in add_trace."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_trace = mock_noveum_modules["trace"]
        mock_span = MagicMock()
        mock_trace.create_span.return_value = mock_span

        tracer.add_trace(
            trace_id="component_123",
            trace_name="Test Component (component_123)",
            trace_type="custom_type",
            inputs={},
            metadata={"custom_key": "custom_value"},
        )

        call_kwargs = mock_trace.create_span.call_args[1]
        attributes = call_kwargs["attributes"]
        assert attributes["from_langflow_component"] is True
        assert attributes["component_id"] == "component_123"
        assert attributes["trace_type"] == "custom_type"
        assert attributes["custom_key"] == "custom_value"

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_add_trace_input_serialization(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test input serialization in add_trace."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_trace = mock_noveum_modules["trace"]
        mock_span = MagicMock()
        mock_trace.create_span.return_value = mock_span

        with patch("langflow.services.tracing.noveum_trace.serialize") as mock_serialize:
            mock_serialize.return_value = {"serialized": "inputs"}
            inputs = {"input_key": "input_value"}

            tracer.add_trace(
                trace_id="component_123",
                trace_name="Test Component (component_123)",
                trace_type="component",
                inputs=inputs,
            )

            mock_serialize.assert_called_once_with(inputs)
            call_kwargs = mock_trace.create_span.call_args[1]
            assert call_kwargs["attributes"]["inputs"] == {"serialized": "inputs"}

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_add_trace_exception_handling(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test exception handling in add_trace."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_trace = mock_noveum_modules["trace"]
        mock_trace.create_span.side_effect = Exception("Test error")

        with patch("langflow.services.tracing.noveum_trace.logger") as mock_logger:
            tracer.add_trace(
                trace_id="component_123",
                trace_name="Test Component (component_123)",
                trace_type="component",
                inputs={},
            )

            mock_logger.debug.assert_called()
            assert "component_123" not in tracer.spans


class TestNoveumTracerEndTrace:
    """Test end_trace method."""

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_trace_successful(self, mock_noveum_modules, sample_trace_id, sample_trace_name, mock_span):
        """Test successful span finishing."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        tracer.spans["component_123"] = mock_span

        outputs = {"output_key": "output_value"}
        end_time = datetime.now(tz=timezone.utc)

        with patch("langflow.services.tracing.noveum_trace.datetime") as mock_datetime:
            mock_datetime.now.return_value = end_time
            tracer.end_trace(
                trace_id="component_123",
                trace_name="Test Component",
                outputs=outputs,
            )

        assert "component_123" not in tracer.spans
        mock_span.set_attributes.assert_called_once()
        mock_span.finish.assert_called_once_with(end_time=end_time)

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_trace_not_ready(self, sample_trace_id, sample_trace_name):
        """Test end_trace when tracer is not ready."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )
        tracer._ready = False
        tracer.spans["component_123"] = MagicMock()

        tracer.end_trace(
            trace_id="component_123",
            trace_name="Test Component",
            outputs={},
        )

        assert "component_123" in tracer.spans

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_trace_missing_span(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test end_trace with missing span."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        with patch("langflow.services.tracing.noveum_trace.logger") as mock_logger:
            tracer.end_trace(
                trace_id="nonexistent_component",
                trace_name="Test Component",
                outputs={},
            )

            mock_logger.debug.assert_called()
            assert "nonexistent_component" not in tracer.spans

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_trace_with_outputs(self, mock_noveum_modules, sample_trace_id, sample_trace_name, mock_span):
        """Test end_trace with outputs."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        tracer.spans["component_123"] = mock_span

        with patch("langflow.services.tracing.noveum_trace.serialize") as mock_serialize:
            mock_serialize.return_value = {"serialized": "outputs"}
            outputs = {"output_key": "output_value"}

            tracer.end_trace(
                trace_id="component_123",
                trace_name="Test Component",
                outputs=outputs,
            )

            mock_serialize.assert_called_once_with(outputs)
            call_kwargs = mock_span.set_attributes.call_args[0][0]
            assert call_kwargs["outputs"]["serialized"] == "outputs"

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_trace_with_error(self, mock_noveum_modules, sample_trace_id, sample_trace_name, mock_span):
        """Test end_trace with error."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        tracer.spans["component_123"] = mock_span
        error = ValueError("Test error")

        tracer.end_trace(
            trace_id="component_123",
            trace_name="Test Component",
            outputs={},
            error=error,
        )

        call_kwargs = mock_span.set_attributes.call_args[0][0]
        assert call_kwargs["outputs"]["error"] == "Test error"
        mock_span.set_status.assert_called_once_with("error", "Test error")

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_trace_with_logs(self, mock_noveum_modules, sample_trace_id, sample_trace_name, mock_span):
        """Test end_trace with logs."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        tracer.spans["component_123"] = mock_span

        logs = [{"log_key": "log_value"}, {"another_log": "value"}]

        with patch("langflow.services.tracing.noveum_trace.serialize") as mock_serialize:
            mock_serialize.side_effect = lambda x: {"serialized": str(x)}

            tracer.end_trace(
                trace_id="component_123",
                trace_name="Test Component",
                outputs={},
                logs=logs,
            )

            call_kwargs = mock_span.set_attributes.call_args[0][0]
            assert "logs" in call_kwargs["outputs"]
            assert len(call_kwargs["outputs"]["logs"]) == 2

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_trace_exception_handling(self, mock_noveum_modules, sample_trace_id, sample_trace_name, mock_span):
        """Test exception handling in end_trace."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        tracer.spans["component_123"] = mock_span
        mock_span.finish.side_effect = Exception("Test error")

        with patch("langflow.services.tracing.noveum_trace.logger") as mock_logger:
            tracer.end_trace(
                trace_id="component_123",
                trace_name="Test Component",
                outputs={},
            )

            mock_logger.debug.assert_called()
            assert "component_123" not in tracer.spans  # Should still be removed


class TestNoveumTracerEnd:
    """Test end method."""

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_successful(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test successful trace finalization."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_client_instance = mock_noveum_modules["client_instance"]
        mock_trace = mock_noveum_modules["trace"]
        mock_client_instance.flush = MagicMock()

        inputs = {"input_key": "input_value"}
        outputs = {"output_key": "output_value"}
        metadata = {"meta_key": "meta_value"}

        tracer.end(inputs=inputs, outputs=outputs, metadata=metadata)

        mock_trace.set_attributes.assert_called_once()
        call_kwargs = mock_trace.set_attributes.call_args[0][0]
        assert "final_inputs" in call_kwargs
        assert "final_outputs" in call_kwargs
        assert "final_metadata" in call_kwargs
        mock_client_instance.finish_trace.assert_called_once_with(mock_trace)
        mock_client_instance.flush.assert_called_once()
        mock_client_instance.shutdown.assert_called_once()

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_not_ready(self, sample_trace_id, sample_trace_name):
        """Test end when tracer is not ready."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )
        tracer._ready = False

        tracer.end(inputs={}, outputs={})

        # Should return early without doing anything

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_with_error(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test end with error."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_trace = mock_noveum_modules["trace"]
        error = ValueError("Test error")

        tracer.end(inputs={}, outputs={}, error=error)

        call_kwargs = mock_trace.set_attributes.call_args[0][0]
        assert call_kwargs["error"] == "Test error"
        mock_trace.set_status.assert_called_once_with("error", "Test error")

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_without_inputs_outputs_metadata(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test end without inputs/outputs/metadata."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_client_instance = mock_noveum_modules["client_instance"]
        mock_trace = mock_noveum_modules["trace"]
        mock_client_instance.flush = MagicMock()

        tracer.end(inputs=None, outputs=None, metadata=None)

        # When all inputs/outputs/metadata are None, trace_attributes is empty
        # so set_attributes should NOT be called
        mock_trace.set_attributes.assert_not_called()
        # But finish_trace should still be called
        mock_client_instance.finish_trace.assert_called_once()

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_flush_handling(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test end flush handling."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_client_instance = mock_noveum_modules["client_instance"]
        mock_client_instance.flush = MagicMock()

        tracer.end(inputs={}, outputs={})

        mock_client_instance.flush.assert_called_once()

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_without_flush(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test end when flush method doesn't exist."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_client_instance = mock_noveum_modules["client_instance"]
        del mock_client_instance.flush  # Remove flush method

        # Should not crash
        tracer.end(inputs={}, outputs={})

        mock_client_instance.finish_trace.assert_called_once()

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_shutdown_exception_handling(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test end shutdown exception handling."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_client_instance = mock_noveum_modules["client_instance"]
        mock_client_instance.flush = MagicMock()
        mock_client_instance.shutdown.side_effect = Exception("Shutdown error")

        with patch("langflow.services.tracing.noveum_trace.logger") as mock_logger:
            tracer.end(inputs={}, outputs={})

            mock_logger.debug.assert_called()
            mock_client_instance.finish_trace.assert_called_once()  # Should still be called

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_end_general_exception_handling(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test end general exception handling."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        mock_trace = mock_noveum_modules["trace"]
        mock_trace.set_attributes.side_effect = Exception("Test error")

        with patch("langflow.services.tracing.noveum_trace.logger") as mock_logger:
            tracer.end(inputs={}, outputs={})

            mock_logger.debug.assert_called()


class TestNoveumTracerGetLangchainCallback:
    """Test get_langchain_callback method."""

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_get_langchain_callback_when_ready(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test get_langchain_callback when ready."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        callback = tracer.get_langchain_callback()

        assert callback is not None
        assert callback == mock_noveum_modules["callback_handler"]

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_get_langchain_callback_when_not_ready(self, sample_trace_id, sample_trace_name):
        """Test get_langchain_callback when not ready."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )
        tracer._ready = False

        callback = tracer.get_langchain_callback()

        assert callback is None


class TestNoveumTracerReadyProperty:
    """Test ready property."""

    @patch.dict(os.environ, {"NOVEUM_API_KEY": "test_key", "NOVEUM_PROJECT": "test_project", "NOVEUM_ENVIRONMENT": "test_env"})
    def test_ready_property_true(self, mock_noveum_modules, sample_trace_id, sample_trace_name):
        """Test ready property returns True when _ready is True."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        assert tracer.ready is True

    @patch.dict(os.environ, {}, clear=True)
    def test_ready_property_false(self, sample_trace_id, sample_trace_name):
        """Test ready property returns False when _ready is False."""
        tracer = NoveumTracer(
            trace_name=sample_trace_name,
            trace_type="chain",
            project_name="test_project",
            trace_id=sample_trace_id,
        )

        assert tracer.ready is False
