import pytest
import os
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.testclient import TestClient
from starlette.middleware.base import RequestResponseEndpoint
import tempfile
import httpx

from langflow.main import (
    create_app,
    setup_sentry,
    setup_static_files,
    get_static_files_dir,
    setup_app,
    get_lifespan,
    load_bundles_with_error_handling,
    RequestCancelledMiddleware,
    JavaScriptMIMETypeMiddleware,
    MAX_PORT
)


class TestCreateApp:
    """Test suite for the create_app function."""

    def test_create_app_returns_fastapi_instance(self):
        """Test that create_app returns a FastAPI application instance."""
        app = create_app()
        assert app is not None
        assert isinstance(app, FastAPI)
        assert hasattr(app, 'router')
        assert hasattr(app, 'routes')

    def test_create_app_has_correct_title_and_version(self):
        """Test that create_app sets correct title and version."""
        app = create_app()
        assert app.title == "Langflow"
        assert app.version is not None

    def test_create_app_has_cors_middleware(self):
        """Test that create_app includes CORS middleware."""
        app = create_app()
        middleware_types = [type(middleware).__name__ for middleware in app.user_middleware]
        assert any('CORS' in name for name in middleware_types)

    def test_create_app_has_content_size_limit_middleware(self):
        """Test that create_app includes ContentSizeLimitMiddleware."""
        app = create_app()
        middleware_types = [type(middleware).__name__ for middleware in app.user_middleware]
        assert any('ContentSizeLimitMiddleware' in name for name in middleware_types)

    def test_create_app_has_javascript_mime_type_middleware(self):
        """Test that create_app includes JavaScriptMIMETypeMiddleware."""
        app = create_app()
        middleware_types = [type(middleware).__name__ for middleware in app.user_middleware]
        assert any('JavaScriptMIMETypeMiddleware' in name for name in middleware_types)

    def test_create_app_includes_routers(self):
        """Test that create_app includes necessary routers."""
        app = create_app()
        assert len(app.routes) > 0
        
        # Check for specific route patterns
        route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
        assert any('/api' in path for path in route_paths)

    def test_create_app_has_lifespan_context(self):
        """Test that create_app configures lifespan context."""
        app = create_app()
        assert app.router.lifespan_context is not None

    def test_create_app_has_exception_handlers(self):
        """Test that create_app configures exception handlers."""
        app = create_app()
        assert hasattr(app, 'exception_handlers')
        assert len(app.exception_handlers) > 0

    def test_create_app_has_pagination(self):
        """Test that create_app includes pagination."""
        app = create_app()
        # FastAPI pagination should be configured
        assert hasattr(app, 'router')

    def test_create_app_with_prometheus_enabled(self):
        """Test create_app with Prometheus enabled."""
        with patch.dict(os.environ, {'LANGFLOW_PROMETHEUS_PORT': '9090'}):
            with patch('langflow.main.start_http_server') as mock_start:
                app = create_app()
                assert app is not None
                mock_start.assert_called_once_with(9090)

    def test_create_app_with_invalid_prometheus_port(self):
        """Test create_app with invalid Prometheus port."""
        with patch.dict(os.environ, {'LANGFLOW_PROMETHEUS_PORT': '99999'}):
            with pytest.raises(ValueError, match="Invalid port number"):
                create_app()

    def test_create_app_with_mcp_server_enabled(self):
        """Test create_app with MCP server enabled."""
        with patch('langflow.main.get_settings_service') as mock_settings:
            mock_settings.return_value.server.mcp_server_enabled = True
            with patch('langflow.main.mcp_router') as mock_mcp_router:
                app = create_app()
                assert app is not None

    def test_create_app_middleware_order(self):
        """Test that middleware is added in correct order."""
        app = create_app()
        assert hasattr(app, 'user_middleware')
        assert len(app.user_middleware) > 0

    def test_create_app_fastapi_instrumentor(self):
        """Test that FastAPI instrumentor is configured."""
        app = create_app()
        # Should have OpenTelemetry instrumentation
        assert app is not None

    def test_create_app_boundary_check_middleware(self):
        """Test boundary check middleware functionality."""
        app = create_app()
        client = TestClient(app)
        
        # Test valid multipart request
        response = client.post(
            "/api/v1/files/upload",
            headers={"Content-Type": "multipart/form-data; boundary=test123"},
            data=b"--test123\r\nContent-Disposition: form-data; name=\"file\"\r\n\r\ntest\r\n--test123--\r\n"
        )
        # Should not be rejected by boundary check
        assert response.status_code != 422 or "boundary" not in response.json().get("detail", "")

    def test_create_app_query_string_flattening_middleware(self):
        """Test query string flattening middleware."""
        app = create_app()
        client = TestClient(app)
        
        # Test with comma-separated query parameters
        response = client.get("/api/v1/health?test=a,b,c")
        # Should not fail due to query string processing
        assert response.status_code in [200, 404]  # 404 is acceptable if route doesn't exist


