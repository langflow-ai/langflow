from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, field_serializer, field_validator
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow

MAX_TEXT_LENGTH=99999

class VertexBuildBase(SQLModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = Field(nullable=False)
    data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    artifacts: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    params: Optional[str] = Field(nullable=True)
    valid: bool = Field(nullable=False)
    flow_id: UUID = Field(foreign_key="flow.id")

    # Needed for Column(JSON)
    class Config:
        arbitrary_types_allowed = True

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            value = UUID(value)
        return value

    @field_serializer("timestamp")
    @classmethod
    def serialize_timestamp(cls, value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value




    @field_serializer("data")
    def serialize_data(self, data: dict) -> dict:
        truncated_data = truncate_long_strings(data)
        return truncated_data


    @field_serializer("artifacts")
    def serialize_artifacts(self, data) -> dict:
        truncated_data = truncate_long_strings(data)
        return truncated_data



class VertexBuildTable(VertexBuildBase, table=True):  # type: ignore
    __tablename__ = "vertex_build"
    build_id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    flow: "Flow" = Relationship(back_populates="vertex_builds")


class VertexBuildMapModel(BaseModel):
    vertex_builds: dict[str, list[VertexBuildTable]]

    @classmethod
    def from_list_of_dicts(cls, vertex_build_dicts: list[VertexBuildTable]):
        vertex_build_map: dict[str, list[VertexBuildTable]] = {}
        for vertex_build in vertex_build_dicts:
            if vertex_build.id not in vertex_build_map:
                vertex_build_map[vertex_build.id] = []
            vertex_build_map[vertex_build.id].append(vertex_build)
        return cls(vertex_builds=vertex_build_map)


def truncate_long_strings(data, max_length=MAX_TEXT_LENGTH):
    """
    Recursively traverse the dictionary or list and truncate strings longer than max_length.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and len(value) > max_length:
                data[key] = value[:max_length] + '...'
            elif isinstance(value, (dict, list)):
                truncate_long_strings(value, max_length)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            if isinstance(item, str) and len(item) > max_length:
                data[index] = item[:max_length] + '...'
            elif isinstance(item, (dict, list)):
                truncate_long_strings(item, max_length)

    return data
