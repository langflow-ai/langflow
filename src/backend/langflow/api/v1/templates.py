from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlmodel import Session, select
from fastapi.encoders import jsonable_encoder

from langflow.database.base import get_session
from langflow.api.v1.schemas import TemplateRead

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.post("/", response_model=TemplateRead)
def create_template(*, session: Session=Depends(get_session), template):
    ...

@router.get("/all")
def get_templates():
    ...

@router.get("/{template_id}")
def get_template(template_id: UUID):
    ...

@router.patch("/{template_id}")
def update_template(template_id: UUID, data):
    ...

@router.delete("/{template_id}")
def delete_tempalte(template_id: UUID):
    ...
