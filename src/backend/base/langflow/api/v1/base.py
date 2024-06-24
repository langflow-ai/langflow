from typing import Optional

from pydantic import BaseModel, field_validator, model_serializer

from langflow.template.frontend_node.base import FrontendNode


class CacheResponse(BaseModel):
    data: dict


class Code(BaseModel):
    code: str


class FrontendNodeRequest(FrontendNode):
    template: dict  # type: ignore

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        # Override the default serialization method in FrontendNode
        # because we don't need the name in the response (i.e. {name: {}})
        return handler(self)


class ValidatePromptRequest(BaseModel):
    name: str
    template: str
    custom_fields: Optional[dict] = None
    frontend_node: Optional[FrontendNodeRequest] = None


# Build ValidationResponse class for {"imports": {"errors": []}, "function": {"errors": []}}
class CodeValidationResponse(BaseModel):
    imports: dict
    function: dict

    @field_validator("imports")
    @classmethod
    def validate_imports(cls, v):
        return v or {"errors": []}

    @field_validator("function")
    @classmethod
    def validate_function(cls, v):
        return v or {"errors": []}


class PromptValidationResponse(BaseModel):
    input_variables: list
    # object return for tweak call
    frontend_node: Optional[FrontendNodeRequest] = None


INVALID_CHARACTERS = {
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

INVALID_NAMES = {
    "input_variables",
    "output_parser",
    "partial_variables",
    "template",
    "template_format",
    "validate_template",
}


def is_json_like(var):
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


def fix_variable(var, invalid_chars, wrong_variables):
    if not var:
        return var, invalid_chars, wrong_variables
    new_var = var

    # Handle variables starting with a number
    if var[0].isdigit():
        invalid_chars.append(var[0])
        new_var, invalid_chars, wrong_variables = fix_variable(var[1:], invalid_chars, wrong_variables)

    # Temporarily replace {{ and }} to avoid treating them as invalid
    new_var = new_var.replace("{{", "ᴛᴇᴍᴘᴏᴘᴇɴ").replace("}}", "ᴛᴇᴍᴘᴄʟᴏsᴇ")

    # Remove invalid characters
    for char in new_var:
        if char in INVALID_CHARACTERS:
            invalid_chars.append(char)
            new_var = new_var.replace(char, "")
            if var not in wrong_variables:  # Avoid duplicating entries
                wrong_variables.append(var)

    # Restore {{ and }}
    new_var = new_var.replace("ᴛᴇᴍᴘᴏᴘᴇɴ", "{{").replace("ᴛᴇᴍᴘᴄʟᴏsᴇ", "}}")

    return new_var, invalid_chars, wrong_variables


def check_variable(var, invalid_chars, wrong_variables, empty_variables):
    if any(char in invalid_chars for char in var):
        wrong_variables.append(var)
    elif var == "":
        empty_variables.append(var)
    return wrong_variables, empty_variables


def check_for_errors(input_variables, fixed_variables, wrong_variables, empty_variables):
    if any(var for var in input_variables if var not in fixed_variables):
        error_message = (
            f"Error: Input variables contain invalid characters or formats. \n"
            f"Invalid variables: {', '.join(wrong_variables)}.\n"
            f"Empty variables: {', '.join(empty_variables)}. \n"
            f"Fixed variables: {', '.join(fixed_variables)}."
        )
        raise ValueError(error_message)


def check_input_variables(input_variables):
    invalid_chars = []
    fixed_variables = []
    wrong_variables = []
    empty_variables = []
    variables_to_check = []

    for var in input_variables:
        # First, let's check if the variable is a JSON string
        # because if it is, it won't be considered a variable
        # and we don't need to validate it
        if is_json_like(var):
            continue

        new_var, wrong_variables, empty_variables = fix_variable(var, invalid_chars, wrong_variables)
        wrong_variables, empty_variables = check_variable(var, INVALID_CHARACTERS, wrong_variables, empty_variables)
        fixed_variables.append(new_var)
        variables_to_check.append(var)

    check_for_errors(variables_to_check, fixed_variables, wrong_variables, empty_variables)

    return fixed_variables
