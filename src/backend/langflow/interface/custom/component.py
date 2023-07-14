from pydantic import BaseModel
from fastapi import HTTPException

from langflow.utils import validate
from langflow.interface.custom.code_parser import CodeParser


class ComponentCodeNullError(HTTPException):
    pass


class ComponentFunctionEntrypointNameNullError(HTTPException):
    pass


class Component(BaseModel):
    ERROR_CODE_NULL = "Python code must be provided."
    ERROR_FUNCTION_ENTRYPOINT_NAME_NULL = (
        "The name of the entrypoint function must be provided."
    )

    code: str
    function_entrypoint_name = "build"
    field_config: dict = {}

    def __init__(self, **data):
        super().__init__(**data)

    def get_code_tree(self, code: str):
        parser = CodeParser(code)
        return parser.parse_code()

    def get_function(self):
        if not self.code:
            raise ComponentCodeNullError(
                status_code=400,
                detail={"error": self.ERROR_CODE_NULL, "traceback": ""},
            )

        if not self.function_entrypoint_name:
            raise ComponentFunctionEntrypointNameNullError(
                status_code=400,
                detail={
                    "error": self.ERROR_FUNCTION_ENTRYPOINT_NAME_NULL,
                    "traceback": "",
                },
            )

        return validate.create_function(self.code, self.function_entrypoint_name)

    def build(self):
        raise NotImplementedError
