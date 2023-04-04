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
    valid: bool


def validate_prompt(template):
    # Extract the input variables from template
    input_variables = extract_input_variables_from_prompt(template)
    return input_variables, len(input_variables) > 0
