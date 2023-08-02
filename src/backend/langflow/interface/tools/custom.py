from typing import Callable, Optional
from langflow.interface.importing.utils import get_function

from pydantic import BaseModel, validator

from langflow.utils import validate
from langchain.agents.tools import Tool


class Function(BaseModel):
    code: str
    function: Optional[Callable] = None
    imports: Optional[str] = None

    # Eval code and store the function
    def __init__(self, **data):
        super().__init__(**data)

    # Validate the function
    @validator("code")
    def validate_func(cls, v):
        try:
            validate.eval_function(v)
        except Exception as e:
            raise e

        return v

    def get_function(self):
        """Get the function"""
        function_name = validate.extract_function_name(self.code)

        return validate.create_function(self.code, function_name)


class PythonFunctionTool(Function, Tool):
    name: str = "Custom Tool"
    description: str
    code: str

    def ___init__(self, name: str, description: str, code: str):
        self.name = name
        self.description = description
        self.code = code
        self.func = get_function(self.code)
        super().__init__(name=name, description=description, func=self.func)


class PythonFunction(Function):
    code: str
