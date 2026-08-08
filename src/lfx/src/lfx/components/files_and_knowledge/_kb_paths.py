"""Shared helpers for Knowledge Base / Memory Base components.

Centralizes the KB root path lookup and embedding-metadata loading that
``ingestion.py``, ``retrieval.py`` and ``memory_retrieval.py`` would otherwise
duplicate.

Astra cloud guard: the user-facing Knowledge Base ingestion and retrieval
components are blocked in Astra cloud deployments via
``raise_error_if_astra_cloud_disable_component``. Memory Base is a runtime-
managed feature (auto-provisioned alongside flows) and is intentionally NOT
gated here; the Astra check stays at each component's entry point so we keep
the policy decision close to the UX rather than baked into a shared loader.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cryptography.fernet import InvalidToken
from langflow.services.auth.utils import decrypt_api_key

from lfx.log.logger import logger
from lfx.services.deps import get_settings_service

_KNOWLEDGE_BASES_ROOT_PATH: Path | None = None


class KBKeyDecryptError(Exception):
    """The stored embedding API key could not be decrypted.

    Raised when ``load_kb_metadata`` is called with ``require_api_key=True``
    and the Fernet decrypt fails — almost always because the server's
    SECRET_KEY changed after the key was stored.
    """


def get_knowledge_bases_root_path() -> Path:
    """Lazily resolve the configured KB root directory."""
    global _KNOWLEDGE_BASES_ROOT_PATH  # noqa: PLW0603
    if _KNOWLEDGE_BASES_ROOT_PATH is None:
        settings = get_settings_service().settings
        knowledge_directory = settings.knowledge_bases_dir
        if not knowledge_directory:
            msg = "Knowledge bases directory is not set in the settings."
            raise ValueError(msg)
        _KNOWLEDGE_BASES_ROOT_PATH = Path(knowledge_directory).expanduser()
    return _KNOWLEDGE_BASES_ROOT_PATH


def reset_knowledge_bases_root_path_cache() -> None:
    """Clear the cached KB root path. Intended for tests that mutate settings."""
    global _KNOWLEDGE_BASES_ROOT_PATH  # noqa: PLW0603
    _KNOWLEDGE_BASES_ROOT_PATH = None


def load_kb_metadata(
    kb_path: Path,
    *,
    log_label: str,
    require_api_key: bool = False,
) -> dict[str, Any]:
    """Load ``embedding_metadata.json`` from a KB directory.

    Returns ``{}`` on missing file / invalid JSON. ``log_label`` is used in log
    messages instead of the on-disk path so usernames (sometimes emails) are
    not leaked into log streams.

    When *require_api_key* is ``True`` and the stored ``api_key`` cannot be
    decrypted (typically a SECRET_KEY mismatch), raises ``KBKeyDecryptError``
    instead of silently returning ``api_key=None``.  Callers that only need
    non-secret metadata (listing, inspection) should leave it ``False``.
    """
    metadata: dict[str, Any] = {}
    metadata_file = kb_path / "embedding_metadata.json"
    if not metadata_file.exists():
        logger.warning("Embedding metadata file not found for %s", log_label)
        return metadata

    try:
        with metadata_file.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
    except json.JSONDecodeError:
        logger.error("Error decoding embedding metadata JSON for %s", log_label)
        return {}

    if metadata.get("api_key"):
        try:
            metadata["api_key"] = decrypt_api_key(metadata["api_key"], get_settings_service())
        except (InvalidToken, TypeError, ValueError) as e:
            if require_api_key:
                msg = (
                    f"Cannot decrypt the stored embedding API key for {log_label}. "
                    "This usually means the server's SECRET_KEY changed after the "
                    "key was saved. To recover, supply the embedding provider API "
                    "key on the component's 'Embedding Provider API Key' input and "
                    "re-run ingestion — the key will be re-encrypted with the "
                    "current SECRET_KEY."
                )
                raise KBKeyDecryptError(msg) from e
            logger.warning("Could not decrypt API key for %s (non-critical path). Error: %s", log_label, e)
            metadata["api_key"] = None
    return metadata
