from pydantic import BaseModel, validator


class Code(BaseModel):
    code: str

    @validator("code")
    def validate_code(cls, v):
        return v


# Build ValidationResponse class for {"imports": {"errors": []}, "function": {"errors": []}}
class ValidationResponse(BaseModel):
    imports: dict
    function: dict

    @validator("imports")
    def validate_imports(cls, v):
        return v or {"errors": []}

    @validator("function")
    def validate_function(cls, v):
        return v or {"errors": []}
