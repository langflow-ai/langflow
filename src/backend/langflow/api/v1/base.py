from langflow.template.frontend_node.base import FrontendNode
from pydantic import BaseModel, validator

from langflow.interface.utils import extract_input_variables_from_prompt
from langchain.prompts import PromptTemplate


class CacheResponse(BaseModel):
    data: dict


class Code(BaseModel):
    code: str


class ValidatePromptRequest(BaseModel):
    template: str
    frontend_node: FrontendNode


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
    frontend_node: FrontendNode


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


def validate_prompt(template: str):
    input_variables = extract_input_variables_from_prompt(template)

    # Check if there are invalid characters in the input_variables
    input_variables = check_input_variables(input_variables)
    try:
        PromptTemplate(template=template, input_variables=input_variables)
    except Exception as exc:
        raise ValueError(str(exc)) from exc

    # if len(input_variables) > 1:
    #     # If there's more than one input variable

    return input_variables


def check_input_variables(input_variables: list):
    invalid_chars = []
    fixed_variables = []
    for variable in input_variables:
        new_var = variable
        for char in INVALID_CHARACTERS:
            if char in variable:
                invalid_chars.append(char)
                new_var = new_var.replace(char, "")
        fixed_variables.append(new_var)
        if new_var != variable:
            input_variables.remove(variable)
            input_variables.append(new_var)
    # If any of the input_variables is not in the fixed_variables, then it means that
    # there are invalid characters in the input_variables
    if any(var not in fixed_variables for var in input_variables):
        raise ValueError(
            f"Invalid input variables: {input_variables}. Please, use something like {fixed_variables} instead."
        )

    return input_variables
