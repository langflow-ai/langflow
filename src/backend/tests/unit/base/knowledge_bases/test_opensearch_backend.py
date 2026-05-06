"""Unit tests for ``OpenSearchBackend`` defaults.

Pins the default vector-field name to ``chunk_embedding`` so the KB
backend stays aligned with the canvas OpenSearch component, which
defaults to the same field. A regression here re-introduces the
``Field 'chunk_embedding' is not knn_vector type`` failure when a
KB-ingested index is wired into the canvas component without a
manual ``Vector Field Name`` override.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from lfx.base.knowledge_bases.backends import OpenSearchBackend
from lfx.base.knowledge_bases.backends.opensearch import (
    DEFAULT_TEXT_FIELD,
    DEFAULT_VECTOR_FIELD,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make_backend(
    kb_path: Path,
    backend_config: dict | None = None,
) -> OpenSearchBackend:
    backend = OpenSearchBackend(
        kb_name="kb_os_defaults",
        kb_path=kb_path,
        backend_config=backend_config or {"index_name": "test_index"},
    )
    # Pre-populate resolved secrets so ``ensure_ready`` is a no-op and
    # ``_build_vector_store`` can run without touching variable_service.
    backend._resolved_url = "https://example.local:9200"
    backend._resolved_username = "admin"
    backend._resolved_password = "secret"  # noqa: S105 — test fixture  # pragma: allowlist secret
    backend._secrets_resolved = True
    return backend


class TestOpenSearchBackendVectorFieldDefault:
    """Default field names must match the canvas OpenSearch component."""

    def test_default_vector_field_is_chunk_embedding(self) -> None:
        # The canvas OpenSearch component defaults to ``chunk_embedding``;
        # the KB backend must agree so a KB-ingested index queries cleanly
        # from the canvas component without a manual override.
        assert DEFAULT_VECTOR_FIELD == "chunk_embedding"

    def test_build_vector_store_uses_chunk_embedding_by_default(self, tmp_path: Path) -> None:
        backend = _make_backend(tmp_path)
        fake_wrapper = MagicMock(name="OpenSearchVectorSearch")
        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch(
                "langchain_community.vectorstores.OpenSearchVectorSearch",
                fake_wrapper,
            ),
        ):
            _ = backend.vector_store

        fake_wrapper.assert_called_once()
        kwargs = fake_wrapper.call_args.kwargs
        assert kwargs["vector_field"] == "chunk_embedding"
        assert kwargs["text_field"] == DEFAULT_TEXT_FIELD
        # Sanity-check the field the backend stashes for iter/count helpers
        # so the in-memory state agrees with what was sent to LangChain.
        assert backend._os_vector_field == "chunk_embedding"

    def test_build_vector_store_honours_backend_config_override(self, tmp_path: Path) -> None:
        # Operators with a legacy ``vector_field`` index (or any custom
        # name) must still be able to override via backend_config.
        backend = _make_backend(
            tmp_path,
            backend_config={"index_name": "test_index", "vector_field": "embedding"},
        )
        fake_wrapper = MagicMock(name="OpenSearchVectorSearch")
        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch(
                "langchain_community.vectorstores.OpenSearchVectorSearch",
                fake_wrapper,
            ),
        ):
            _ = backend.vector_store

        kwargs = fake_wrapper.call_args.kwargs
        assert kwargs["vector_field"] == "embedding"
        assert backend._os_vector_field == "embedding"


@pytest.mark.parametrize(
    ("config_value", "expected"),
    [
        (None, "chunk_embedding"),
        ("", "chunk_embedding"),
        ("custom_vec", "custom_vec"),
    ],
)
def test_vector_field_resolution_table(tmp_path: Path, config_value: str | None, expected: str) -> None:
    """Empty / missing config falls back to the default; truthy wins."""
    cfg: dict = {"index_name": "test_index"}
    if config_value is not None:
        cfg["vector_field"] = config_value
    backend = _make_backend(tmp_path, backend_config=cfg)
    fake_wrapper = MagicMock(name="OpenSearchVectorSearch")
    with (
        patch("opensearchpy.OpenSearch", return_value=MagicMock()),
        patch(
            "langchain_community.vectorstores.OpenSearchVectorSearch",
            fake_wrapper,
        ),
    ):
        _ = backend.vector_store

    assert fake_wrapper.call_args.kwargs["vector_field"] == expected
