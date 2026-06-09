from pydantic import BaseModel


class StorageSettings(BaseModel):
    """File storage backend (local filesystem or object storage)."""

    storage_type: str = "local"
    """Storage type for file storage. Defaults to 'local'. Supports 'local' and 's3'."""
    object_storage_bucket_name: str | None = "langflow-bucket"
    """Object storage bucket name for file storage. Defaults to 'langflow-bucket'."""
    object_storage_prefix: str | None = "files"
    """Object storage prefix for file storage. Defaults to 'files'."""
    object_storage_tags: dict[str, str] | None = None
    """Object storage tags for file storage."""
