from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from langflow.services.auth import utils as auth_utils
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable import Variable, VariableCreate, VariableRead, VariableUpdate
from langflow.services.deps import get_session, get_settings_service

router = APIRouter(prefix="/variables", tags=["Variables"])


@router.post("/", response_model=VariableRead, status_code=201)
def create_variable(
    *,
    session: Session = Depends(get_session),
    variable: VariableCreate,
    current_user: User = Depends(get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    """Create a new variable."""
    try:
        # check if variable name already exists
        variable_exists = session.exec(
            select(Variable).where(
                Variable.name == variable.name,
                Variable.user_id == current_user.id,
            )
        ).first()
        if variable_exists:
            raise HTTPException(status_code=400, detail="Variable name already exists")

        variable_dict = variable.model_dump()
        variable_dict["user_id"] = current_user.id

        db_variable = Variable.model_validate(variable_dict)
        if not db_variable.name and not db_variable.value:
            raise HTTPException(status_code=400, detail="Variable name and value cannot be empty")
        elif not db_variable.name:
            raise HTTPException(status_code=400, detail="Variable name cannot be empty")
        elif not db_variable.value:
            raise HTTPException(status_code=400, detail="Variable value cannot be empty")
        encrypted = auth_utils.encrypt_api_key(db_variable.value, settings_service=settings_service)
        db_variable.value = encrypted
        db_variable.user_id = current_user.id
        session.add(db_variable)
        session.commit()
        session.refresh(db_variable)
        return db_variable
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[VariableRead], status_code=200)
def read_variables(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    """Read all variables."""
    try:
        variables = session.exec(select(Variable).where(Variable.user_id == current_user.id)).all()
        return variables
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{variable_id}", response_model=VariableRead, status_code=200)
def update_variable(
    *,
    session: Session = Depends(get_session),
    variable_id: UUID,
    variable: VariableUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update a variable."""
    try:
        db_variable = session.exec(
            select(Variable).where(Variable.id == variable_id, Variable.user_id == current_user.id)
        ).first()
        if not db_variable:
            raise HTTPException(status_code=404, detail="Variable not found")

        variable_data = variable.model_dump(exclude_unset=True)
        for key, value in variable_data.items():
            setattr(db_variable, key, value)
        db_variable.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(db_variable)
        return db_variable
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{variable_id}", status_code=204)
def delete_variable(
    *,
    session: Session = Depends(get_session),
    variable_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a variable."""
    try:
        db_variable = session.exec(
            select(Variable).where(Variable.id == variable_id, Variable.user_id == current_user.id)
        ).first()
        if not db_variable:
            raise HTTPException(status_code=404, detail="Variable not found")
        session.delete(db_variable)
        session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
