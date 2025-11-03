from fastapi import APIRouter
from lfx.base.models.unified_models import get_embedding_model_options, get_language_model_options

from langflow.api.utils import CurrentActiveUser

router = APIRouter(prefix="/model_options", tags=["Model Options"])


@router.get("/language", status_code=200)
async def get_language_model_options_endpoint(
    current_user: CurrentActiveUser,
):
    """Get language model options filtered by user's enabled providers and models."""
    return get_language_model_options(user_id=current_user.id)


@router.get("/embedding", status_code=200)
async def get_embedding_model_options_endpoint(
    current_user: CurrentActiveUser,
):
    """Get embedding model options filtered by user's enabled providers and models."""
    return get_embedding_model_options(user_id=current_user.id)
