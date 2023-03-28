from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from langflow.interface.run import process_graph
from langflow.interface.types import build_langchain_types_dict

# build router
router = APIRouter()


@router.get("/all")
def get_all():
    return build_langchain_types_dict()


@router.post("/predict")
def get_load(data: Dict[str, Any]):
    try:
        return process_graph(data)
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))
