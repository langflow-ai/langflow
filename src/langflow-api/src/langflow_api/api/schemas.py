from pathlib import Path
from uuid import UUID

from pydantic import BaseModel


class UploadFileResponse(BaseModel):
    """File upload response schema."""

    id: UUID
    name: str
    path: Path
    size: int
    provider: str | None = None
