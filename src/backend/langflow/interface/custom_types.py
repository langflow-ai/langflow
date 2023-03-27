from pydantic import BaseModel, validator
from langchain.agents import tool


class PythonFunction(BaseModel):
    code: str

    # Validate the function
    @validator("code")
    def validate_func(cls, v):
        # Validate with LangChain's tool decorator
        tool(v)
        return v
