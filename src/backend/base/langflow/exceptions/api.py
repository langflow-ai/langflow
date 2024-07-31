from fastapi import HTTPException
from pydantic import BaseModel
class InvalidChatInputException(Exception):
    pass

# create a pidantic documentation for this class
class exceptionBody(BaseModel):
    message: str | list[str]
    traceback: str | list[str] | None=None
    description: str | list[str] | None=None
    code: str | None=None
    suggestion: str | list[str] | None=None

class APIException(HTTPException):
    def __init__(self, exception: exceptionBody, status_code: int = 500):
        super().__init__(status_code=status_code, detail=exception.model_dump())
