from pydantic import BaseModel
from langflow.services.database.models.user import UserRead

class UsersResponse(BaseModel):
    total_count: int
    users: list[UserRead]
