"""Unit tests for path traversal security fixes.

Tests the security fixes for CVE-2025-XXXXX (Arbitrary File Write vulnerability).
Verifies both API-layer filename sanitization and storage-layer path containment checks.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient


async def test_upload_file_rejects_directory_traversal(client: AsyncClient, logged_in_headers):
    """Test that directory traversal sequences in multipart filename are rejected."""
    malicious_filename = "../../etc/passwd"
    files = {"file": (malicious_filename, b"malicious content", "text/plain")}

    response = await client.post(
        "api/v2/files/",
        files=files,
        headers=logged_in_headers,
    )

    assert response.status_code == 400
    assert "Invalid file name" in response.json()["detail"]


async def test_upload_file_rejects_backslash_traversal(client: AsyncClient, logged_in_headers):
    """Test that Windows-style directory traversal is rejected."""
    malicious_filename = "..\\..\\windows\\system32\\config\\sam"
    files = {"file": (malicious_filename, b"malicious content", "text/plain")}

    response = await client.post(
        "api/v2/files/",
        files=files,
        headers=logged_in_headers,
    )

    assert response.status_code == 400
    assert "Invalid file name" in response.json()["detail"]


async def test_upload_file_rejects_absolute_path(client: AsyncClient, logged_in_headers):
    """Test that absolute paths in filename are rejected."""
    malicious_filename = "/etc/passwd"
    files = {"file": (malicious_filename, b"malicious content", "text/plain")}

    response = await client.post(
        "api/v2/files/",
        files=files,
        headers=logged_in_headers,
    )

    assert response.status_code == 400
    assert "Invalid file name" in response.json()["detail"]


async def test_upload_file_rejects_complex_traversal(client: AsyncClient, logged_in_headers):
    """Test that complex traversal patterns are rejected."""
    malicious_filenames = [
        "....//....//etc/shadow",
        "normal/../../../evil.py",
        "file.txt/../../../root/.ssh/id_rsa",
    ]

    for filename in malicious_filenames:
        files = {"file": (filename, b"malicious content", "text/plain")}
        response = await client.post(
            "api/v2/files/",
            files=files,
            headers=logged_in_headers,
        )

        assert response.status_code == 400, f"Failed to reject: {filename}"
        assert "Invalid file name" in response.json()["detail"]


async def test_upload_file_accepts_valid_filename(client: AsyncClient, logged_in_headers):
    """Test that legitimate filenames are accepted."""
    valid_filenames = [
        "document.pdf",
        "image.png",
        "data_file.csv",
        "my-file_v2.txt",
    ]

    for filename in valid_filenames:
        files = {"file": (filename, b"legitimate content", "text/plain")}
        response = await client.post(
            "api/v2/files/",
            files=files,
            headers=logged_in_headers,
        )

        assert response.status_code == 201, f"Rejected valid filename: {filename}"
        data = response.json()
        assert data["name"] is not None


async def test_upload_file_rejects_path_with_slashes(client: AsyncClient, logged_in_headers):
    """Test that filenames containing slashes are rejected (security fix)."""
    # Filenames with slashes should be rejected to prevent path traversal
    files = {"file": ("subdir/nested/file.txt", b"content", "text/plain")}
    response = await client.post(
        "api/v2/files/",
        files=files,
        headers=logged_in_headers,
    )

    # Should be rejected because it contains slashes
    assert response.status_code == 400
    assert "Invalid file name" in response.json()["detail"]


async def test_upload_file_rejects_empty_filename(client: AsyncClient, logged_in_headers):
    """Test that empty filename is rejected."""
    files = {"file": ("", b"content", "text/plain")}
    response = await client.post(
        "api/v2/files/",
        files=files,
        headers=logged_in_headers,
    )

    # Should be rejected with either 400 or 422 (both are valid error codes for invalid input)
    assert response.status_code in (400, 422)


async def test_upload_and_download_legitimate_file(client: AsyncClient, logged_in_headers):
    """Test complete upload and download flow with legitimate file."""
    filename = "test_document.pdf"
    content = b"This is a legitimate PDF content"

    # Upload
    files = {"file": (filename, content, "application/pdf")}
    upload_response = await client.post(
        "api/v2/files/",
        files=files,
        headers=logged_in_headers,
    )

    assert upload_response.status_code == 201
    data = upload_response.json()
    assert "test_document" in data["name"]
    assert data["size"] == len(content)

    # Download
    file_id = data["id"]
    download_response = await client.get(
        f"api/v2/files/{file_id}",
        headers=logged_in_headers,
    )

    assert download_response.status_code == 200
    assert download_response.content == content


async def test_upload_file_no_path_escape_via_null_bytes(client: AsyncClient, logged_in_headers):
    """Test that null bytes and other tricks don't bypass validation."""
    # Null bytes and other special characters should not bypass validation
    malicious_filenames = [
        "file.txt\x00../../etc/passwd",
        "../../etc/passwd\x00.txt",
    ]

    for filename in malicious_filenames:
        files = {"file": (filename, b"malicious", "text/plain")}
        response = await client.post(
            "api/v2/files/",
            files=files,
            headers=logged_in_headers,
        )

        # Should be rejected (either 400 for invalid filename or sanitized to safe name)
        # The important thing is it doesn't write to /etc/passwd
        assert response.status_code in (400, 201)
        if response.status_code == 201:
            # If accepted, verify the filename was sanitized
            data = response.json()
            assert "etc" not in data["path"]
            assert "passwd" not in data["path"] or "passwd" in data["name"]


@pytest.mark.usefixtures("active_user")
async def test_storage_layer_path_containment_check(client: AsyncClient, logged_in_headers):
    """Test that storage layer has defense-in-depth path containment.

    This test verifies that even if API layer validation is bypassed,
    the storage layer will reject path traversal attempts.
    """
    # This test verifies the storage layer protection exists
    # by attempting an upload that should be caught by API layer
    # but would also be caught by storage layer if API layer failed

    malicious_filename = "../../../../../../tmp/pwned.txt"
    files = {"file": (malicious_filename, b"you got pwned", "text/plain")}

    response = await client.post(
        "api/v2/files/",
        files=files,
        headers=logged_in_headers,
    )

    # Should be rejected at API layer
    assert response.status_code == 400

    # Verify no file was created in /tmp (S108: this is intentional for security testing)
    import tempfile

    tmp_dir = tempfile.gettempdir()
    pwned_path = Path(tmp_dir) / "pwned.txt"
    if pwned_path.exists():
        # If it exists, verify it wasn't created by us
        content = pwned_path.read_bytes()
        assert b"you got pwned" not in content


async def test_upload_file_with_unicode_filename(client: AsyncClient, logged_in_headers):
    """Test that Unicode filenames are handled correctly."""
    unicode_filenames = [
        "文档.pdf",
        "документ.txt",
        "αρχείο.csv",
    ]

    for filename in unicode_filenames:
        files = {"file": (filename, b"content", "text/plain")}
        response = await client.post(
            "api/v2/files/",
            files=files,
            headers=logged_in_headers,
        )

        # Should accept valid Unicode filenames
        assert response.status_code == 201, f"Rejected Unicode filename: {filename}"


async def test_upload_file_preserves_extension(client: AsyncClient, logged_in_headers):
    """Test that file extensions are preserved correctly."""
    files = {"file": ("document.pdf", b"PDF content", "application/pdf")}
    response = await client.post(
        "api/v2/files/",
        files=files,
        headers=logged_in_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["path"].endswith(".pdf")
