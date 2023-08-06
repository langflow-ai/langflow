from langflow.services.database.models.base import SQLModelSerializable, SQLModel
from sqlmodel import Field
from typing import Optional
from datetime import datetime
import uuid


class Component(SQLModelSerializable, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    frontend_node_id: uuid.UUID = Field(index=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    python_code: Optional[str] = Field(default=None)
    return_type: Optional[str] = Field(default=None)
    is_disabled: bool = Field(default=False)
    is_read_only: bool = Field(default=False)
    create_at: datetime = Field(default_factory=datetime.utcnow)
    update_at: datetime = Field(default_factory=datetime.utcnow)


class ComponentModel(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    frontend_node_id: uuid.UUID = Field(default=uuid.uuid4())
    name: str = Field(default="")
    description: Optional[str] = None
    python_code: Optional[str] = None
    return_type: Optional[str] = None
    is_disabled: bool = False
    is_read_only: bool = False
