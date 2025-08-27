from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import NoResultFound

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.variable.model import VariableCreate, VariableRead, VariableUpdate
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE, VALID_CATEGORIES
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(prefix="/variables", tags=["Variables"])


@router.post("/", response_model=VariableRead, status_code=201)
async def create_variable(
    *,
    session: DbSession,
    variable: VariableCreate,
    current_user: CurrentActiveUser,
):
    """Create a new variable."""
    variable_service = get_variable_service()
    if not variable.name and not variable.value:
        raise HTTPException(status_code=400, detail="Variable name and value cannot be empty")

    if not variable.name:
        raise HTTPException(status_code=400, detail="Variable name cannot be empty")

    if not variable.value:
        raise HTTPException(status_code=400, detail="Variable value cannot be empty")

    if variable.name in await variable_service.list_variables(user_id=current_user.id, session=session):
        raise HTTPException(status_code=400, detail="Variable name already exists")
    try:
        return await variable_service.create_variable(
            user_id=current_user.id,
            name=variable.name,
            value=variable.value,
            default_fields=variable.default_fields or [],
            type_=variable.type or CREDENTIAL_TYPE,
            session=session,
            category=variable.category,
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[VariableRead], status_code=200)
async def read_variables(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Read all variables."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)
    try:
        return await variable_service.get_all(user_id=current_user.id, session=session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/category/{category}", response_model=list[VariableRead], status_code=200)
async def read_variables_by_category(
    *,
    session: DbSession,
    category: str,
    current_user: CurrentActiveUser,
):
    """Read all variables for a specific category."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)

    normalized_category = category.lower()
    category_mapping = {cat.lower(): cat for cat in VALID_CATEGORIES}

    if normalized_category not in category_mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}",
        )

    correct_category = category_mapping[normalized_category]

    try:
        return await variable_service.get_by_category(
            user_id=current_user.id, category=correct_category, session=session
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{variable_id}", response_model=VariableRead, status_code=200)
async def update_variable(
    *,
    session: DbSession,
    variable_id: UUID,
    variable: VariableUpdate,
    current_user: CurrentActiveUser,
):
    """Update a variable."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)
    try:
        return await variable_service.update_variable_fields(
            user_id=current_user.id,
            variable_id=variable_id,
            variable=variable,
            session=session,
        )
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail="Variable not found") from e

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{variable_id}", status_code=204)
async def delete_variable(
    *,
    session: DbSession,
    variable_id: UUID,
    current_user: CurrentActiveUser,
) -> None:
    """Delete a variable."""
    variable_service = get_variable_service()
    try:
        await variable_service.delete_variable_by_id(user_id=current_user.id, variable_id=variable_id, session=session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# @router.get("/enabled_providers", status_code=200)
# async def get_enabled_providers(
#     *,
#     session: DbSession,
#     current_user: CurrentActiveUser,
#     providers: list[str] = Query(default=[]),
# ):
#     """Get enabled providers for the current user."""
#     from langflow.base.models.unified_models import get_model_provider_variable_mapping
#     from langflow.services.variable.constants import CATEGORY_LLM

#     variable_service = get_variable_service()
#     if not isinstance(variable_service, DatabaseVariableService):
#         msg = "Variable service is not an instance of DatabaseVariableService"
#         raise TypeError(msg)
#     try:
#         # Get all LLM category variables for the user
#         variables = await variable_service.get_by_category(
#             user_id=current_user.id, category=CATEGORY_LLM, session=session
#         )
#         if not variables:
#             return {
#                 "enabled_providers": [],
#                 "provider_status": {},
#             }
#         variable_names = {variable.name for variable in variables if variable}

#         # Get the provider-variable mapping
#         provider_variable_map = get_model_provider_variable_mapping()

#         enabled_providers = []
#         provider_status = {}

#         for provider, var_name in provider_variable_map.items():
#             is_enabled = var_name in variable_names
#             provider_status[provider] = is_enabled
#             if is_enabled:
#                 enabled_providers.append(provider)

#         result = {
#             "enabled_providers": enabled_providers,
#             "provider_status": provider_status,
#         }

#         if providers:
#             # Filter enabled_providers and provider_status by requested providers
#             filtered_enabled = [p for p in result["enabled_providers"] if p in providers]
#             filtered_status = {p: v for p, v in result["provider_status"].items() if p in providers}
#             return {
#                 "enabled_providers": filtered_enabled,
#                 "provider_status": filtered_status,
#             }
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e)) from e
