"""Tests for the health check router schemas."""

from langflow.api.health_check_router import HealthResponse


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_default_values(self):
        response = HealthResponse()
        assert response.status == "nok"
        assert response.chat == "error check the server logs"
        assert response.db == "error check the server logs"

    def test_has_error_default(self):
        response = HealthResponse()
        assert response.has_error() is True

    def test_has_error_all_ok(self):
        response = HealthResponse(status="ok", chat="ok", db="ok")
        assert response.has_error() is False

    def test_has_error_partial(self):
        response = HealthResponse(status="ok", chat="ok", db="error check the server logs")
        assert response.has_error() is True

    def test_has_error_chat_error(self):
        response = HealthResponse(status="ok", chat="error something", db="ok")
        assert response.has_error() is True

    def test_has_error_status_error(self):
        response = HealthResponse(status="error", chat="ok", db="ok")
        assert response.has_error() is True

    def test_model_dump(self):
        response = HealthResponse(status="ok", chat="ok", db="ok")
        dumped = response.model_dump()
        assert dumped == {"status": "ok", "chat": "ok", "db": "ok"}

    def test_custom_values(self):
        response = HealthResponse(status="ok", chat="connected", db="connected")
        assert response.has_error() is False
