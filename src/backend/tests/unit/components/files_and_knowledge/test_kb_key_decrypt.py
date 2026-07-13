"""Tests for KB embedding-key decrypt failure behavior.

Verifies that:
1. A decrypt failure raises ``KBKeyDecryptError`` when ``require_api_key=True``.
2. A component-supplied key bypasses the stored key with no error.
3. Metadata reads that do not need the key (``require_api_key=False``) stay quiet.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from cryptography.fernet import InvalidToken
from lfx.components.files_and_knowledge._kb_paths import (
    KBKeyDecryptError,
    load_kb_metadata,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_metadata(kb_path: Path, *, api_key: str | None = "encrypted-blob") -> Path:
    metadata = {
        "embedding_provider": "OpenAI",
        "embedding_model": "text-embedding-3-small",
        "model_selection": {
            "name": "text-embedding-3-small",
            "provider": "OpenAI",
            "metadata": {"embedding_class": "OpenAIEmbeddings"},
        },
        "chunk_size": 1000,
        "api_key": api_key,
        "api_key_used": api_key is not None,
    }
    metadata_file = kb_path / "embedding_metadata.json"
    metadata_file.write_text(json.dumps(metadata))
    return metadata_file


class TestLoadKbMetadataDecrypt:
    """Unit tests for ``load_kb_metadata`` decrypt-failure paths."""

    @pytest.fixture(autouse=True)
    def _kb_dir(self, tmp_path):
        self.kb_path = tmp_path / "user" / "my_kb"
        self.kb_path.mkdir(parents=True)

    def test_require_api_key_raises_on_decrypt_failure(self):
        _write_metadata(self.kb_path)
        with (
            patch(
                "lfx.components.files_and_knowledge._kb_paths.decrypt_api_key",
                side_effect=InvalidToken,
            ),
            pytest.raises(KBKeyDecryptError, match="SECRET_KEY"),
        ):
            load_kb_metadata(self.kb_path, log_label="test-kb", require_api_key=True)

    def test_no_require_returns_none_on_decrypt_failure(self):
        """Non-critical reads (listing/inspection) get api_key=None, no raise."""
        _write_metadata(self.kb_path)
        with patch(
            "lfx.components.files_and_knowledge._kb_paths.decrypt_api_key",
            side_effect=InvalidToken,
        ):
            result = load_kb_metadata(self.kb_path, log_label="test-kb", require_api_key=False)
        assert result["api_key"] is None
        assert result["embedding_provider"] == "OpenAI"

    def test_successful_decrypt_returns_plaintext(self):
        _write_metadata(self.kb_path)
        with patch(
            "lfx.components.files_and_knowledge._kb_paths.decrypt_api_key",
            return_value="sk-real-key",
        ):
            result = load_kb_metadata(self.kb_path, log_label="test-kb", require_api_key=True)
        assert result["api_key"] == "sk-real-key"  # pragma: allowlist secret

    def test_no_stored_key_no_raise(self):
        """KB created without an api_key never triggers decrypt at all."""
        _write_metadata(self.kb_path, api_key=None)
        result = load_kb_metadata(self.kb_path, log_label="test-kb", require_api_key=True)
        assert result.get("api_key") is None

    def test_missing_metadata_file_returns_empty(self):
        result = load_kb_metadata(self.kb_path, log_label="test-kb", require_api_key=True)
        assert result == {}

    def test_invalid_json_returns_empty(self):
        (self.kb_path / "embedding_metadata.json").write_text("{bad json")
        result = load_kb_metadata(self.kb_path, log_label="test-kb", require_api_key=True)
        assert result == {}

    def test_error_message_names_kb(self):
        _write_metadata(self.kb_path)
        with (
            patch(
                "lfx.components.files_and_knowledge._kb_paths.decrypt_api_key",
                side_effect=InvalidToken,
            ),
            pytest.raises(KBKeyDecryptError, match="test-kb"),
        ):
            load_kb_metadata(self.kb_path, log_label="test-kb", require_api_key=True)


class TestRetrievalPathDecryptRecovery:
    """Integration-style tests: retrieval with component-supplied key vs stored key."""

    @pytest.fixture(autouse=True)
    def _kb_dir(self, tmp_path):
        self.kb_path = tmp_path / "user" / "my_kb"
        self.kb_path.mkdir(parents=True)

    def test_component_key_bypasses_undecryptable_stored_key(self):
        """When require_api_key=False (component will supply), no raise even on bad stored key."""
        _write_metadata(self.kb_path)
        with patch(
            "lfx.components.files_and_knowledge._kb_paths.decrypt_api_key",
            side_effect=InvalidToken,
        ):
            result = load_kb_metadata(self.kb_path, log_label="test-kb", require_api_key=False)
        assert result["api_key"] is None
        assert result["embedding_provider"] == "OpenAI"
