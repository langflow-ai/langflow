from fastapi import HTTPException
from pydantic import BaseModel

from langflow_execution.api.v1.schema.flow import Flow

class ExceptionBody(BaseModel):
    message: str | list[str]
    traceback: str | list[str] | None = None
    description: str | list[str] | None = None
    code: str | None = None
    suggestion: str | list[str] | None = None


class APIException(HTTPException):
    def __init__(self, exception: Exception, flow: Flow | None = None, status_code: int = 500):
        body = self.build_exception_body(exception, flow)
        super().__init__(status_code=status_code, detail=body.model_dump_json())

    @staticmethod
    def build_exception_body(exc: str | list[str] | Exception, flow: Flow | None) -> ExceptionBody:
        body = {"message": str(exc)}
        if flow:
            outdated_components = get_outdated_components(flow)
            if outdated_components:
                body["suggestion"] = get_suggestion_message(outdated_components)
        return ExceptionBody(**body)
