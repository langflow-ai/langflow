from fastapi import APIRouter, HTTPException

from langflow.api.v1.base import (
    Code,
    CodeValidationResponse,
    ValidatePromptRequest,
    PromptValidationResponse,
    validate_prompt,
)
from langflow.template.field.base import TemplateField
from loguru import logger
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
def post_validate_prompt(prompt_request: ValidatePromptRequest):
    try:
        input_variables = validate_prompt(prompt_request.template)
        # Check if frontend_node is None before proceeding to avoid attempting to update a non-existent node.
        if prompt_request.frontend_node is None:
            return PromptValidationResponse(
                input_variables=input_variables,
                frontend_node=None,
            )
        old_custom_fields = get_old_custom_fields(prompt_request)

        add_new_variables_to_template(input_variables, prompt_request)

        remove_old_variables_from_template(
            old_custom_fields, input_variables, prompt_request
        )

        update_input_variables_field(input_variables, prompt_request)

        return PromptValidationResponse(
            input_variables=input_variables,
            frontend_node=prompt_request.frontend_node,
        )
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


def get_old_custom_fields(prompt_request):
    try:
        if (
            len(prompt_request.frontend_node.custom_fields) == 1
            and prompt_request.name == ""
        ):
            # If there is only one custom field and the name is empty string
            # then we are dealing with the first prompt request after the node was created
            prompt_request.name = list(
                prompt_request.frontend_node.custom_fields.keys()
            )[0]

        old_custom_fields = prompt_request.frontend_node.custom_fields[
            prompt_request.name
        ].copy()
    except KeyError:
        old_custom_fields = []
    prompt_request.frontend_node.custom_fields[prompt_request.name] = []
    return old_custom_fields


def add_new_variables_to_template(input_variables, prompt_request):
    for variable in input_variables:
        try:
            template_field = TemplateField(
                name=variable,
                display_name=variable,
                field_type="str",
                show=True,
                advanced=False,
                multiline=True,
                input_types=["Document", "BaseOutputParser"],
                value="",  # Set the value to empty string
            )
            if variable in prompt_request.frontend_node.template:
                # Set the new field with the old value
                template_field.value = prompt_request.frontend_node.template[variable][
                    "value"
                ]

            prompt_request.frontend_node.template[variable] = template_field.to_dict()

            # Check if variable is not already in the list before appending
            if (
                variable
                not in prompt_request.frontend_node.custom_fields[prompt_request.name]
            ):
                prompt_request.frontend_node.custom_fields[prompt_request.name].append(
                    variable
                )

        except Exception as exc:
            logger.exception(exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc


def remove_old_variables_from_template(
    old_custom_fields, input_variables, prompt_request
):
    for variable in old_custom_fields:
        if variable not in input_variables:
            try:
                # Remove the variable from custom_fields associated with the given name
                if (
                    variable
                    in prompt_request.frontend_node.custom_fields[prompt_request.name]
                ):
                    prompt_request.frontend_node.custom_fields[
                        prompt_request.name
                    ].remove(variable)

                # Remove the variable from the template
                prompt_request.frontend_node.template.pop(variable, None)

            except Exception as exc:
                logger.exception(exc)
                raise HTTPException(status_code=500, detail=str(exc)) from exc


def update_input_variables_field(input_variables, prompt_request):
    if "input_variables" in prompt_request.frontend_node.template:
        prompt_request.frontend_node.template["input_variables"][
            "value"
        ] = input_variables
