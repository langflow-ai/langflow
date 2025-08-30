from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Text
from sqlmodel import Field, Index, SQLModel, UniqueConstraint

from langflow.schema.serialize import UUIDstr


class Component(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "components"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    component_path: str = Field(nullable=False, index=True)  # Just the component name for verification
    folder: str = Field(nullable=False, index=True)  # Folder/category (e.g., "search", "agents", etc.)
    version: str = Field(nullable=False, index=True)
    code: str = Field(sa_type=Text, nullable=False)  # Full component source code - use Text for large content
    signature: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("folder", "component_path", "version", name="uq_folder_component_version"),
        Index("idx_components_signature", "signature"),
    )
