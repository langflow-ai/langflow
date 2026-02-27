from fastapi import HTTPException
from pydantic import BaseModel

from langflow.api.utils import get_suggestion_message
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow.utils import get_outdated_components


class InvalidChatInputError(Exception):
    pass


class WorkflowExecutionError(Exception):
    """Base exception for workflow execution errors."""


class WorkflowTimeoutError(WorkflowExecutionError):
    """Workflow execution timeout."""


class WorkflowValidationError(WorkflowExecutionError):
    """Workflow validation error (e.g., invalid flow data, graph build failure)."""


class WorkflowQueueFullError(WorkflowExecutionError):
    """Raised when the background task queue is full."""


class WorkflowResourceError(WorkflowExecutionError):
    """Raised when the server is out of memory or other resources."""


class WorkflowServiceUnavailableError(WorkflowExecutionError):
    """Raised when the task queue service is unavailable (e.g., broker down)."""


# create a pidantic documentation for this class
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