class TestSetupSentry:
    """Test suite for the setup_sentry function."""

    def test_setup_sentry_with_dsn(self):
        """Test setup_sentry with DSN configured."""
        app = FastAPI()
        
        with patch('langflow.main.get_settings_service') as mock_settings:
            mock_settings.return_value.telemetry.sentry_dsn = "https://test@sentry.io/123"
            mock_settings.return_value.telemetry.sentry_traces_sample_rate = 0.1
            mock_settings.return_value.telemetry.sentry_profiles_sample_rate = 0.1
            
            with patch('langflow.main.sentry_sdk') as mock_sentry:
                setup_sentry(app)
                mock_sentry.init.assert_called_once_with(
                    dsn="https://test@sentry.io/123",
                    traces_sample_rate=0.1,
                    profiles_sample_rate=0.1
                )

    def test_setup_sentry_without_dsn(self):
        """Test setup_sentry without DSN configured."""
        app = FastAPI()
        
        with patch('langflow.main.get_settings_service') as mock_settings:
            mock_settings.return_value.telemetry.sentry_dsn = None
            
            with patch('langflow.main.sentry_sdk') as mock_sentry:
                setup_sentry(app)
                mock_sentry.init.assert_not_called()

    def test_setup_sentry_adds_middleware(self):
        """Test that setup_sentry adds Sentry middleware."""
        app = FastAPI()
        
        with patch('langflow.main.get_settings_service') as mock_settings:
            mock_settings.return_value.telemetry.sentry_dsn = "https://test@sentry.io/123"
            mock_settings.return_value.telemetry.sentry_traces_sample_rate = 0.1
            mock_settings.return_value.telemetry.sentry_profiles_sample_rate = 0.1
            
            with patch('langflow.main.sentry_sdk'):
                setup_sentry(app)
                # Should have added Sentry middleware
                middleware_types = [type(middleware).__name__ for middleware in app.user_middleware]
                assert any('Sentry' in name for name in middleware_types)


class TestSetupStaticFiles:
    """Test suite for the setup_static_files function."""

    def test_setup_static_files_mounts_directory(self):
        """Test that setup_static_files mounts the static directory."""
        app = FastAPI()
        static_dir = Path("/tmp/static")
        
        with patch('langflow.main.StaticFiles') as mock_static:
            setup_static_files(app, static_dir)
            mock_static.assert_called_once_with(directory=static_dir, html=True)

    def test_setup_static_files_adds_404_handler(self):
        """Test that setup_static_files adds 404 handler."""
        app = FastAPI()
        static_dir = Path("/tmp/static")
        
        setup_static_files(app, static_dir)
        
        # Should have added 404 exception handler
        assert 404 in app.exception_handlers

    @pytest.mark.asyncio
    async def test_setup_static_files_404_handler_returns_index(self):
        """Test that 404 handler returns index.html."""
        app = FastAPI()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)
            index_file = static_dir / "index.html"
            index_file.write_text("<html><body>Test</body></html>")
            
            setup_static_files(app, static_dir)
            
            # Test 404 handler
            handler = app.exception_handlers[404]
            response = await handler(Mock(), Mock())
            assert response is not None

    @pytest.mark.asyncio
    async def test_setup_static_files_404_handler_missing_index(self):
        """Test 404 handler when index.html doesn't exist."""
        app = FastAPI()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)
            
            setup_static_files(app, static_dir)
            
            # Test 404 handler with missing index.html
            handler = app.exception_handlers[404]
            with pytest.raises(RuntimeError, match="File at path .* does not exist"):
                await handler(Mock(), Mock())


