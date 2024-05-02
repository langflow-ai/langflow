from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def utc_now():
    return datetime.now(timezone.utc)


class VariableBase(SQLModel):
    name: str = Field(description="Name of the variable")
    value: str = Field(description="Encrypted value of the variable")
    default_fields: Optional[List[str]] = Field(sa_column=Column(JSON))
    type: Optional[str] = Field(None, description="Type of the variable")


class Variable(VariableBase, table=True):
    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the variable",
    )
    # name is unique per user
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the variable",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last update time of the variable",
    )
    default_fields: Optional[List[str]] = Field(sa_column=Column(JSON))
    # foreign key to user table
    user_id: UUID = Field(description="User ID associated with this variable", foreign_key="user.id")
    user: "User" = Relationship(back_populates="variables")


class VariableCreate(VariableBase):
    created_at: Optional[datetime] = Field(default_factory=utc_now, description="Creation time of the variable")

    updated_at: Optional[datetime] = Field(default_factory=utc_now, description="Creation time of the variable")


class VariableRead(SQLModel):
    id: UUID
    name: Optional[str] = Field(None, description="Name of the variable")
    type: Optional[str] = Field(None, description="Type of the variable")
    default_fields: Optional[List[str]] = Field(None, description="Default fields for the variable")


class VariableUpdate(SQLModel):
    id: UUID  # Include the ID for updating
    name: Optional[str] = Field(None, description="Name of the variable")
    value: Optional[str] = Field(None, description="Encrypted value of the variable")
    default_fields: Optional[List[str]] = Field(None, description="Default fields for the variable")
