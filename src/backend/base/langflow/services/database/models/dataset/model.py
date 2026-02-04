from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, UniqueConstraint, func

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def utc_now():
    return datetime.now(timezone.utc)


# Dataset Models
class DatasetBase(SQLModel):
    name: str = Field(description="Name of the dataset", index=True)
    description: str | None = Field(default=None, description="Description of the dataset")


class Dataset(DatasetBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "dataset"
    __table_args__ = (UniqueConstraint("user_id", "name", name="unique_dataset_name_per_user"),)

    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the dataset",
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the dataset",
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last update time of the dataset",
    )
    user_id: UUID = Field(description="User ID associated with this dataset", foreign_key="user.id")
    user: "User" = Relationship(back_populates="datasets")
    items: list["DatasetItem"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )


class DatasetCreate(DatasetBase):
    pass


class DatasetRead(SQLModel):
    id: UUID
    name: str
    description: str | None = None
    user_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    item_count: int = 0


class DatasetReadWithItems(DatasetRead):
    items: list["DatasetItemRead"] = []


class DatasetUpdate(SQLModel):
    name: str | None = None
    description: str | None = None


# DatasetItem Models
class DatasetItemBase(SQLModel):
    input: str = Field(description="Input data as JSON string")
    expected_output: str = Field(description="Expected output data as JSON string")
    order: int = Field(default=0, description="Order of the item in the dataset")


class DatasetItem(DatasetItemBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "datasetitem"

    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the dataset item",
    )
    dataset_id: UUID = Field(
        description="Dataset ID this item belongs to",
        foreign_key="dataset.id",
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the dataset item",
    )
    dataset: Dataset = Relationship(back_populates="items")


class DatasetItemCreate(DatasetItemBase):
    pass


class DatasetItemRead(SQLModel):
    id: UUID
    dataset_id: UUID
    input: str
    expected_output: str
    order: int
    created_at: datetime | None = None


class DatasetItemUpdate(SQLModel):
    input: str | None = None
    expected_output: str | None = None
    order: int | None = None