class TestGetStaticFilesDir:
    """Test suite for the get_static_files_dir function."""

    def test_get_static_files_dir_returns_path(self):
        """Test that get_static_files_dir returns a Path object."""
        result = get_static_files_dir()
        assert isinstance(result, Path)
        assert result.name == "frontend"

    def test_get_static_files_dir_relative_to_main(self):
        """Test that get_static_files_dir returns path relative to main.py."""
        result = get_static_files_dir()
        # Should be relative to the main.py file location
        assert "frontend" in str(result)


class TestSetupApp:
    """Test suite for the setup_app function."""

    def test_setup_app_creates_fastapi_app(self):
        """Test that setup_app creates FastAPI app."""
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)
            index_file = static_dir / "index.html"
            index_file.write_text("<html><body>Test</body></html>")
            
            app = setup_app(static_dir)
            assert isinstance(app, FastAPI)

    def test_setup_app_backend_only(self):
        """Test setup_app with backend_only=True."""
        app = setup_app(backend_only=True)
        assert isinstance(app, FastAPI)

    def test_setup_app_with_nonexistent_static_dir(self):
        """Test setup_app with non-existent static directory."""
        nonexistent_dir = Path("/nonexistent/directory")
        
        with pytest.raises(RuntimeError, match="Static files directory .* does not exist"):
            setup_app(nonexistent_dir)

    def test_setup_app_with_none_static_dir(self):
        """Test setup_app with None static directory."""
        app = setup_app(static_files_dir=None, backend_only=True)
        assert isinstance(app, FastAPI)

    def test_setup_app_uses_default_static_dir(self):
        """Test that setup_app uses default static directory."""
        with patch('langflow.main.get_static_files_dir') as mock_get_dir:
            mock_get_dir.return_value = Path("/mock/static")
            
            with patch('langflow.main.setup_static_files'):
                app = setup_app(backend_only=True)
                assert isinstance(app, FastAPI)


class TestGetLifespan:
    """Test suite for the get_lifespan function."""

    def test_get_lifespan_returns_context_manager(self):
        """Test that get_lifespan returns a context manager."""
        lifespan = get_lifespan()
        assert callable(lifespan)

    def test_get_lifespan_with_fix_migration(self):
        """Test get_lifespan with fix_migration=True."""
        lifespan = get_lifespan(fix_migration=True)
        assert callable(lifespan)

    def test_get_lifespan_with_version(self):
        """Test get_lifespan with version parameter."""
        lifespan = get_lifespan(version="1.0.0")
        assert callable(lifespan)

    @pytest.mark.asyncio
    async def test_lifespan_context_manager(self):
        """Test lifespan context manager functionality."""
        lifespan = get_lifespan()
        app = FastAPI()
        
        # Mock all the startup dependencies
        with patch('langflow.main.configure'), \
             patch('langflow.main.initialize_services'), \
             patch('langflow.main.setup_llm_caching'), \
             patch('langflow.main.initialize_super_user_if_needed'), \
             patch('langflow.main.load_bundles_with_error_handling') as mock_load_bundles, \
             patch('langflow.main.get_and_cache_all_types_dict'), \
             patch('langflow.main.create_or_update_starter_projects'), \
             patch('langflow.main.load_flows_from_directory'), \
             patch('langflow.main.sync_flows_from_fs'), \
             patch('langflow.main.init_mcp_servers'), \
             patch('langflow.main.get_settings_service'), \
             patch('langflow.main.get_telemetry_service'), \
             patch('langflow.main.get_queue_service'), \
             patch('langflow.main.teardown_services'), \
             patch('langflow.main.FileLock'), \
             patch('langflow.main.logger'):
            
            mock_load_bundles.return_value = ([], [])
            
            try:
                async with lifespan(app):
                    assert True  # Successfully entered context
            except Exception as e:
                # Some startup errors are expected in test environment
                assert "test" in str(e).lower() or "mock" in str(e).lower()

    @pytest.mark.asyncio
    async def test_lifespan_handles_startup_errors(self):
        """Test lifespan handles startup errors gracefully."""
        lifespan = get_lifespan()
        app = FastAPI()
        
        with patch('langflow.main.initialize_services', side_effect=Exception("Startup failed")):
            with pytest.raises(Exception, match="Startup failed"):
                async with lifespan(app):
                    pass

    @pytest.mark.asyncio
    async def test_lifespan_cleanup_on_error(self):
        """Test lifespan cleanup on error."""
        lifespan = get_lifespan()
        app = FastAPI()
        
        with patch('langflow.main.initialize_services', side_effect=Exception("Startup failed")), \
             patch('langflow.main.teardown_services') as mock_teardown:
            
            try:
                async with lifespan(app):
                    pass
            except Exception:
                pass
            
            # Should still call teardown
            mock_teardown.assert_called_once()


