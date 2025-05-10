from fastapi import APIRouter, HTTPException
from loguru import logger

from langflow.api.utils import CurrentActiveUser
from langflow.api.v1.base import Code, CodeValidationResponse, PromptValidationResponse, ValidatePromptRequest
from langflow.base.prompts.api_utils import process_prompt_template
from langflow.utils.validate import validate_code

# build router
router = APIRouter(prefix="/validate", tags=["Validate"])


@router.post("/code", status_code=200)
async def post_validate_code(code: Code, _current_user: CurrentActiveUser) -> CodeValidationResponse:
    try:
        errors = validate_code(code.code)
        return CodeValidationResponse(
            imports=errors.get("imports", {}),
            function=errors.get("function", {}),
        )
    except Exception as e:
        logger.opt(exception=True).debug("Error validating code")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/prompt", status_code=200)
async def post_validate_prompt(prompt_request: ValidatePromptRequest) -> PromptValidationResponse:
    try:
        if not prompt_request.frontend_node:
            return PromptValidationResponse(
                input_variables=[],
                frontend_node=None,
            )

        # Process the prompt template using direct attributes
        input_variables = process_prompt_template(
            template=prompt_request.template,
            name=prompt_request.name,
            custom_fields=prompt_request.frontend_node.custom_fields,
            frontend_node_template=prompt_request.frontend_node.template,
        )

        return PromptValidationResponse(
            input_variables=input_variables,
            frontend_node=prompt_request.frontend_node,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
