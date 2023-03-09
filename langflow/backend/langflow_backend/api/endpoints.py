from fastapi import APIRouter, HTTPException
from langflow_backend.interface.types import build_langchain_types_dict, get_type_list
from langflow_backend.interface.loading import process_data_graph
from typing import Any, Dict


# build router
router = APIRouter()


@router.get("/all")
def get_all():
    return build_langchain_types_dict()


@router.post("/predict")
def get_load(data: Dict[str, Any]):
    try:
        return process_data_graph(data)
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))