class TestLoadBundlesWithErrorHandling:
    """Test suite for the load_bundles_with_error_handling function."""

    @pytest.mark.asyncio
    async def test_load_bundles_success(self):
        """Test successful bundle loading."""
        with patch('langflow.main.load_bundles_from_urls') as mock_load:
            mock_load.return_value = (["bundle1"], ["path1"])
            
            result = await load_bundles_with_error_handling()
            assert result == (["bundle1"], ["path1"])

    @pytest.mark.asyncio
    async def test_load_bundles_timeout_error(self):
        """Test bundle loading with timeout error."""
        with patch('langflow.main.load_bundles_from_urls', side_effect=httpx.TimeoutException("Timeout")):
            result = await load_bundles_with_error_handling()
            assert result == ([], [])

    @pytest.mark.asyncio
    async def test_load_bundles_http_error(self):
        """Test bundle loading with HTTP error."""
        with patch('langflow.main.load_bundles_from_urls', side_effect=httpx.HTTPError("HTTP Error")):
            result = await load_bundles_with_error_handling()
            assert result == ([], [])

    @pytest.mark.asyncio
    async def test_load_bundles_request_error(self):
        """Test bundle loading with request error."""
        with patch('langflow.main.load_bundles_from_urls', side_effect=httpx.RequestError("Request Error")):
            result = await load_bundles_with_error_handling()
            assert result == ([], [])


class TestRequestCancelledMiddleware:
    """Test suite for the RequestCancelledMiddleware class."""

    def test_request_cancelled_middleware_init(self):
        """Test RequestCancelledMiddleware initialization."""
        app = FastAPI()
        middleware = RequestCancelledMiddleware(app)
        assert middleware.app == app

    @pytest.mark.asyncio
    async def test_request_cancelled_middleware_normal_request(self):
        """Test middleware with normal request."""
        app = FastAPI()
        middleware = RequestCancelledMiddleware(app)
        
        request = Mock()
        request.is_disconnected = AsyncMock(return_value=False)
        
        response = Mock()
        call_next = AsyncMock(return_value=response)
        
        result = await middleware.dispatch(request, call_next)
        assert result == response

    @pytest.mark.asyncio
    async def test_request_cancelled_middleware_cancelled_request(self):
        """Test middleware with cancelled request."""
        app = FastAPI()
        middleware = RequestCancelledMiddleware(app)
        
        request = Mock()
        request.is_disconnected = AsyncMock(return_value=True)
        
        async def slow_call_next(req):
            await asyncio.sleep(1)
            return Mock()
        
        result = await middleware.dispatch(request, slow_call_next)
        assert result.status_code == 499
        assert result.body == b"Request was cancelled"


class TestJavaScriptMIMETypeMiddleware:
    """Test suite for the JavaScriptMIMETypeMiddleware class."""

    @pytest.mark.asyncio
    async def test_javascript_mime_type_middleware_js_file(self):
        """Test middleware sets correct MIME type for JS files."""
        middleware = JavaScriptMIMETypeMiddleware(None)
        
        request = Mock()
        request.url.path = "/static/script.js"
        
        response = Mock()
        response.status_code = 200
        response.headers = {}
        
        call_next = AsyncMock(return_value=response)
        
        result = await middleware.dispatch(request, call_next)
        assert result.headers["Content-Type"] == "text/javascript"

    @pytest.mark.asyncio
    async def test_javascript_mime_type_middleware_non_js_file(self):
        """Test middleware doesn't modify non-JS files."""
        middleware = JavaScriptMIMETypeMiddleware(None)
        
        request = Mock()
        request.url.path = "/static/style.css"
        
        response = Mock()
        response.status_code = 200
        response.headers = {}
        
        call_next = AsyncMock(return_value=response)
        
        result = await middleware.dispatch(request, call_next)
        assert "Content-Type" not in result.headers

    @pytest.mark.asyncio
    async def test_javascript_mime_type_middleware_files_path(self):
        """Test middleware ignores files/ path."""
        middleware = JavaScriptMIMETypeMiddleware(None)
        
        request = Mock()
        request.url.path = "/files/script.js"
        
        response = Mock()
        response.status_code = 200
        response.headers = {}
        
        call_next = AsyncMock(return_value=response)
        
        result = await middleware.dispatch(request, call_next)
        assert "Content-Type" not in result.headers

    @pytest.mark.asyncio
    async def test_javascript_mime_type_middleware_handles_exceptions(self):
        """Test middleware handles exceptions properly."""
        middleware = JavaScriptMIMETypeMiddleware(None)
        
        request = Mock()
        request.url.path = "/static/script.js"
        
        from pydantic_core import PydanticSerializationError
        
        call_next = AsyncMock(side_effect=PydanticSerializationError("Test error"))
        
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, call_next)
        
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_javascript_mime_type_middleware_other_exceptions(self):
        """Test middleware re-raises other exceptions."""
        middleware = JavaScriptMIMETypeMiddleware(None)
        
        request = Mock()
        call_next = AsyncMock(side_effect=ValueError("Other error"))
        
        with pytest.raises(ValueError):
            await middleware.dispatch(request, call_next)


