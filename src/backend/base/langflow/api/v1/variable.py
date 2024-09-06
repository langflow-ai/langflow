from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session

from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable import VariableCreate, VariableRead, VariableUpdate
from langflow.services.deps import get_session, get_settings_service, get_variable_service
from langflow.services.variable.base import VariableService
from langflow.services.variable.constants import GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(prefix="/variables", tags=["Variables"])


@router.post("/", response_model=VariableRead, status_code=201)
def create_variable(
    *,
    session: Session = Depends(get_session),
    variable: VariableCreate,
    current_user: User = Depends(get_current_active_user),
    settings_service=Depends(get_settings_service),
    variable_service: DatabaseVariableService = Depends(get_variable_service),
):
    """Create a new variable."""
    try:
        if not variable.name and not variable.value:
            raise HTTPException(status_code=400, detail="Variable name and value cannot be empty")

        if not variable.name:
            raise HTTPException(status_code=400, detail="Variable name cannot be empty")

        if not variable.value:
            raise HTTPException(status_code=400, detail="Variable value cannot be empty")

        if variable.name in variable_service.list_variables(user_id=current_user.id, session=session):
            raise HTTPException(status_code=400, detail="Variable name already exists")

        return variable_service.create_variable(
            user_id=current_user.id,
            name=variable.name,
            value=variable.value,
            default_fields=variable.default_fields or [],
            _type=variable.type or GENERIC_TYPE,
            session=session,
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[VariableRead], status_code=200)
def read_variables(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    variable_service: DatabaseVariableService = Depends(get_variable_service),
):
    """Read all variables."""
    try:
        return variable_service.get_all(user_id=current_user.id, session=session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{variable_id}", response_model=VariableRead, status_code=200)
def update_variable(
    *,
    session: Session = Depends(get_session),
    variable_id: UUID,
    variable: VariableUpdate,
    current_user: User = Depends(get_current_active_user),
    variable_service: DatabaseVariableService = Depends(get_variable_service),
):
    """Update a variable."""
    try:
        return variable_service.update_variable_fields(
            user_id=current_user.id,
            variable_id=variable_id,
            variable=variable,
            session=session,
        )
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Variable not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{variable_id}", status_code=204)
def delete_variable(
    *,
    session: Session = Depends(get_session),
    variable_id: UUID,
    current_user: User = Depends(get_current_active_user),
    variable_service: VariableService = Depends(get_variable_service),
):
    """Delete a variable."""
    try:
        variable_service.delete_variable_by_id(user_id=current_user.id, variable_id=variable_id, session=session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
