"""Tests for API schema models."""

from uuid import uuid4

from langflow.api.schemas import UploadFileResponse


class TestUploadFileResponse:
    """Tests for UploadFileResponse model."""

    def test_create_response(self):
        uid = uuid4()
        response = UploadFileResponse(id=uid, name="test.txt", path="/uploads/test.txt", size=1024)
        assert response.id == uid
        assert response.name == "test.txt"
        assert response.path == "/uploads/test.txt"
        assert response.size == 1024
        assert response.provider is None

    def test_with_provider(self):
        uid = uuid4()
        response = UploadFileResponse(id=uid, name="test.txt", path="/uploads/test.txt", size=1024, provider="s3")
        assert response.provider == "s3"
