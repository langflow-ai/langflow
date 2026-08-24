"""Shared KB root-path helper for Knowledge Base / Memory Base components.

Only the root-directory lookup lives here now. The on-disk
``embedding_metadata.json`` sidecar this module used to read is gone: the
``knowledge_base`` row is the sole authority for a KB's embedding config,
backend routing, and stats, so components resolve all of that from the database
and touch the filesystem only when the resolved backend is local Chroma.

Astra cloud guard: the user-facing Knowledge Base ingestion and retrieval
components are blocked in Astra cloud deployments via
``raise_error_if_astra_cloud_disable_component``. Memory Base is a runtime-
managed feature (auto-provisioned alongside flows) and is intentionally NOT
gated here; the Astra check stays at each component's entry point so we keep
the policy decision close to the UX rather than baked into a shared loader.
"""

from __future__ import annotations

from pathlib import Path

from lfx.services.deps import get_settings_service

_KNOWLEDGE_BASES_ROOT_PATH: Path | None = None


def get_knowledge_bases_root_path() -> Path:
    """Lazily resolve the configured KB root directory.

    Only reached for local-Chroma knowledge bases — every other backend stores
    off-box and never asks for a path. Deployments that serve only remote vector
    stores therefore never hit the ``knowledge_bases_dir`` requirement.
    """
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
