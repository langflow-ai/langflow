from collections import defaultdict

from fastapi import APIRouter, HTTPException
from loguru import logger

from langflow_base.api.v1.base import (
    Code,
    CodeValidationResponse,
    PromptValidationResponse,
    ValidatePromptRequest,
    validate_prompt,
)
from langflow_base.template.field.base import TemplateField
from langflow_base.utils.validate import validate_code

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
def post_validate_prompt(prompt_request: ValidatePromptRequest):
    try:
        input_variables = validate_prompt(prompt_request.template)
        # Check if frontend_node is None before proceeding to avoid attempting to update a non-existent node.
        if prompt_request.frontend_node is None:
            return PromptValidationResponse(
                input_variables=input_variables,
                frontend_node=None,
            )
        if not prompt_request.custom_fields:
            prompt_request.custom_fields = defaultdict(list)
        old_custom_fields = get_old_custom_fields(prompt_request.custom_fields, prompt_request.name)

        add_new_variables_to_template(
            input_variables,
            prompt_request.custom_fields,
            prompt_request.frontend_node.template,
            prompt_request.name,
        )

        remove_old_variables_from_template(
            old_custom_fields,
            input_variables,
            prompt_request.custom_fields,
            prompt_request.frontend_node.template,
            prompt_request.name,
        )

        update_input_variables_field(input_variables, prompt_request.frontend_node.template)

        return PromptValidationResponse(
            input_variables=input_variables,
            frontend_node=prompt_request.frontend_node,
        )
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e
