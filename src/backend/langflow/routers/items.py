from fastapi import APIRouter, Depends
from ..models.user import User
from ..auth.auth import get_current_active_user

router = APIRouter()


@router.get("/users/me/items/")
async def read_own_items(
  current_user: User = Depends(get_current_active_user)
):
    return [{"item_id": "Foo", "owner": current_user.username}]
