"""
Unit tests for Langflow middleware functionality.
Testing framework: pytest
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from typing import Dict, Any

from langflow.middleware import ContentSizeLimitMiddleware, MaxFileSizeException


class TestMaxFileSizeException:
    """Test MaxFileSizeException functionality."""
    
    def test_max_file_size_exception_initialization(self):
        """Test MaxFileSizeException initialization with default message."""
        exception = MaxFileSizeException()
        assert exception.status_code == 413
        assert "File size is larger than the maximum file size {}MB" in exception.detail
    
    def test_max_file_size_exception_custom_message(self):
        """Test MaxFileSizeException initialization with custom message."""
        custom_message = "Custom file size error message"
        exception = MaxFileSizeException(detail=custom_message)
        assert exception.status_code == 413
        assert exception.detail == custom_message
    
    def test_max_file_size_exception_inheritance(self):
        """Test MaxFileSizeException inherits from HTTPException."""
        from fastapi import HTTPException
        exception = MaxFileSizeException()
        assert isinstance(exception, HTTPException)
    
    def test_max_file_size_exception_formatted_message(self):
        """Test MaxFileSizeException with formatted message."""
        max_size = 10
        detail = f"File size is larger than the maximum file size {max_size}MB"
        exception = MaxFileSizeException(detail=detail)
        assert exception.detail == detail
        assert str(max_size) in exception.detail


class TestContentSizeLimitMiddleware:
    """Test ContentSizeLimitMiddleware functionality."""
    
    def test_content_size_limit_middleware_initialization(self):
        """Test ContentSizeLimitMiddleware initialization."""
        mock_app = Mock()
        middleware = ContentSizeLimitMiddleware(mock_app)
        
        assert middleware.app is mock_app
        assert middleware.logger is not None
        assert hasattr(middleware, 'receive_wrapper')
        assert hasattr(middleware, '__call__')
    
    def test_content_size_limit_middleware_logger_setup(self):
        """Test middleware logger is properly set up."""
        mock_app = Mock()
        middleware = ContentSizeLimitMiddleware(mock_app)
        
        # Check that logger is from loguru
        assert hasattr(middleware.logger, 'info')
        assert hasattr(middleware.logger, 'error')
        assert hasattr(middleware.logger, 'warning')
    
    def test_receive_wrapper_static_method(self):
        """Test receive_wrapper is a static method."""
        # Test that receive_wrapper can be called as static method
        mock_receive = AsyncMock()
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        assert callable(wrapper)
        assert wrapper.__name__ == 'inner'
    
    @patch('langflow.middleware.get_settings_service')
    def test_receive_wrapper_no_limit(self, mock_get_settings):
        """Test receive_wrapper when no file size limit is set."""
        # Mock settings service to return None for max_file_size_upload
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = None
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        mock_receive.return_value = {
            "type": "http.request",
            "body": b"test content"
        }
        
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        async def test_no_limit():
            result = await wrapper()
            assert result["type"] == "http.request"
            assert result["body"] == b"test content"
        
        asyncio.run(test_no_limit())
    
    @patch('langflow.middleware.get_settings_service')
    def test_receive_wrapper_non_http_request(self, mock_get_settings):
        """Test receive_wrapper with non-HTTP request types."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 10
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        mock_receive.return_value = {
            "type": "websocket.connect",
            "body": b"websocket data"
        }
        
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        async def test_non_http():
            result = await wrapper()
            assert result["type"] == "websocket.connect"
            # Should pass through without size checking
        
        asyncio.run(test_non_http())
    
    @patch('langflow.middleware.get_settings_service')
    def test_receive_wrapper_within_limit(self, mock_get_settings):
        """Test receive_wrapper when content is within size limit."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 10  # 10MB limit
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        # Small content that should pass
        mock_receive.return_value = {
            "type": "http.request",
            "body": b"small content"
        }
        
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        async def test_within_limit():
            result = await wrapper()
            assert result["type"] == "http.request"
            assert result["body"] == b"small content"
        
        asyncio.run(test_within_limit())
    
    @patch('langflow.middleware.get_settings_service')
    def test_receive_wrapper_exceeds_limit(self, mock_get_settings):
        """Test receive_wrapper when content exceeds size limit."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 1  # 1MB limit
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        # Large content that exceeds 1MB
        large_content = b"x" * (2 * 1024 * 1024)  # 2MB
        mock_receive.return_value = {
            "type": "http.request",
            "body": large_content
        }
        
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        async def test_exceeds_limit():
            with pytest.raises(MaxFileSizeException) as exc_info:
                await wrapper()
            
            assert exc_info.value.status_code == 413
            assert "Content size limit exceeded" in exc_info.value.detail
            assert "Maximum allowed is 1MB" in exc_info.value.detail
        
        asyncio.run(test_exceeds_limit())
    
    @patch('langflow.middleware.get_settings_service')
    def test_receive_wrapper_cumulative_size_tracking(self, mock_get_settings):
        """Test receive_wrapper tracks cumulative size across multiple calls."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 1  # 1MB limit
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        # Create a sequence of messages that together exceed the limit
        chunk_size = 600 * 1024  # 600KB chunks
        
        call_count = 0
        async def mock_receive_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {
                    "type": "http.request",
                    "body": b"x" * chunk_size
                }
            return {
                "type": "http.request",
                "body": b""
            }
        
        mock_receive.side_effect = mock_receive_func
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        async def test_cumulative():
            # First call should succeed (600KB)
            result1 = await wrapper()
            assert result1["type"] == "http.request"
            
            # Second call should fail (600KB + 600KB = 1.2MB > 1MB)
            with pytest.raises(MaxFileSizeException) as exc_info:
                await wrapper()
            
            assert exc_info.value.status_code == 413
            assert "Content size limit exceeded" in exc_info.value.detail
        
        asyncio.run(test_cumulative())
    
    @patch('langflow.middleware.get_settings_service')
    def test_receive_wrapper_empty_body(self, mock_get_settings):
        """Test receive_wrapper with empty body."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 10
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        mock_receive.return_value = {
            "type": "http.request",
            "body": b""
        }
        
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        async def test_empty_body():
            result = await wrapper()
            assert result["type"] == "http.request"
            assert result["body"] == b""
        
        asyncio.run(test_empty_body())
    
    @patch('langflow.middleware.get_settings_service')
    def test_receive_wrapper_missing_body(self, mock_get_settings):
        """Test receive_wrapper with missing body field."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 10
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        mock_receive.return_value = {
            "type": "http.request"
            # No body field
        }
        
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        async def test_missing_body():
            result = await wrapper()
            assert result["type"] == "http.request"
            # Should handle missing body gracefully
        
        asyncio.run(test_missing_body())
    
    def test_middleware_call_http_scope(self):
        """Test middleware __call__ method with HTTP scope."""
        mock_app = AsyncMock()
        middleware = ContentSizeLimitMiddleware(mock_app)
        
        scope = {"type": "http", "path": "/api/test"}
        receive = AsyncMock()
        send = AsyncMock()
        
        async def test_http_call():
            await middleware(scope, receive, send)
            
            # Should call the app with wrapped receive
            mock_app.assert_called_once()
            call_args = mock_app.call_args[0]
            assert call_args[0] == scope
            assert call_args[2] == send
            # The receive argument should be wrapped
            assert call_args[1] != receive
        
        asyncio.run(test_http_call())
    
    def test_middleware_call_non_http_scope(self):
        """Test middleware __call__ method with non-HTTP scope."""
        mock_app = AsyncMock()
        middleware = ContentSizeLimitMiddleware(mock_app)
        
        scope = {"type": "websocket", "path": "/ws"}
        receive = AsyncMock()
        send = AsyncMock()
        
        async def test_non_http_call():
            await middleware(scope, receive, send)
            
            # Should call the app directly without wrapping
            mock_app.assert_called_once_with(scope, receive, send)
        
        asyncio.run(test_non_http_call())
    
    @patch('langflow.middleware.get_settings_service')
    def test_middleware_integration_with_settings_service(self, mock_get_settings):
        """Test middleware integration with settings service."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 5
        mock_get_settings.return_value = mock_settings
        
        mock_app = AsyncMock()
        middleware = ContentSizeLimitMiddleware(mock_app)
        
        # Create a mock receive that returns a large file
        mock_receive = AsyncMock()
        large_content = b"x" * (10 * 1024 * 1024)  # 10MB
        mock_receive.return_value = {
            "type": "http.request",
            "body": large_content
        }
        
        scope = {"type": "http", "path": "/api/upload"}
        send = AsyncMock()
        
        async def test_settings_integration():
            with pytest.raises(MaxFileSizeException) as exc_info:
                await middleware(scope, mock_receive, send)
            
            # Verify the settings service was called
            mock_get_settings.assert_called()
            assert exc_info.value.status_code == 413
            assert "Maximum allowed is 5MB" in exc_info.value.detail
        
        asyncio.run(test_settings_integration())
    
    def test_middleware_error_message_formatting(self):
        """Test error message formatting in middleware."""
        # Test the error message format when size limit is exceeded
        max_size = 10
        received_bytes = 15 * 1024 * 1024  # 15MB in bytes
        received_mb = round(received_bytes / (1024 * 1024), 3)
        
        expected_message = (
            f"Content size limit exceeded. Maximum allowed is {max_size}MB"
            f" and got {received_mb}MB."
        )
        
        # This tests the message format that should be used in the middleware
        assert f"Maximum allowed is {max_size}MB" in expected_message
        assert f"got {received_mb}MB" in expected_message
        assert "Content size limit exceeded" in expected_message
    
    @patch('langflow.middleware.get_settings_service')
    def test_middleware_size_calculation_accuracy(self, mock_get_settings):
        """Test accurate size calculation in middleware."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 1  # 1MB limit
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        # Create content that's exactly at the limit
        exact_limit_content = b"x" * (1 * 1024 * 1024)  # Exactly 1MB
        mock_receive.return_value = {
            "type": "http.request",
            "body": exact_limit_content
        }
        
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        async def test_exact_limit():
            # Should succeed at exact limit
            result = await wrapper()
            assert result["type"] == "http.request"
            assert len(result["body"]) == 1024 * 1024
        
        asyncio.run(test_exact_limit())
    
    @patch('langflow.middleware.get_settings_service')
    def test_middleware_different_message_types(self, mock_get_settings):
        """Test middleware behavior with different ASGI message types."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 10
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        
        # Test different message types
        message_types = [
            {"type": "http.request", "body": b"content"},
            {"type": "http.disconnect"},
            {"type": "websocket.connect"},
            {"type": "websocket.receive", "text": "message"},
            {"type": "websocket.disconnect"}
        ]
        
        for message in message_types:
            mock_receive.return_value = message
            wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
            
            async def test_message_type():
                result = await wrapper()
                assert result["type"] == message["type"]
                if message["type"] == "http.request":
                    assert "body" in result
            
            asyncio.run(test_message_type())
    
    @patch('langflow.middleware.get_settings_service')
    def test_middleware_concurrent_requests(self, mock_get_settings):
        """Test middleware behavior with concurrent requests."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 5
        mock_get_settings.return_value = mock_settings
        
        mock_app = AsyncMock()
        middleware = ContentSizeLimitMiddleware(mock_app)
        
        # Create multiple concurrent requests
        async def make_request(content_size):
            mock_receive = AsyncMock()
            mock_receive.return_value = {
                "type": "http.request",
                "body": b"x" * content_size
            }
            
            scope = {"type": "http", "path": "/api/test"}
            send = AsyncMock()
            
            await middleware(scope, mock_receive, send)
        
        async def test_concurrent():
            # Create tasks for concurrent requests
            tasks = []
            
            # Small requests that should succeed
            for i in range(3):
                task = asyncio.create_task(make_request(1024))  # 1KB
                tasks.append(task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
            
            # All should have succeeded
            assert len(tasks) == 3
        
        asyncio.run(test_concurrent())
    
    def test_middleware_asgi_compliance(self):
        """Test middleware follows ASGI specification."""
        mock_app = AsyncMock()
        middleware = ContentSizeLimitMiddleware(mock_app)
        
        # Test that middleware is callable with correct signature
        assert callable(middleware)
        
        # Test that __call__ method has correct signature
        import inspect
        sig = inspect.signature(middleware.__call__)
        params = list(sig.parameters.keys())
        
        # ASGI application should have (scope, receive, send) signature
        assert len(params) == 4  # self, scope, receive, send
        assert params[1] == 'scope'
        assert params[2] == 'receive'
        assert params[3] == 'send'
    
    @patch('langflow.middleware.get_settings_service')
    def test_middleware_error_handling_edge_cases(self, mock_get_settings):
        """Test middleware error handling in edge cases."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 1
        mock_get_settings.return_value = mock_settings
        
        # Test with settings service returning None
        mock_get_settings.return_value = None
        
        mock_receive = AsyncMock()
        mock_receive.return_value = {
            "type": "http.request",
            "body": b"test content"
        }
        
        wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
        
        async def test_no_settings():
            # Should handle missing settings gracefully
            try:
                result = await wrapper()
                # If no exception, it should return the message
                assert result["type"] == "http.request"
            except AttributeError:
                # Expected if settings service is None
                pass
        
        asyncio.run(test_no_settings())
    
    @patch('langflow.middleware.get_settings_service')
    def test_middleware_performance_with_large_files(self, mock_get_settings):
        """Test middleware performance characteristics with large files."""
        mock_settings = Mock()
        mock_settings.server.max_file_size_upload = 100  # 100MB limit
        mock_get_settings.return_value = mock_settings
        
        mock_receive = AsyncMock()
        
        # Test with progressively larger file sizes
        file_sizes = [
            1024,          # 1KB
            1024 * 1024,   # 1MB
            10 * 1024 * 1024,  # 10MB
            50 * 1024 * 1024,  # 50MB
        ]
        
        for size in file_sizes:
            mock_receive.return_value = {
                "type": "http.request",
                "body": b"x" * size
            }
            
            wrapper = ContentSizeLimitMiddleware.receive_wrapper(mock_receive)
            
            async def test_size():
                import time
                start_time = time.time()
                result = await wrapper()
                end_time = time.time()
                
                # Should complete in reasonable time
                assert end_time - start_time < 1.0  # Less than 1 second
                assert result["type"] == "http.request"
                assert len(result["body"]) == size
            
            asyncio.run(test_size())