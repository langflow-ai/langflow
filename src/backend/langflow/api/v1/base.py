from typing import Optional
from langflow.template.frontend_node.base import FrontendNode
from pydantic import BaseModel, validator

from langflow.interface.utils import extract_input_variables_from_prompt
from langchain.prompts import PromptTemplate


class CacheResponse(BaseModel):
    data: dict


class Code(BaseModel):
    code: str


class FrontendNodeRequest(FrontendNode):
    template: dict  # type: ignore


class ValidatePromptRequest(BaseModel):
    name: str
    template: str
    # optional for tweak call
    frontend_node: Optional[FrontendNodeRequest] = None


# Build ValidationResponse class for {"imports": {"errors": []}, "function": {"errors": []}}
class CodeValidationResponse(BaseModel):
    imports: dict
    function: dict

    @validator("imports")
    def validate_imports(cls, v):
        return v or {"errors": []}

    @validator("function")
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
    "{",
    "}",
}

INVALID_NAMES = {
    "input_variables",
    "output_parser",
    "partial_variables",
    "template",
    "template_format",
    "validate_template",
}


def validate_prompt(template: str):
    input_variables = extract_input_variables_from_prompt(template)

    # Check if there are invalid characters in the input_variables
    input_variables = check_input_variables(input_variables)
    if any(var in INVALID_NAMES for var in input_variables):
        raise ValueError(
            f"Invalid input variables. None of the variables can be named {', '.join(input_variables)}. "
        )

    try:
        PromptTemplate(template=template, input_variables=input_variables)
    except Exception as exc:
        raise ValueError(str(exc)) from exc

    return input_variables


def check_input_variables(input_variables: list):
    invalid_chars = []
    fixed_variables = []
    wrong_variables = []
    empty_variables = []
    for variable in input_variables:
        new_var = variable

        # if variable is empty, then we should add that to the wrong variables
        if not variable:
            empty_variables.append(variable)
            continue

        # if variable starts with a number we should add that to the invalid chars
        # and wrong variables
        if variable[0].isdigit():
            invalid_chars.append(variable[0])
            new_var = new_var.replace(variable[0], "")
            wrong_variables.append(variable)
        else:
            for char in INVALID_CHARACTERS:
                if char in variable:
                    invalid_chars.append(char)
                    new_var = new_var.replace(char, "")
                    wrong_variables.append(variable)
        fixed_variables.append(new_var)
    # If any of the input_variables is not in the fixed_variables, then it means that
    # there are invalid characters in the input_variables

    if any(var not in fixed_variables for var in input_variables):
        error_message = build_error_message(
            input_variables,
            invalid_chars,
            wrong_variables,
            fixed_variables,
            empty_variables,
        )
        raise ValueError(error_message)
    return input_variables


def build_error_message(
    input_variables, invalid_chars, wrong_variables, fixed_variables, empty_variables
):
    input_variables_str = ", ".join([f"'{var}'" for var in input_variables])
    error_string = f"Invalid input variables: {input_variables_str}. "

    if wrong_variables and invalid_chars:
        # fix the wrong variables replacing invalid chars and find them in the fixed variables
        error_string_vars = "You can fix them by replacing the invalid characters: "
        wvars = wrong_variables.copy()
        for i, wrong_var in enumerate(wvars):
            for char in invalid_chars:
                wrong_var = wrong_var.replace(char, "")
            if wrong_var in fixed_variables:
                error_string_vars += f"'{wrong_variables[i]}' -> '{wrong_var}'"
        error_string += error_string_vars
    elif empty_variables:
        error_string += f" There are {len(empty_variables)} empty variable{'s' if len(empty_variables) > 1 else ''}."
    elif len(set(fixed_variables)) != len(fixed_variables):
        error_string += "There are duplicate variables."
    return error_string
