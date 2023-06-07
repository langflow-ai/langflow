from pydantic import BaseModel, validator

from langflow.interface.utils import extract_input_variables_from_prompt


class CacheResponse(BaseModel):
    data: dict


class Code(BaseModel):
    code: str


class Prompt(BaseModel):
    template: str


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

    return PromptValidationResponse(input_variables=input_variables)


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
