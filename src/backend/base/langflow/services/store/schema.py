from uuid import UUID

from pydantic import BaseModel, field_validator


class TagResponse(BaseModel):
    id: UUID
    name: str | None


class UsersLikesResponse(BaseModel):
    likes_count: int | None
    liked_by_user: bool | None


class CreateComponentResponse(BaseModel):
    id: UUID


class TagsIdResponse(BaseModel):
    tags_id: TagResponse | None


class ListComponentResponse(BaseModel):
    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    liked_by_count: int | None = None
    liked_by_user: bool | None = None
    is_component: bool | None = None
    metadata: dict | None = {}
    user_created: dict | None = {}
    tags: list[TagResponse] | None = None
    downloads_count: int | None = None
    last_tested_version: str | None = None
    private: bool | None = None

    # tags comes as a TagsIdResponse but we want to return a list of TagResponse
    @field_validator("tags", mode="before")
    @classmethod
    def tags_to_list(cls, v):
        # Check if all values are have id and name
        # if so, return v else transform to TagResponse
        if not v:
            return v
        if all("id" in tag and "name" in tag for tag in v):
            return v
        return [TagResponse(**tag.get("tags_id")) for tag in v if tag.get("tags_id")]


class ListComponentResponseModel(BaseModel):
    count: int | None = 0
    authorized: bool
    results: list[ListComponentResponse] | None


class DownloadComponentResponse(BaseModel):
    id: UUID
    name: str | None
    description: str | None
    data: dict | None
    is_component: bool | None
    metadata: dict | None = {}


class StoreComponentCreate(BaseModel):
    name: str
    description: str | None
    data: dict
    tags: list[str] | None
    parent: UUID | None = None
    is_component: bool | None
    last_tested_version: str | None = None
    private: bool | None = True
