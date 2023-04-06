from langflow.graph.utils import extract_input_variables_from_prompt
from pydantic import BaseModel, validator


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


def validate_prompt(template: str):
    input_variables = extract_input_variables_from_prompt(template)
    if invalid := [variable for variable in input_variables if " " in variable]:
        raise ValueError(
            f"Invalid input variables: {invalid}. Please remove spaces from input variables"
        )
    return PromptValidationResponse(input_variables=input_variables)
