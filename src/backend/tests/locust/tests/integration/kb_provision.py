"""Knowledge-base directory settings + local KB provisioning.

Points live settings ``knowledge_bases_dir`` at a temp root and creates the
KB directory/DB record expected by ingest/retrieve fixtures. Used by KB and
ensemble cases in ``test_subsystem_coverage``.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from langflow.api.utils import knowledge_base_service

from tests.locust.langflow_runtime.flows.defaults import DEFAULT_KB_NAME

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@contextmanager
def knowledge_bases_dir(root: Path) -> Iterator[Path]:
    """Point the live settings ``knowledge_bases_dir`` at ``root`` for the test.

    Uses the public settings + cache-reset path instead of patching the private
    ``_KNOWLEDGE_BASES_ROOT_PATH`` module global.
    """
    from lfx.components.files_and_knowledge._kb_paths import reset_knowledge_bases_root_path_cache
    from lfx.services.deps import get_settings_service

    settings = get_settings_service().settings
    previous = settings.knowledge_bases_dir
    settings.knowledge_bases_dir = str(root)
    reset_knowledge_bases_root_path_cache()
    try:
        yield root
    finally:
        settings.knowledge_bases_dir = previous
        reset_knowledge_bases_root_path_cache()


async def provision_local_kb(*, username: str, user_id: Any, root: Path, kb_name: str = DEFAULT_KB_NAME) -> Path:
    """Create KB directory + DB record under the configured knowledge-bases root."""
    kb_path = root / username / kb_name
    kb_path.mkdir(parents=True, exist_ok=True)
    metadata = {
        "embedding_provider": "HuggingFace",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "model_selection": {
            "name": "sentence-transformers/all-MiniLM-L6-v2",
            "provider": "HuggingFace",
            "metadata": {
                "embedding_class": "HuggingFaceEmbeddings",
                "param_mapping": {"model_name": "model"},
            },
        },
        "chunk_size": 200,
        "created_at": "2026-07-24T00:00:00Z",
    }
    (kb_path / "embedding_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    await knowledge_base_service.create_record(user_id=user_id, name=kb_name)
    return kb_path
