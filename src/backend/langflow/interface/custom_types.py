from langflow.utils import util
from pydantic import BaseModel, validator
from langchain.agents import tool


class Function(BaseModel):
    code: str

    # Validate the function
    @validator("code")
    def validate_func(cls, v):
        # Validate with LangChain's tool decorator
        tool(v)
        return v

    def get_function(self):
        """Get the function"""
        return util.eval_function(self.code)


class PythonFunction(Function):
    """Python function"""

    code: str
