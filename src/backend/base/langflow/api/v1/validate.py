from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlmodel import Session

from langflow.api.v1.base import Code, CodeValidationResponse, PromptValidationResponse, ValidatePromptRequest
from langflow.base.prompts.api_utils import (
    add_new_variables_to_template,
    get_old_custom_fields,
    remove_old_variables_from_template,
    update_input_variables_field,
    validate_prompt,
)
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_service, get_session
from langflow.services.schema import ServiceType
from langflow.services.variable.service import VariableService
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
def post_validate_prompt(
    prompt_request: ValidatePromptRequest,
    variable_service: VariableService = Depends(get_service(ServiceType.VARIABLE_SERVICE, partial=True)),
    current_user: User = Depends(auth_utils.get_current_active_user),
    db: Session = Depends(get_session),
):
    try:
        field_data = prompt_request.frontend_node.template.get(prompt_request.name, {})
        if field_data.get("type") == "prompt" and field_data.get("load_from_db"):
            prompt_request.template = variable_service.get_variable(current_user.id, field_data.get("value"), db)

        input_variables = validate_prompt(prompt_request.template)

        # Check if frontend_node is None before proceeding to avoid attempting to update a non-existent node.
        if prompt_request.frontend_node is None:
            return PromptValidationResponse(
                input_variables=input_variables,
                frontend_node=None,
            )
        if not prompt_request.frontend_node.custom_fields:
            prompt_request.frontend_node.custom_fields = defaultdict(list)
        old_custom_fields = get_old_custom_fields(prompt_request.frontend_node.custom_fields, prompt_request.name)

        add_new_variables_to_template(
            input_variables,
            prompt_request.frontend_node.custom_fields,
            prompt_request.frontend_node.template,
            prompt_request.name,
        )

        remove_old_variables_from_template(
            old_custom_fields,
            input_variables,
            prompt_request.frontend_node.custom_fields,
            prompt_request.frontend_node.template,
            prompt_request.name,
        )

        update_input_variables_field(input_variables, prompt_request.frontend_node.template)

        # If frontend_node.template contains only one field that is type == 'prompt', then we can remove all fields that are not
        # 'code', and not in the input_variables list.
        prompt_fields = [
            key
            for key, field in prompt_request.frontend_node.template.items()
            if isinstance(field, dict) and field["type"] == "prompt"
        ]

        if len(prompt_fields) == 1:
            for key, field in prompt_request.frontend_node.template.copy().items():
                if isinstance(field, dict) and field["type"] != "code" and key not in input_variables + prompt_fields:
                    del prompt_request.frontend_node.template[key]
        return PromptValidationResponse(
            input_variables=input_variables,
            frontend_node=prompt_request.frontend_node,
        )
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e
