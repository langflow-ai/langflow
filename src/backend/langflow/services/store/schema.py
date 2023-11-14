from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, validator


class TagResponse(BaseModel):
    id: UUID
    name: Optional[str]


class UsersLikesResponse(BaseModel):
    likes_count: Optional[int]
    liked_by_user: Optional[bool]


class ComponentResponse(BaseModel):
    id: UUID
    status: Optional[str]
    sort: Optional[int]
    user_name: Optional[str]
    date_created: Optional[datetime]
    user_updated: Optional[UUID]
    date_updated: Optional[datetime]
    is_component: Optional[bool]
    name: Optional[str]
    description: Optional[str]
    data: Optional[dict]
    tags: Optional[List[int]]
    liked_by_count: Optional[int]
    downloads_count: Optional[int]
    parent: Optional[UUID]
    metadata: Optional[dict]
    last_tested_version: Optional[str]


class TagsIdResponse(BaseModel):
    tags_id: Optional[TagResponse]


class ListComponentResponse(BaseModel):
    id: UUID
    name: Optional[str]
    description: Optional[str]
    liked_by_count: Optional[int]
    liked_by_user: Optional[bool]
    is_component: Optional[bool]
    metadata: Optional[dict]
    user_created: Optional[dict]
    tags: Optional[List[TagResponse]] = None
    downloads_count: Optional[int]
    last_tested_version: Optional[str]

    # tags comes as a TagsIdResponse but we want to return a list of TagResponse
    @validator("tags", pre=True)
    def tags_to_list(cls, v):
        # Check if all values are have id and name
        # if so, return v else transform to TagResponse
        if not v:
            return v
        if all(["id" in tag and "name" in tag for tag in v]):
            return v
        else:
            return [TagResponse(**tag.get("tags_id")) for tag in v if tag.get("tags_id")]


class ListComponentResponseModel(BaseModel):
    count: int
    authorized: bool
    results: Optional[List[ListComponentResponse]]


class DownloadComponentResponse(BaseModel):
    id: UUID
    name: Optional[str]
    description: Optional[str]
    data: Optional[dict]
    is_component: Optional[bool]
    metadata: Optional[dict]
    downloads_count: Optional[int]


class StoreComponentCreate(BaseModel):
    name: str
    description: Optional[str]
    data: dict
    tags: Optional[List[str]]
    parent: Optional[UUID]
    is_component: Optional[bool]
    metadata: Optional[dict]
    last_tested_version: Optional[str]
