from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID


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
    likes_count: Optional[List[UUID]]
    parent: Optional[UUID]


class StoreComponentCreate(BaseModel):
    name: str
    description: Optional[str]
    data: dict
    tags: Optional[List[str]]
    parent: Optional[UUID]
    is_component: Optional[bool]