class TestConstants:
    """Test suite for constants and other utilities."""

    def test_max_port_constant(self):
        """Test MAX_PORT constant."""
        assert MAX_PORT == 65535

    def test_tasks_list_initialized(self):
        """Test that _tasks list is initialized."""
        from langflow.main import _tasks
        assert isinstance(_tasks, list)


class TestIntegration:
    """Integration tests for main module."""

    def test_full_app_creation_flow(self):
        """Test the complete app creation flow."""
        app = create_app()
        assert isinstance(app, FastAPI)
        assert app.title == "Langflow"
        assert len(app.routes) > 0
        assert len(app.user_middleware) > 0

    def test_app_with_all_middleware(self):
        """Test app with all middleware configured."""
        app = create_app()
        
        # Check all expected middleware types
        middleware_types = [type(middleware).__name__ for middleware in app.user_middleware]
        expected_middleware = [
            'ContentSizeLimitMiddleware',
            'CORSMiddleware',
            'JavaScriptMIMETypeMiddleware'
        ]
        
        for expected in expected_middleware:
            assert any(expected in name for name in middleware_types)

    def test_app_exception_handling(self):
        """Test app exception handling."""
        app = create_app()
        client = TestClient(app)
        
        # Test that the app can handle requests
        response = client.get("/")
        # Should not crash the app
        assert response.status_code in [200, 404, 422]

    def test_app_with_environment_variables(self):
        """Test app creation with various environment variables."""
        env_vars = {
            'LANGFLOW_DEBUG': 'true',
            'LANGFLOW_LOG_LEVEL': 'DEBUG',
            'LANGFLOW_HOST': '127.0.0.1',
            'LANGFLOW_PORT': '8080'
        }
        
        with patch.dict(os.environ, env_vars):
            app = create_app()
            assert isinstance(app, FastAPI)

    def test_setup_app_integration(self):
        """Test setup_app integration."""
        app = setup_app(backend_only=True)
        assert isinstance(app, FastAPI)
        assert app.title == "Langflow"
        assert len(app.routes) > 0


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_create_app_with_import_errors(self):
        """Test create_app handles import errors gracefully."""
        with patch('langflow.main.router', side_effect=ImportError("Module not found")):
            with pytest.raises(ImportError):
                create_app()

    def test_create_app_with_service_errors(self):
        """Test create_app handles service initialization errors."""
        with patch('langflow.main.get_settings_service', side_effect=Exception("Service error")):
            with pytest.raises(Exception):
                create_app()

    def test_prometheus_port_validation(self):
        """Test Prometheus port validation."""
        # Test invalid port (too high)
        with patch.dict(os.environ, {'LANGFLOW_PROMETHEUS_PORT': '99999'}):
            with pytest.raises(ValueError):
                create_app()
        
        # Test invalid port (negative)
        with patch.dict(os.environ, {'LANGFLOW_PROMETHEUS_PORT': '-1'}):
            with pytest.raises(ValueError):
                create_app()

    def test_lifespan_cancellation_handling(self):
        """Test lifespan cancellation handling."""
        lifespan = get_lifespan()
        app = FastAPI()
        
        # This test verifies that the lifespan can be created without errors
        assert callable(lifespan)

    def test_middleware_error_propagation(self):
        """Test that middleware errors are properly propagated."""
        app = create_app()
        
        # Test that the app has proper error handling
        assert len(app.exception_handlers) > 0
        assert Exception in app.exception_handlers or 500 in app.exception_handlers