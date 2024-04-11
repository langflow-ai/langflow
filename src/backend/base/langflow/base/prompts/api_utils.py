from fastapi import HTTPException
from langchain.prompts import PromptTemplate
from loguru import logger

from langflow.api.v1.base import INVALID_NAMES, check_input_variables
from langflow.interface.utils import extract_input_variables_from_prompt
from langflow.template.field.prompt import DefaultPromptField


def validate_prompt(prompt_template: str, silent_errors: bool = False) -> list[str]:
    input_variables = extract_input_variables_from_prompt(prompt_template)

    # Check if there are invalid characters in the input_variables
    input_variables = check_input_variables(input_variables)
    if any(var in INVALID_NAMES for var in input_variables):
        raise ValueError(f"Invalid input variables. None of the variables can be named {', '.join(input_variables)}. ")

    try:
        PromptTemplate(template=prompt_template, input_variables=input_variables)
    except Exception as exc:
        logger.error(f"Invalid prompt: {exc}")
        if not silent_errors:
            raise ValueError(f"Invalid prompt: {exc}") from exc

    return input_variables


def get_old_custom_fields(custom_fields, name):
    try:
        if len(custom_fields) == 1 and name == "":
            # If there is only one custom field and the name is empty string
            # then we are dealing with the first prompt request after the node was created
            name = list(custom_fields.keys())[0]

        old_custom_fields = custom_fields[name]
        if not old_custom_fields:
            old_custom_fields = []

        old_custom_fields = old_custom_fields.copy()
    except KeyError:
        old_custom_fields = []
    custom_fields[name] = []
    return old_custom_fields


def add_new_variables_to_template(input_variables, custom_fields, template, name):
    for variable in input_variables:
        try:
            template_field = DefaultPromptField(name=variable, display_name=variable)
            if variable in template:
                # Set the new field with the old value
                template_field.value = template[variable]["value"]

            template[variable] = template_field.to_dict()

            # Check if variable is not already in the list before appending
            if variable not in custom_fields[name]:
                custom_fields[name].append(variable)

        except Exception as exc:
            logger.exception(exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc


def remove_old_variables_from_template(old_custom_fields, input_variables, custom_fields, template, name):
    for variable in old_custom_fields:
        if variable not in input_variables:
            try:
                # Remove the variable from custom_fields associated with the given name
                if variable in custom_fields[name]:
                    custom_fields[name].remove(variable)

                # Remove the variable from the template
                template.pop(variable, None)

            except Exception as exc:
                logger.exception(exc)
                raise HTTPException(status_code=500, detail=str(exc)) from exc


def update_input_variables_field(input_variables, template):
    if "input_variables" in template:
        template["input_variables"]["value"] = input_variables
