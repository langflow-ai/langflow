from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PathSettings(BaseModel):
    """Filesystem paths Langflow reads from and writes to."""

    config_dir: str | None = None
    """Base directory for Langflow data (db, logs, caches)."""

    knowledge_bases_dir: str | None = "~/.langflow/knowledge_bases"
    """The directory to store knowledge bases."""

    kb_disk_reconcile_enabled: bool = False
    """Whether startup scans ``knowledge_bases_dir`` for KB directories lacking a DB row.

    The ``knowledge_base`` table is the sole authority for KB metadata; the on-disk
    ``embedding_metadata.json`` sidecar is no longer written or read by any steady-state
    code path. This reconcile exists only to adopt directories left by a Langflow version
    that predates that change, so it is off by default and pays no boot cost.

    Set ``LANGFLOW_KB_DISK_RECONCILE_ENABLED=true`` to re-enable it at startup, or run it
    once on demand with ``langflow reconcile-kb-from-disk`` (which also accepts
    ``--dry-run``). It never deletes anything and is idempotent."""

    kb_allowed_folder_roots: list[str] = []
    """Allow-list of directories the folder-ingestion endpoint may read from.

    Comma-separated when set via env (``LANGFLOW_KB_ALLOWED_FOLDER_ROOTS``),
    e.g. ``/srv/docs,/data/shared``. Empty by default — operators must opt in.
    ``POST /api/v1/knowledge_bases/{kb_name}/ingest/folder`` refuses to walk any
    directory that is not equal to or inside one of these roots; symlink escapes
    are blocked because the path is resolved before the containment check. Leave
    empty in multi-tenant cloud deployments to refuse arbitrary-path access."""

    kb_folder_max_file_size_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    """Maximum file size accepted by Knowledge Base folder ingestion.

    Set ``LANGFLOW_KB_FOLDER_MAX_FILE_SIZE_BYTES`` to an operator-chosen positive
    byte count. Public ingestion routes inject this value into ``FolderSource``;
    request bodies cannot raise or lower the server-owned limit."""

    directory_component_allowed_roots: list[str] = []
    """Additional directories the legacy Directory component may read from.

    The component always allows paths equal to or inside the process working
    directory. Operators can set ``LANGFLOW_DIRECTORY_COMPONENT_ALLOWED_ROOTS``
    as a comma-separated list for other trusted read-only content roots. Parent
    traversal and symlink escapes are still blocked after canonicalization."""

    @field_validator("config_dir", mode="before")
    @classmethod
    def set_langflow_dir(cls, value: Any) -> str:
        if not value:
            from platformdirs import user_cache_dir

            app_name = "langflow"
            app_author = "langflow"

            cache_dir = user_cache_dir(app_name, app_author)

            value = Path(cache_dir)
            value.mkdir(parents=True, exist_ok=True)

        if isinstance(value, str):
            value = Path(value)
        value = value.resolve()
        if not value.exists():
            value.mkdir(parents=True, exist_ok=True)

        return str(value)
