from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TeamTemplateCreate(BaseModel):
    source_flow_id: UUID
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    category: str = Field(default="all-templates", min_length=1, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("name", "category")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            msg = "Value must not be blank"
            raise ValueError(msg)
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip() for tag in value if tag.strip()))


class TeamTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    tags: list[str] | None = Field(default=None, max_length=10)
    refresh_from_source: bool = False

    @field_validator("name", "category")
    @classmethod
    def strip_optional_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            msg = "Value must not be blank"
            raise ValueError(msg)
        return value

    @field_validator("tags")
    @classmethod
    def validate_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(dict.fromkeys(tag.strip() for tag in value if tag.strip()))


class TeamTemplateSummary(BaseModel):
    id: UUID
    name: str
    description: str | None
    category: str
    tags: list[str]
    icon: str | None
    gradient: str | None
    source_flow_id: UUID | None
    workspace_id: UUID | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    source: str = "team"


class TeamTemplateRead(TeamTemplateSummary):
    flow_data: dict
    schema_version: int
    sanitizer_version: int


class TeamTemplateCreateResponse(TeamTemplateRead):
    cleared_fields: int


class TeamTemplateList(BaseModel):
    items: list[TeamTemplateSummary]
    total: int
    page: int
    page_size: int
