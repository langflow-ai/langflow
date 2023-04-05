from pydantic import BaseModel, validator

from langflow.graph.utils import extract_input_variables_from_prompt


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
