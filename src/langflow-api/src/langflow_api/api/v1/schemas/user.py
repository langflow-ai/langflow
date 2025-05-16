from langflow.services.database.models.user import UserRead
from pydantic import BaseModel


class UsersResponse(BaseModel):
    total_count: int
    users: list[UserRead]
