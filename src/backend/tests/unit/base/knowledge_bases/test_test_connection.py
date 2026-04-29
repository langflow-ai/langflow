"""Unit tests for ``BaseVectorStoreBackend.test_connection`` and overrides.

Exercises the default implementation (via Chroma + a stub backend),
the Chroma-specific path-writability check, and the OpenSearch
``cluster.info`` ping with each error class mapped to the
appropriate user-facing message.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from lfx.base.knowledge_bases.backends import (
    BackendType,
    ChromaBackend,
    OpenSearchBackend,
    TestConnectionResult,
)
from lfx.base.knowledge_bases.backends.base import BaseVectorStoreBackend

if TYPE_CHECKING:
    from pathlib import Path


class _StubBackend(BaseVectorStoreBackend):
    """Minimal backend whose ``_build_vector_store`` is controllable."""

    backend_type = BackendType.CHROMA  # arbitrary; not exercised here

    def __init__(self, *, kb_path: Path, build_error: Exception | None = None) -> None:
        super().__init__(kb_name="stub_kb", kb_path=kb_path)
        self._build_error = build_error

    def _build_vector_store(self) -> Any:
        if self._build_error is not None:
            raise self._build_error
        return MagicMock(name="vector_store")


class TestDefaultTestConnection:
    """Default impl on ``BaseVectorStoreBackend``.

    Exercised via a stub backend so we can drive the success and failure
    paths without depending on any concrete vector-store library.
    """

    @pytest.mark.asyncio
    async def test_returns_ok_when_build_succeeds(self, tmp_path: Path) -> None:
        backend = _StubBackend(kb_path=tmp_path)
        result = await backend.test_connection()
        assert isinstance(result, TestConnectionResult)
        assert result.ok is True
        assert result.message

    @pytest.mark.asyncio
    async def test_returns_failure_when_build_raises(self, tmp_path: Path) -> None:
        backend = _StubBackend(kb_path=tmp_path, build_error=RuntimeError("boom"))
        result = await backend.test_connection()
        assert result.ok is False
        assert "boom" in result.message
        assert result.details.get("type") == "RuntimeError"


class TestChromaTestConnection:
    """Chroma override verifies the kb_path is writable + client opens."""

    @pytest.mark.asyncio
    async def test_returns_ok_for_writable_path(self, tmp_path: Path) -> None:
        kb_path = tmp_path / "kb_chroma_ok"
        backend = ChromaBackend(kb_name="kb_chroma_ok", kb_path=kb_path)
        try:
            result = await backend.test_connection()
        finally:
            await backend.teardown()
        assert result.ok is True
        assert "Chroma" in result.message
        assert result.details.get("path") == str(kb_path)

    @pytest.mark.asyncio
    async def test_returns_failure_for_unwritable_path(self, tmp_path: Path) -> None:
        # Drop a read-only parent directory so mkdir cannot create the
        # KB subdirectory inside it. ``chmod`` semantics differ on
        # Windows; gate the test on POSIX where 0o500 reliably blocks
        # writes for the current user.
        if os.name != "posix":
            pytest.skip("Permission semantics rely on POSIX chmod.")
        parent = tmp_path / "ro_parent"
        parent.mkdir()
        parent.chmod(0o500)
        kb_path = parent / "kb_chroma_fail"
        backend = ChromaBackend(kb_name="kb_chroma_fail", kb_path=kb_path)
        try:
            result = await backend.test_connection()
        finally:
            await backend.teardown()
            # Restore permissions so pytest's tmp_path cleanup succeeds.
            parent.chmod(0o700)
        assert result.ok is False
        assert "not writable" in result.message
        assert result.details.get("type") in {"PermissionError", "OSError"}


class TestOpenSearchTestConnection:
    """OpenSearch override pings ``cluster.info`` and maps errors."""

    def _make_backend(
        self,
        kb_path: Path,
        *,
        url: str = "https://example.local:9200",
        username: str | None = "admin",
        password: str | None = "secret",  # noqa: S107 — test fixture
    ) -> OpenSearchBackend:
        backend = OpenSearchBackend(
            kb_name="kb_os_test",
            kb_path=kb_path,
            backend_config={"index_name": "test_index"},
        )
        # Pre-populate resolved secrets so ``ensure_ready`` is a no-op.
        backend._resolved_url = url
        backend._resolved_username = username
        backend._resolved_password = password
        backend._secrets_resolved = True
        return backend

    @pytest.mark.asyncio
    async def test_returns_ok_when_cluster_info_succeeds(self, tmp_path: Path) -> None:
        backend = self._make_backend(tmp_path)
        fake_client = MagicMock()
        fake_client.info.return_value = {
            "cluster_name": "my-cluster",
            "version": {"number": "2.11.0"},
        }
        with (
            patch("opensearchpy.OpenSearch", return_value=fake_client),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch"),
        ):
            result = await backend.test_connection()
        assert result.ok is True
        assert "my-cluster" in result.message
        assert result.details.get("cluster_name") == "my-cluster"
        assert result.details.get("version") == "2.11.0"
        fake_client.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_auth_message_on_authentication_exception(self, tmp_path: Path) -> None:
        from opensearchpy.exceptions import AuthenticationException

        backend = self._make_backend(tmp_path)
        fake_client = MagicMock()
        fake_client.info.side_effect = AuthenticationException(401, "auth failed", {})
        with (
            patch("opensearchpy.OpenSearch", return_value=fake_client),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch"),
        ):
            result = await backend.test_connection()
        assert result.ok is False
        assert result.details.get("type") == "AuthenticationException"
        assert "Authentication failed" in result.message

    @pytest.mark.asyncio
    async def test_returns_authorization_message_on_authorization_exception(self, tmp_path: Path) -> None:
        from opensearchpy.exceptions import AuthorizationException

        backend = self._make_backend(tmp_path)
        fake_client = MagicMock()
        fake_client.info.side_effect = AuthorizationException(403, "forbidden", {})
        with (
            patch("opensearchpy.OpenSearch", return_value=fake_client),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch"),
        ):
            result = await backend.test_connection()
        assert result.ok is False
        assert result.details.get("type") == "AuthorizationException"
        assert "Authorization failed" in result.message

    @pytest.mark.asyncio
    async def test_returns_connection_message_on_connection_error(self, tmp_path: Path) -> None:
        from opensearchpy.exceptions import ConnectionError as OSConnectionError

        backend = self._make_backend(tmp_path)
        fake_client = MagicMock()
        fake_client.info.side_effect = OSConnectionError("N/A", "refused", Exception("refused"))
        with (
            patch("opensearchpy.OpenSearch", return_value=fake_client),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch"),
        ):
            result = await backend.test_connection()
        assert result.ok is False
        assert result.details.get("type") == "ConnectionError"
        assert "Could not reach the cluster" in result.message

    @pytest.mark.asyncio
    async def test_returns_ssl_message_on_ssl_error(self, tmp_path: Path) -> None:
        from opensearchpy.exceptions import SSLError as OSSSLError

        backend = self._make_backend(tmp_path)
        fake_client = MagicMock()
        fake_client.info.side_effect = OSSSLError("N/A", "ssl bad", Exception("ssl bad"))
        with (
            patch("opensearchpy.OpenSearch", return_value=fake_client),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch"),
        ):
            result = await backend.test_connection()
        assert result.ok is False
        assert result.details.get("type") == "SSLError"
        assert "TLS handshake failed" in result.message

    @pytest.mark.asyncio
    async def test_returns_failure_when_url_secret_missing(self, tmp_path: Path) -> None:
        # Force ensure_ready to fail by leaving the resolved URL unset.
        backend = OpenSearchBackend(
            kb_name="kb_os_missing_url",
            kb_path=tmp_path,
            backend_config={"index_name": "idx"},
        )
        # ``_resolve_secrets`` raises ValueError when the URL variable is
        # not configured; do not pre-populate ``_secrets_resolved`` so
        # the resolution path actually runs.
        result = await backend.test_connection()
        assert result.ok is False
        # Either ConfigError (mapped from ValueError) or the type of the
        # failure raised inside variable_service — both are acceptable
        # so long as ``ok`` is False and there is a user-readable message.
        assert result.message
