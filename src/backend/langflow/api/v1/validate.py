from fastapi import APIRouter, HTTPException

from langflow.api.v1.base import (
    Code,
    CodeValidationResponse,
    Prompt,
    PromptValidationResponse,
    validate_prompt,
)
from langflow.utils.logger import logger
from langflow.utils.validate import validate_code

# build router
router = APIRouter(prefix="/validate", tags=["Validate"])


@router.post("/code", status_code=200, response_model=CodeValidationResponse)
def post_validate_code(code: Code):
    try:
        errors = validate_code(code.code)
        return CodeValidationResponse(
            imports=errors.get("imports", {}),
            function=errors.get("function", {}),
        )
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))


@router.post("/prompt", status_code=200, response_model=PromptValidationResponse)
def post_validate_prompt(prompt: Prompt):
    try:
        return validate_prompt(prompt.template)
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e
