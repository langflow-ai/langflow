from fastapi import APIRouter, HTTPException

from langflow.api.v1.base import (
    Code,
    CodeValidationResponse,
    ValidatePromptRequest,
    PromptValidationResponse,
    validate_prompt,
)
from langflow.template.field.base import TemplateField
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
def post_validate_prompt(prompt: ValidatePromptRequest):
    try:
        input_variables = validate_prompt(prompt.template)
        # Reinitialize custom_fields
        old_custom_fields = prompt.frontend_node.custom_fields.copy()
        prompt.frontend_node.custom_fields = []
        # Add new variables to the template
        for variable in input_variables:
            try:
                template_field = TemplateField(
                    name=variable,
                    field_type="str",
                    show=True,
                    advanced=False,
                    input_types=["BaseLoader", "BaseOutputParser"],
                )

                prompt.frontend_node.template[variable] = template_field.to_dict()
                prompt.frontend_node.custom_fields.append(variable)

            except Exception as exc:
                logger.exception(exc)
                raise HTTPException(status_code=500, detail=str(exc)) from exc

        # Remove variables that are not in the template anymore
        for variable in old_custom_fields:
            if variable not in input_variables:
                try:
                    prompt.frontend_node.template.pop(variable, None)
                except Exception as exc:
                    logger.exception(exc)
                    raise HTTPException(status_code=500, detail=str(exc)) from exc

        # Now we will set the field "input_variables" to the new list of variables
        # if it exists
        if "input_variables" in prompt.frontend_node.template:
            prompt.frontend_node.template["input_variables"]["value"] = input_variables

        return PromptValidationResponse(
            input_variables=input_variables,
            frontend_node=prompt.frontend_node,
        )
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e
