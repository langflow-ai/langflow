from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langflow.interface.utils import extract_input_variables_from_prompt
from loguru import logger

from lfx.inputs.inputs import DefaultPromptField

_INVALID_CHARACTERS = {
    " ",
    ",",
    ".",
    ":",
    ";",
    "!",
    "?",
    "/",
    "\\",
    "(",
    ")",
    "[",
    "]",
}

_INVALID_NAMES = {
    "code",
    "input_variables",
    "output_parser",
    "partial_variables",
    "template",
    "template_format",
    "validate_template",
}


def _is_json_like(var):
    if var.startswith("{{") and var.endswith("}}"):
        # If it is a double brance variable
        # we don't want to validate any of its content
        return True
    # the above doesn't work on all cases because the json string can be multiline
    # or indented which can add \n or spaces at the start or end of the string
    # test_case_3 new_var == '\n{{\n    "test": "hello",\n    "text": "world"\n}}\n'
    # what we can do is to remove the \n and spaces from the start and end of the string
    # and then check if the string starts with {{ and ends with }}
    var = var.strip()
    var = var.replace("\n", "")
    var = var.replace(" ", "")
    # Now it should be a valid json string
    return var.startswith("{{") and var.endswith("}}")


def _fix_variable(var, invalid_chars, wrong_variables):
    if not var:
        return var, invalid_chars, wrong_variables
    new_var = var

    # Handle variables starting with a number
    if var[0].isdigit():
        invalid_chars.append(var[0])
        new_var, invalid_chars, wrong_variables = _fix_variable(var[1:], invalid_chars, wrong_variables)

    # Temporarily replace {{ and }} to avoid treating them as invalid
    new_var = new_var.replace("{{", "ᴛᴇᴍᴘᴏᴘᴇɴ").replace("}}", "ᴛᴇᴍᴘᴄʟᴏsᴇ")  # noqa: RUF001

    # Remove invalid characters
    for char in new_var:
        if char in _INVALID_CHARACTERS:
            invalid_chars.append(char)
            new_var = new_var.replace(char, "")
            if var not in wrong_variables:  # Avoid duplicating entries
                wrong_variables.append(var)

    # Restore {{ and }}
    new_var = new_var.replace("ᴛᴇᴍᴘᴏᴘᴇɴ", "{{").replace("ᴛᴇᴍᴘᴄʟᴏsᴇ", "}}")  # noqa: RUF001

    return new_var, invalid_chars, wrong_variables


def _check_variable(var, invalid_chars, wrong_variables, empty_variables):
    if any(char in invalid_chars for char in var):
        wrong_variables.append(var)
    elif var == "":
        empty_variables.append(var)
    return wrong_variables, empty_variables


def _check_for_errors(input_variables, fixed_variables, wrong_variables, empty_variables) -> None:
    if any(var for var in input_variables if var not in fixed_variables):
        error_message = (
            f"Error: Input variables contain invalid characters or formats. \n"
            f"Invalid variables: {', '.join(wrong_variables)}.\n"
            f"Empty variables: {', '.join(empty_variables)}. \n"
            f"Fixed variables: {', '.join(fixed_variables)}."
        )
        raise ValueError(error_message)


def _check_input_variables(input_variables):
    invalid_chars = []
    fixed_variables = []
    wrong_variables = []
    empty_variables = []
    variables_to_check = []

    for var in input_variables:
        # First, let's check if the variable is a JSON string
        # because if it is, it won't be considered a variable
        # and we don't need to validate it
        if _is_json_like(var):
            continue

        new_var, wrong_variables, empty_variables = _fix_variable(var, invalid_chars, wrong_variables)
        wrong_variables, empty_variables = _check_variable(var, _INVALID_CHARACTERS, wrong_variables, empty_variables)
        fixed_variables.append(new_var)
        variables_to_check.append(var)

    _check_for_errors(variables_to_check, fixed_variables, wrong_variables, empty_variables)

    return fixed_variables


def validate_prompt(prompt_template: str, *, silent_errors: bool = False) -> list[str]:
    input_variables = extract_input_variables_from_prompt(prompt_template)

    # Check if there are invalid characters in the input_variables
    input_variables = _check_input_variables(input_variables)
    if any(var in _INVALID_NAMES for var in input_variables):
        msg = f"Invalid input variables. None of the variables can be named {', '.join(input_variables)}. "
        raise ValueError(msg)

    try:
        PromptTemplate(template=prompt_template, input_variables=input_variables)
    except Exception as exc:
        msg = f"Invalid prompt: {exc}"
        logger.exception(msg)
        if not silent_errors:
            raise ValueError(msg) from exc

    return input_variables


def get_old_custom_fields(custom_fields, name):
    try:
        if len(custom_fields) == 1 and name == "":
            # If there is only one custom field and the name is empty string
            # then we are dealing with the first prompt request after the node was created
            name = next(iter(custom_fields.keys()))

        old_custom_fields = custom_fields[name]
        if not old_custom_fields:
            old_custom_fields = []

        old_custom_fields = old_custom_fields.copy()
    except KeyError:
        old_custom_fields = []
    custom_fields[name] = []
    return old_custom_fields


def add_new_variables_to_template(input_variables, custom_fields, template, name) -> None:
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
            raise HTTPException(status_code=500, detail=str(exc)) from exc


def remove_old_variables_from_template(old_custom_fields, input_variables, custom_fields, template, name) -> None:
    for variable in old_custom_fields:
        if variable not in input_variables:
            try:
                # Remove the variable from custom_fields associated with the given name
                if variable in custom_fields[name]:
                    custom_fields[name].remove(variable)

                # Remove the variable from the template
                template.pop(variable, None)

            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc


def update_input_variables_field(input_variables, template) -> None:
    if "input_variables" in template:
        template["input_variables"]["value"] = input_variables


def process_prompt_template(
    template: str, name: str, custom_fields: dict[str, list[str]] | None, frontend_node_template: dict[str, Any]
):
    """Process and validate prompt template, update template and custom fields."""
    # Validate the prompt template and extract input variables
    input_variables = validate_prompt(template)

    # Initialize custom_fields if None
    if custom_fields is None:
        custom_fields = defaultdict(list)

    # Retrieve old custom fields
    old_custom_fields = get_old_custom_fields(custom_fields, name)

    # Add new variables to the template
    add_new_variables_to_template(input_variables, custom_fields, frontend_node_template, name)

    # Remove old variables from the template
    remove_old_variables_from_template(old_custom_fields, input_variables, custom_fields, frontend_node_template, name)

    # Update the input variables field in the template
    update_input_variables_field(input_variables, frontend_node_template)

    return input_variables
