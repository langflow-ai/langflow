from fastapi import APIRouter, HTTPException

from langflow.api.base import (
    Code,
    CodeValidationResponse,
    Prompt,
    PromptValidationResponse,
)
from langflow.graph.utils import extract_input_variables_from_prompt
from langflow.utils.logger import logger
from langflow.utils.validate import validate_code

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
        input_variables = extract_input_variables_from_prompt(prompt.template)
        return PromptValidationResponse(input_variables=input_variables)
    except Exception as e:
        logger.exception(e)
        return HTTPException(status_code=500, detail=str(e))
