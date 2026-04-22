"""Regression tests for the SDK upload helper after the auth change.

After PR #12831, the server's ``/api/v1/upload/{flow_id}`` endpoint requires
authentication.  The SDK helpers in :mod:`lfx.load.utils` were updated to
forward an optional ``api_key`` (or ``LANGFLOW_API_KEY`` env var) as the
``x-api-key`` header so existing callers can pass credentials without
rewriting against the non-deprecated ``/api/v1/files/upload/{flow_id}``
route.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx.load.utils import UploadError, upload, upload_file


def _ok_response() -> MagicMock:
    response = MagicMock()
    response.status_code = httpx.codes.CREATED
    response.json.return_value = {"file_path": "flow_id/some_file.txt"}
    return response


def test_upload_sends_api_key_header_when_passed_explicitly(tmp_path):
    file_path = tmp_path / "x.txt"
    file_path.write_bytes(b"contents")

    with patch("lfx.load.utils.httpx.post", return_value=_ok_response()) as mock_post:
        upload(str(file_path), "http://host", "flow-1", api_key="sk-test-123")  # pragma: allowlist secret

    assert mock_post.call_count == 1
    _args, kwargs = mock_post.call_args
    assert kwargs["headers"] == {"x-api-key": "sk-test-123"}  # pragma: allowlist secret


def test_upload_falls_back_to_env_var(tmp_path, monkeypatch):
    file_path = tmp_path / "x.txt"
    file_path.write_bytes(b"contents")
    monkeypatch.setenv("LANGFLOW_API_KEY", "sk-from-env")  # pragma: allowlist secret

    with patch("lfx.load.utils.httpx.post", return_value=_ok_response()) as mock_post:
        upload(str(file_path), "http://host", "flow-1")

    _args, kwargs = mock_post.call_args
    assert kwargs["headers"] == {"x-api-key": "sk-from-env"}  # pragma: allowlist secret


def test_upload_explicit_api_key_overrides_env_var(tmp_path, monkeypatch):
    file_path = tmp_path / "x.txt"
    file_path.write_bytes(b"contents")
    monkeypatch.setenv("LANGFLOW_API_KEY", "sk-from-env")  # pragma: allowlist secret

    with patch("lfx.load.utils.httpx.post", return_value=_ok_response()) as mock_post:
        upload(str(file_path), "http://host", "flow-1", api_key="sk-explicit")  # pragma: allowlist secret

    _args, kwargs = mock_post.call_args
    assert kwargs["headers"] == {"x-api-key": "sk-explicit"}  # pragma: allowlist secret


def test_upload_sends_no_headers_when_no_api_key(tmp_path, monkeypatch):
    """Preserve pre-fix wire format for callers who intentionally pass no key.

    The server will now reject the request, but the SDK should not fabricate
    a bogus header.  An authn failure at the server is the correct signal.
    """
    file_path = tmp_path / "x.txt"
    file_path.write_bytes(b"contents")
    monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)

    with patch("lfx.load.utils.httpx.post", return_value=_ok_response()) as mock_post:
        upload(str(file_path), "http://host", "flow-1")

    _args, kwargs = mock_post.call_args
    assert kwargs["headers"] == {}


def test_upload_file_forwards_api_key(tmp_path):
    """``upload_file`` must pass the api_key through to ``upload``."""
    file_path = tmp_path / "x.txt"
    file_path.write_bytes(b"contents")

    with patch("lfx.load.utils.upload", return_value={"file_path": "flow/x.txt"}) as mock_upload:
        upload_file(
            str(file_path),
            host="http://host",
            flow_id="flow-1",
            components=["comp"],
            api_key="sk-explicit",  # pragma: allowlist secret
        )

    # pragma: allowlist secret
    mock_upload.assert_called_once_with(
        str(file_path),
        "http://host",
        "flow-1",
        api_key="sk-explicit",  # pragma: allowlist secret
    )


def test_upload_raises_upload_error_on_auth_failure(tmp_path, monkeypatch):
    """A server-side 401 (no auth sent) surfaces as UploadError to the caller."""
    file_path = tmp_path / "x.txt"
    file_path.write_bytes(b"contents")
    monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)

    response = MagicMock()
    response.status_code = httpx.codes.UNAUTHORIZED
    with patch("lfx.load.utils.httpx.post", return_value=response), pytest.raises(UploadError):
        upload(str(file_path), "http://host", "flow-1")
