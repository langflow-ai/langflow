"""Tests for API schema models."""

from uuid import UUID, uuid4

from langflow.api.schemas import UploadFileResponse


class TestUploadFileResponse:
    """Tests for UploadFileResponse model."""

    def test_create_response(self):
        uid = uuid4()
        response = UploadFileResponse(id=uid, name="test.txt", path="/tmp/test.txt", size=1024)
        assert response.id == uid
        assert response.name == "test.txt"
        assert response.path == "/tmp/test.txt"
        assert response.size == 1024
        assert response.provider is None

    def test_with_provider(self):
        uid = uuid4()
        response = UploadFileResponse(id=uid, name="test.txt", path="/tmp/test.txt", size=1024, provider="s3")
        assert response.provider == "s3"

    def test_model_dump(self):
        uid = uuid4()
        response = UploadFileResponse(id=uid, name="file.pdf", path="/uploads/file.pdf", size=2048, provider="local")
        dumped = response.model_dump()
        assert dumped["id"] == uid
        assert dumped["name"] == "file.pdf"
        assert dumped["path"] == "/uploads/file.pdf"
        assert dumped["size"] == 2048
        assert dumped["provider"] == "local"

    def test_id_is_uuid(self):
        uid = uuid4()
        response = UploadFileResponse(id=uid, name="test.txt", path="/test", size=100)
        assert isinstance(response.id, UUID)

    def test_zero_size(self):
        response = UploadFileResponse(id=uuid4(), name="empty.txt", path="/empty", size=0)
        assert response.size == 0

    def test_large_size(self):
        response = UploadFileResponse(id=uuid4(), name="large.bin", path="/large", size=10**12)
        assert response.size == 10**12
