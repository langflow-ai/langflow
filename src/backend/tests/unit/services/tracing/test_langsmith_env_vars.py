"""Tests to verify LangSmith tracing configuration, fallback, and precedence.

These tests verify that LangSmithTracer and TracingService handle environment
variables (like LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_TRACING) in
accordance with precedence and fallback behavior.
"""

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from langflow.services.tracing.langsmith import LangSmithTracer
from langflow.services.tracing.service import (
    TracingService,
    trace_context_var,
)
from lfx.services.settings.base import Settings
from lfx.services.settings.service import SettingsService


@pytest.fixture
def mock_settings_service():
    """Create a mock settings service for TracingService initialization."""
    settings = Settings()
    settings.deactivate_tracing = False
    return SettingsService(settings, MagicMock())


@pytest.fixture
def tracing_service(mock_settings_service):
    """Initialize TracingService with mock settings."""
    return TracingService(mock_settings_service)


@pytest.fixture
def stop_tracer_initialization():
    """Mock TracingService._start to raise an exception, preventing tracer initialization."""
    with patch.object(TracingService, "_start", side_effect=RuntimeError("Stop initialization")):
        yield


@pytest.fixture
def clear_trace_context():
    """Ensure trace_context_var is cleared even if a test assertion fails."""
    yield
    trace_context_var.set(None)


class TestLangSmithConfiguration:
    """Verify setup_langsmith environment variable precedence and tracing injection."""

    @pytest.fixture
    def mock_tracer(self):
        """Fixture providing an uninitialized LangSmithTracer.

        Consider changing setup_langsmith to a @staticmethod if it doesn't use self.
        """
        return LangSmithTracer.__new__(LangSmithTracer)

    def test_setup_langsmith_no_keys(self, mock_tracer):
        """Verify setup_langsmith returns False when no API keys are present in the environment."""
        with patch.dict(os.environ, {}, clear=True):
            assert mock_tracer.setup_langsmith() is False

    def test_setup_langsmith_with_langsmith_key(self, mock_tracer):
        """Verify setup_langsmith succeeds and injects variables when only LANGSMITH_API_KEY is present."""
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": "smith-key"}, clear=True), patch(
            "langsmith.Client", MagicMock()
        ):
            assert mock_tracer.setup_langsmith() is True
            assert os.environ.get("LANGSMITH_TRACING") == "true"
            assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"

    def test_setup_langsmith_with_langchain_key_fallback(self, mock_tracer):
        """Verify setup_langsmith succeeds and injects variables when only LANGCHAIN_API_KEY is present."""
        with patch.dict(os.environ, {"LANGCHAIN_API_KEY": "chain-key"}, clear=True), patch(
            "langsmith.Client", MagicMock()
        ):
            assert mock_tracer.setup_langsmith() is True
            assert os.environ.get("LANGSMITH_TRACING") == "true"
            assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"

    def test_setup_langsmith_api_key_precedence(self, mock_tracer):
        """Verify setup_langsmith gives precedence to LANGSMITH_API_KEY when both keys are present."""
        with patch.dict(
            os.environ,
            {"LANGSMITH_API_KEY": "smith-priority-key", "LANGCHAIN_API_KEY": "chain-fallback-key"},
            clear=True,
        ), patch("langsmith.Client", MagicMock()):
            assert mock_tracer.setup_langsmith() is True
            assert os.getenv("LANGSMITH_API_KEY") == "smith-priority-key"


class TestTracingServiceProjectName:
    """Verify TracingService resolves LANGSMITH_PROJECT with fallback to LANGCHAIN_PROJECT."""

    def test_tracing_service_project_name_deactivated_defaults(self, mock_settings_service):
        """Verify TracingService project_name defaults to 'Langflow' when tracing is deactivated and env is empty."""
        mock_settings_service.settings.deactivate_tracing = True
        ts = TracingService(mock_settings_service)
        with patch.dict(os.environ, {}, clear=True):
            assert ts.project_name == "Langflow"

    def test_tracing_service_project_name_deactivated_langchain_fallback(self, mock_settings_service):
        """Verify TracingService project_name falls back to LANGCHAIN_PROJECT when tracing is deactivated."""
        mock_settings_service.settings.deactivate_tracing = True
        ts = TracingService(mock_settings_service)
        with patch.dict(os.environ, {"LANGCHAIN_PROJECT": "fallback-project"}, clear=True):
            assert ts.project_name == "fallback-project"

    def test_tracing_service_project_name_deactivated_langsmith_priority(self, mock_settings_service):
        """Verify TracingService project_name prioritizes LANGSMITH_PROJECT over LANGCHAIN_PROJECT."""
        mock_settings_service.settings.deactivate_tracing = True
        ts = TracingService(mock_settings_service)
        with patch.dict(
            os.environ, {"LANGSMITH_PROJECT": "smith-project", "LANGCHAIN_PROJECT": "chain-project"}, clear=True
        ):
            assert ts.project_name == "smith-project"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("stop_tracer_initialization", "clear_trace_context")
    async def test_start_tracers_project_name_defaults(self, tracing_service):
        """Verify start_tracers sets project_name to 'Langflow' by default when tracing is active."""
        run_id = uuid.uuid4()
        with patch.dict(os.environ, {}, clear=True):
            await tracing_service.start_tracers(run_id, "test_run", "test_user", "test_session", project_name=None)
            assert tracing_service.project_name == "Langflow"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("stop_tracer_initialization", "clear_trace_context")
    async def test_start_tracers_project_name_langchain_fallback(self, tracing_service):
        """Verify start_tracers sets project_name to LANGCHAIN_PROJECT when active."""
        run_id = uuid.uuid4()
        with patch.dict(os.environ, {"LANGCHAIN_PROJECT": "fallback-project"}, clear=True):
            await tracing_service.start_tracers(run_id, "test_run", "test_user", "test_session", project_name=None)
            assert tracing_service.project_name == "fallback-project"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("stop_tracer_initialization", "clear_trace_context")
    async def test_start_tracers_project_name_langsmith_priority(self, tracing_service):
        """Verify start_tracers prioritizes LANGSMITH_PROJECT over LANGCHAIN_PROJECT when active."""
        run_id = uuid.uuid4()
        with patch.dict(
            os.environ, {"LANGSMITH_PROJECT": "smith-project", "LANGCHAIN_PROJECT": "chain-project"}, clear=True
        ):
            await tracing_service.start_tracers(run_id, "test_run", "test_user", "test_session", project_name=None)
            assert tracing_service.project_name == "smith-project"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("stop_tracer_initialization", "clear_trace_context")
    async def test_start_tracers_project_name_explicit_param(self, tracing_service):
        """Verify start_tracers explicit parameter overrides all environment variables."""
        run_id = uuid.uuid4()
        with patch.dict(os.environ, {"LANGSMITH_PROJECT": "smith-project"}, clear=True):
            await tracing_service.start_tracers(
                run_id, "test_run", "test_user", "test_session", project_name="explicit-project"
            )
            assert tracing_service.project_name == "explicit-project"
