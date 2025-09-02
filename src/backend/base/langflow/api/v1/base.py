from lfx.template.frontend_node.base import FrontendNode
from pydantic import BaseModel, field_validator, model_serializer


class CacheResponse(BaseModel):
    data: dict


class Code(BaseModel):
    code: str


class FrontendNodeRequest(FrontendNode):
    template: dict  # type: ignore[assignment]

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        # Override the default serialization method in FrontendNode
        # because we don't need the name in the response (i.e. {name: {}})
        return handler(self)


class ValidatePromptRequest(BaseModel):
    name: str
    template: str
    custom_fields: dict | None = None
    frontend_node: FrontendNodeRequest | None = None


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
    frontend_node: FrontendNodeRequest | None = None
