from fastapi import HTTPException
from langflow.api.base import (
    Code,
    CodeValidationResponse,
    Prompt,
    PromptValidationResponse,
    validate_prompt,
)

from langflow.utils.validate import validate_code
from langflow.utils.logger import logger


from fastapi import APIRouter, HTTPException

# build router
router = APIRouter(prefix="/validate", tags=["validate"])


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
        input_variables, valid = validate_prompt(prompt.template)
        return PromptValidationResponse(input_variables=input_variables, valid=valid)
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))
