from typing import Callable
from langflow.utils import util
from pydantic import BaseModel, validator



class Function(BaseModel):
    code: str

    # Eval code and store the function
    def __init__(self, **data):
        super().__init__(**data)

    # Validate the function
    @validator("code")
    def validate_func(cls, v):
        # Validate with LangChain's tool decorator
        func = util.eval_function(v)
        if not isinstance(func, Callable):
            raise ValueError("Function must be a callable")

        return v

    def get_function(self):
        """Get the function"""
        return util.eval_function(self.code)


class PythonFunction(Function):
    """Python function"""

    code: str
