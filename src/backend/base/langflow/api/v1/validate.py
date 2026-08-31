from fastapi import APIRouter, Depends, HTTPException
from lfx.base.prompts.api_utils import process_prompt_template
from lfx.custom.validate import validate_code
from lfx.log.logger import logger

from langflow.api.utils import CurrentActiveUser
from langflow.api.v1.base import Code, CodeValidationResponse, PromptValidationResponse, ValidatePromptRequest
from langflow.api.v1.custom_component_policy import resolve_component_code_for_action
from langflow.services.auth.utils import get_current_active_user
from langflow.services.deps import get_catalog_policy_service, get_settings_service

# build router
router = APIRouter(prefix="/validate", tags=["Validate"])


@router.post("/code", status_code=200, include_in_schema=False)
async def post_validate_code(code: Code, user: CurrentActiveUser) -> CodeValidationResponse:
    effective_code = resolve_component_code_for_action(
        code.code,
        user=user,
        settings=get_settings_service().settings,
        snapshot=get_catalog_policy_service().snapshot,
        disabled_detail="Custom component validation is disabled",
        admin_only_detail="Custom component validation is restricted to administrators",
    )
    try:
        errors = validate_code(effective_code)
        return CodeValidationResponse(
            imports=errors.get("imports", {}),
            function=errors.get("function", {}),
        )
    except Exception as e:
        logger.debug("Error validating code", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/prompt", status_code=200, dependencies=[Depends(get_current_active_user)], include_in_schema=False)
async def post_validate_prompt(
    prompt_request: ValidatePromptRequest,
) -> PromptValidationResponse:
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
            is_mustache=prompt_request.mustache,
        )

        return PromptValidationResponse(
            input_variables=input_variables,
            frontend_node=prompt_request.frontend_node,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
