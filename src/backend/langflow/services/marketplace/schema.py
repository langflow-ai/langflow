from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List


class ComponentResponse(BaseModel):
    name: str
    description: Optional[str]
    id: int
    status: Optional[str]
    sort: Optional[int]
    user_created: Optional[int]
    date_created: Optional[datetime]
    user_updated: Optional[int]
    date_updated: Optional[datetime]
    is_component: bool
    likes: Optional[int]
    tags: Optional[List[str]]
    data: Optional[str]
    documentation: Optional[str]
