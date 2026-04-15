"""Tests for DisconnectHandlerStreamingResponse."""

import pytest
from langflow.api.disconnect import DisconnectHandlerStreamingResponse

pytestmark = pytest.mark.asyncio


class TestDisconnectHandlerStreamingResponse:
    """Tests for DisconnectHandlerStreamingResponse."""

    def test_init_default(self):
        async def gen():
            yield b"data"

        response = DisconnectHandlerStreamingResponse(content=gen())
        assert response.on_disconnect is None
        assert response.status_code == 200

    def test_init_with_callback(self):
        async def gen():
            yield b"data"

        def callback():
            pass

        response = DisconnectHandlerStreamingResponse(content=gen(), on_disconnect=callback)
        assert response.on_disconnect is callback

    def test_init_with_custom_status(self):
        async def gen():
            yield b"data"

        response = DisconnectHandlerStreamingResponse(content=gen(), status_code=201)
        assert response.status_code == 201

    def test_init_with_headers(self):
        async def gen():
            yield b"data"

        response = DisconnectHandlerStreamingResponse(
            content=gen(), headers={"X-Custom": "value"}, media_type="text/plain"
        )
        assert response.media_type == "text/plain"

    async def test_listen_for_disconnect_calls_sync_callback(self):
        async def gen():
            yield b"data"

        called = []

        def callback():
            called.append(True)

        response = DisconnectHandlerStreamingResponse(content=gen(), on_disconnect=callback)

        async def mock_receive():
            return {"type": "http.disconnect"}

        await response.listen_for_disconnect(mock_receive)
        assert len(called) == 1

    async def test_listen_for_disconnect_calls_async_callback(self):
        async def gen():
            yield b"data"

        called = []

        async def callback():
            called.append(True)

        response = DisconnectHandlerStreamingResponse(content=gen(), on_disconnect=callback)

        async def mock_receive():
            return {"type": "http.disconnect"}

        await response.listen_for_disconnect(mock_receive)
        assert len(called) == 1

    async def test_listen_for_disconnect_no_callback(self):
        async def gen():
            yield b"data"

        response = DisconnectHandlerStreamingResponse(content=gen())

        async def mock_receive():
            return {"type": "http.disconnect"}

        # Should not raise even without callback
        await response.listen_for_disconnect(mock_receive)

    async def test_listen_for_disconnect_waits_for_disconnect(self):
        async def gen():
            yield b"data"

        called = []

        def callback():
            called.append(True)

        response = DisconnectHandlerStreamingResponse(content=gen(), on_disconnect=callback)

        call_count = 0

        async def mock_receive():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"type": "http.request"}
            return {"type": "http.disconnect"}

        await response.listen_for_disconnect(mock_receive)
        assert len(called) == 1
        assert call_count == 3
