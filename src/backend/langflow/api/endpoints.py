from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from langflow.api.base import Code, ValidationResponse
from langflow.interface.run import process_graph
from langflow.interface.types import build_langchain_types_dict
from langflow.utils.validate import validate_code
import logging

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


@router.post("/validate", status_code=200, response_model=ValidationResponse)
def post_validate_code(code: Code):
    try:
        errors = validate_code(code.code)
        return ValidationResponse(
            imports=errors.get("imports", {}),
            function=errors.get("function", {}),
        )
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))
