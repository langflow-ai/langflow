from fastapi import APIRouter, Depends
from ..models.user import User
from ..auth.auth import get_current_active_user

router = APIRouter()


@router.get("/users/all/")
async def read_own_items(
  current_user: User = Depends(get_current_active_user)
):
    return [
      {
        "item_id": "my_id",
        "owner": current_user.username
      }
    ]
