from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import ValidationInfo, field_validator
from sqlmodel import JSON, Column, DateTime, Field, Relationship, SQLModel, func

from langflow.services.variable.constants import CATEGORY_GLOBAL, CREDENTIAL_TYPE, VALID_CATEGORIES

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def utc_now():
    return datetime.now(timezone.utc)


class VariableBase(SQLModel):
    name: str = Field(description="Name of the variable")
    value: str = Field(description="Encrypted value of the variable")
    default_fields: list[str] | None = Field(default=[], sa_column=Column(JSON))
    type: str | None = Field(None, description="Type of the variable")
    category: str | None = Field(
        default=CATEGORY_GLOBAL, description="Category of the variable (global, settings, llm_settings, etc.)"
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None):
        if v is not None and v not in VALID_CATEGORIES:
            msg = f"Category must be one of: {', '.join(VALID_CATEGORIES)}"
            raise ValueError(msg)
        return v


class Variable(VariableBase, table=True):  # type: ignore[call-arg]
    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the variable",
    )
    # name is unique per user
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the variable",
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last update time of the variable",
    )
    default_fields: list[str] | None = Field(sa_column=Column(JSON))
    # foreign key to user table
    user_id: UUID = Field(description="User ID associated with this variable", foreign_key="user.id")
    user: "User" = Relationship(back_populates="variables")


class VariableCreate(VariableBase):
    created_at: datetime | None = Field(default_factory=utc_now, description="Creation time of the variable")
    updated_at: datetime | None = Field(default_factory=utc_now, description="Creation time of the variable")


class VariableRead(SQLModel):
    id: UUID
    name: str | None = Field(None, description="Name of the variable")
    type: str | None = Field(None, description="Type of the variable")
    value: str | None = Field(None, description="Encrypted value of the variable")
    default_fields: list[str] | None = Field(None, description="Default fields for the variable")
    category: str | None = Field(default=CATEGORY_GLOBAL, description="Category of the variable")

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str, info: ValidationInfo):
        if info.data.get("type") == CREDENTIAL_TYPE:
            return None
        return value


class VariableUpdate(SQLModel):
    id: UUID  # Include the ID for updating
    name: str | None = Field(None, description="Name of the variable")
    value: str | None = Field(None, description="Encrypted value of the variable")
    default_fields: list[str] | None = Field(None, description="Default fields for the variable")
    category: str | None = Field(None, description="Category of the variable")
    type: str | None = Field(None, description="Type of the variable")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None):
        if v is not None and v not in VALID_CATEGORIES:
            msg = f"Category must be one of: {', '.join(VALID_CATEGORIES)}"
            raise ValueError(msg)
        return v
