from uuid import UUID
from langflow.database.models.flow_style import (
    FlowStyle,
    FlowStyleCreate,
    FlowStyleRead,
    FlowStyleUpdate,
)
from langflow.database.base import get_session
from sqlmodel import Session, select
from fastapi import APIRouter, Depends, HTTPException


# build router
router = APIRouter(prefix="/flow_styles", tags=["FlowStyles"])

# FlowStyleCreate:
# class FlowStyleBase(SQLModel):
#     color: str = Field(index=True)
#     emoji: str = Field(index=False)
#     flow_id: UUID = Field(default=None, foreign_key="flow.id")


@router.post("/", response_model=FlowStyleRead)
def create_flow_style(
    *, session: Session = Depends(get_session), flow_style: FlowStyleCreate
):
    """Create a new flow_style."""
    db_flow_style = FlowStyle.from_orm(flow_style)
    session.add(db_flow_style)
    session.commit()
    session.refresh(db_flow_style)
    return db_flow_style


@router.get("/", response_model=list[FlowStyleRead])
def read_flow_styles(*, session: Session = Depends(get_session)):
    """Read all flows."""
    try:
        flows = session.exec(select(FlowStyle)).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return flows


@router.get("/{flow_styles_id}", response_model=FlowStyleRead)
def read_flow_style(*, session: Session = Depends(get_session), flow_styles_id: UUID):
    """Read a flow_style."""
    if flow_style := session.get(FlowStyle, flow_styles_id):
        return flow_style
    else:
        raise HTTPException(status_code=404, detail="FlowStyle not found")


@router.patch("/{flow_style_id}", response_model=FlowStyleRead)
def update_flow_style(
    *,
    session: Session = Depends(get_session),
    flow_style_id: UUID,
    flow_style: FlowStyleUpdate,
):
    """Update a flow_style."""
    db_flow_style = session.get(FlowStyle, flow_style_id)
    if not db_flow_style:
        raise HTTPException(status_code=404, detail="FlowStyle not found")
    flow_data = flow_style.dict(exclude_unset=True)
    for key, value in flow_data.items():
        if hasattr(db_flow_style, key) and value is not None:
            setattr(db_flow_style, key, value)
    session.add(db_flow_style)
    session.commit()
    session.refresh(db_flow_style)
    return db_flow_style


@router.delete("/{flow_id}")
def delete_flow_style(*, session: Session = Depends(get_session), flow_id: UUID):
    """Delete a flow_style."""
    flow_style = session.get(FlowStyle, flow_id)
    if not flow_style:
        raise HTTPException(status_code=404, detail="FlowStyle not found")
    session.delete(flow_style)
    session.commit()
    return {"message": "FlowStyle deleted successfully"}
