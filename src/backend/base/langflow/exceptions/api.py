from fastapi import HTTPException
from langflow.api.utils import get_suggestion_messsage
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow.utils import get_outdated_components
from pydantic import BaseModel


class InvalidChatInputException(Exception):
    pass


# create a pidantic documentation for this class
class ExceptionBody(BaseModel):
    message: str | list[str]
    traceback: str | list[str] | None = None
    description: str | list[str] | None = None
    code: str | None = None
    suggestion: str | list[str] | None = None


class APIException(HTTPException):
    def __init__(self, exception: ExceptionBody, status_code: int = 500):
        super().__init__(status_code=status_code, detail=exception.model_dump_json())

    @staticmethod
    def from_exc_and_flow(exc: str | list[str], flow: Flow) -> ExceptionBody:
        body = {"message": str(exc)}
        outdated_components = get_outdated_components(flow)
        if outdated_components:
            body["suggestion"] = get_suggestion_messsage(outdated_components)
        excep = ExceptionBody(**body)
        return excep
