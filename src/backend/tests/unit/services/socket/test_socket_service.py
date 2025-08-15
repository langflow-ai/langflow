from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import socketio
from langflow.services.cache.base import AsyncBaseCacheService, CacheService
from langflow.services.socket.service import SocketIOService


class TestSocketIOService:
    """Test cases for SocketIOService."""

    @pytest.fixture
    def mock_cache_service(self):
        """Create a mock cache service."""
        return MagicMock(spec=CacheService)

    @pytest.fixture
    def mock_async_cache_service(self):
        """Create a mock async cache service."""
        return MagicMock(spec=AsyncBaseCacheService)

    @pytest.fixture
    def socket_service(self, mock_cache_service):
        """Create a SocketIOService instance for testing."""
        return SocketIOService(mock_cache_service)

    @pytest.fixture
    def mock_sio(self):
        """Create a mock socketio server."""
        mock_server = MagicMock(spec=socketio.AsyncServer)
        mock_server.event = MagicMock()
        mock_server.on = MagicMock()
        mock_server.emit = AsyncMock()
        return mock_server

    def test_service_name(self):
        """Test that service name is correctly set."""
        assert SocketIOService.name == "socket_service"

    def test_initialization_with_cache_service(self, mock_cache_service):
        """Test initialization with cache service."""
        service = SocketIOService(mock_cache_service)
        assert service.cache_service == mock_cache_service

    def test_initialization_with_async_cache_service(self, mock_async_cache_service):
        """Test initialization with async cache service."""
        service = SocketIOService(mock_async_cache_service)
        assert service.cache_service == mock_async_cache_service

    def test_init_with_socketio_server(self, socket_service, mock_sio):
        """Test initialization with socketio server."""
        socket_service.init(mock_sio)

        assert socket_service.sio == mock_sio
        assert hasattr(socket_service, "sessions")
        assert socket_service.sessions == {}

        # Verify event handlers are registered
        mock_sio.event.assert_any_call(socket_service.connect)
        mock_sio.event.assert_any_call(socket_service.disconnect)
        mock_sio.on.assert_any_call("message")
        mock_sio.on.assert_any_call("get_vertices")
        mock_sio.on.assert_any_call("build_vertex")

    def test_init_with_none_sio(self, socket_service):
        """Test initialization with None sio server."""
        socket_service.init(None)

        assert socket_service.sio is None
        assert hasattr(socket_service, "sessions")
        assert socket_service.sessions == {}

    @pytest.mark.asyncio
    async def test_emit_error(self, socket_service, mock_sio):
        """Test emit_error method."""
        socket_service.init(mock_sio)

        sid = "test_sid"
        error = {"error": "test error"}

        await socket_service.emit_error(sid, error)

        mock_sio.emit.assert_called_once_with("error", to=sid, data=error)

    @pytest.mark.asyncio
    async def test_connect(self, socket_service, mock_sio):
        """Test connect method."""
        socket_service.init(mock_sio)

        sid = "test_sid"
        environ = {"test": "environment"}

        with patch("langflow.services.socket.service.logger") as mock_logger:
            await socket_service.connect(sid, environ)

            mock_logger.info.assert_called_once_with(f"Socket connected: {sid}")
            assert socket_service.sessions[sid] == environ

    @pytest.mark.asyncio
    async def test_disconnect(self, socket_service, mock_sio):
        """Test disconnect method."""
        socket_service.init(mock_sio)

        # Set up initial session
        sid = "test_sid"
        socket_service.sessions[sid] = {"test": "data"}

        with patch("langflow.services.socket.service.logger") as mock_logger:
            await socket_service.disconnect(sid)

            mock_logger.info.assert_called_once_with(f"Socket disconnected: {sid}")
            assert sid not in socket_service.sessions

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_session(self, socket_service, mock_sio):
        """Test disconnect method with non-existent session."""
        socket_service.init(mock_sio)

        sid = "nonexistent_sid"

        with patch("langflow.services.socket.service.logger") as mock_logger:
            await socket_service.disconnect(sid)

            mock_logger.info.assert_called_once_with(f"Socket disconnected: {sid}")
            # Should not raise error

    @pytest.mark.asyncio
    async def test_message_with_data(self, socket_service, mock_sio):
        """Test message method with provided data."""
        socket_service.init(mock_sio)

        sid = "test_sid"
        data = {"custom": "data"}

        await socket_service.message(sid, data)

        mock_sio.emit.assert_called_once_with("message", to=sid, data=data)

    @pytest.mark.asyncio
    async def test_message_without_data(self, socket_service, mock_sio):
        """Test message method without provided data."""
        socket_service.init(mock_sio)

        sid = "test_sid"

        await socket_service.message(sid)

        expected_data = {"foo": "bar", "baz": [1, 2, 3]}
        mock_sio.emit.assert_called_once_with("message", to=sid, data=expected_data)

    @pytest.mark.asyncio
    async def test_emit_message(self, socket_service, mock_sio):
        """Test emit_message method."""
        socket_service.init(mock_sio)

        to = "test_recipient"
        data = {"test": "message"}

        await socket_service.emit_message(to, data)

        mock_sio.emit.assert_called_once_with("message", to=to, data=data)

    @pytest.mark.asyncio
    async def test_emit_token(self, socket_service, mock_sio):
        """Test emit_token method."""
        socket_service.init(mock_sio)

        to = "test_recipient"
        data = {"token": "test_token"}

        await socket_service.emit_token(to, data)

        mock_sio.emit.assert_called_once_with("token", to=to, data=data)

    def test_sessions_initialization(self, socket_service, mock_sio):
        """Test that sessions dict is properly initialized."""
        socket_service.init(mock_sio)

        assert hasattr(socket_service, "sessions")
        assert isinstance(socket_service.sessions, dict)
        assert socket_service.sessions == {}

    @pytest.mark.asyncio
    async def test_multiple_sessions(self, socket_service, mock_sio):
        """Test handling multiple sessions."""
        socket_service.init(mock_sio)

        # Connect multiple sessions
        with patch("langflow.services.socket.service.logger"):
            await socket_service.connect("sid1", {"env": "1"})
            await socket_service.connect("sid2", {"env": "2"})

            assert len(socket_service.sessions) == 2
            assert socket_service.sessions["sid1"] == {"env": "1"}
            assert socket_service.sessions["sid2"] == {"env": "2"}

            # Disconnect one session
            await socket_service.disconnect("sid1")

            assert len(socket_service.sessions) == 1
            assert "sid1" not in socket_service.sessions
            assert socket_service.sessions["sid2"] == {"env": "2"}

    @pytest.mark.asyncio
    async def test_error_handling_in_emit_methods(self, socket_service, mock_sio):
        """Test error handling in emit methods."""
        socket_service.init(mock_sio)

        # Mock emit to raise an exception
        mock_sio.emit.side_effect = Exception("Connection error")

        # These methods should handle exceptions gracefully
        with pytest.raises(Exception, match="Connection error"):
            await socket_service.emit_error("sid", {"error": "test"})

        with pytest.raises(Exception, match="Connection error"):
            await socket_service.emit_message("sid", {"message": "test"})

        with pytest.raises(Exception, match="Connection error"):
            await socket_service.emit_token("sid", {"token": "test"})
