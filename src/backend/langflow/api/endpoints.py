import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from langflow.interface.run import process_graph
from langflow.interface.types import build_langchain_types_dict

# build router
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/all")
def get_all():
    return build_langchain_types_dict()


@router.post("/predict")
def get_load(data: Dict[str, Any]):
    try:
        return process_graph(data)
    except Exception as e:
        # Log stack trace
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e
