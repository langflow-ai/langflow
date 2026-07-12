"""Task/workflow exceptions owned by the services package."""


class WorkflowExecutionError(Exception):
    """Base exception for workflow execution errors."""


class WorkflowResourceError(WorkflowExecutionError):
    """Raised when the server is out of memory or other resources."""


class WorkflowServiceUnavailableError(WorkflowExecutionError):
    """Raised when the task queue service is unavailable (e.g., broker down)."""


# Preserve the historical pickle/import path used by langflow.exceptions.api.
WorkflowExecutionError.__module__ = "langflow.exceptions.api"
WorkflowResourceError.__module__ = "langflow.exceptions.api"
WorkflowServiceUnavailableError.__module__ = "langflow.exceptions.api"

__all__ = [
    "WorkflowExecutionError",
    "WorkflowResourceError",
    "WorkflowServiceUnavailableError",
]
