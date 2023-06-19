from fastapi import APIRouter, Depends
from langflow.models.user import User
from langflow.auth.auth import get_current_active_user

router = APIRouter()


@router.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
