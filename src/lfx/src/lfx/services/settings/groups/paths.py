from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator


class PathSettings(BaseModel):
    """Filesystem paths Langflow reads from and writes to."""

    config_dir: str | None = None
    """Base directory for Langflow data (db, logs, caches)."""

    knowledge_bases_dir: str | None = "~/.langflow/knowledge_bases"
    """The directory to store knowledge bases."""

    kb_allowed_folder_roots: list[str] = []
    """Allow-list of directories the folder-ingestion endpoint may read from.

    Comma-separated when set via env (``LANGFLOW_KB_ALLOWED_FOLDER_ROOTS``),
    e.g. ``/srv/docs,/data/shared``. Empty by default — operators must opt in.
    ``POST /api/v1/knowledge_bases/{kb_name}/ingest/folder`` refuses to walk any
    directory that is not equal to or inside one of these roots; symlink escapes
    are blocked because the path is resolved before the containment check. Leave
    empty in multi-tenant cloud deployments to refuse arbitrary-path access."""

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
