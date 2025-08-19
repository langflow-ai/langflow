# Create an exception class that receives the message and the formatted traceback

from langflow.schema.properties import Source


class ComponentBuildError(Exception):
    def __init__(self, message: str, formatted_traceback: str):
        self.message = message
        self.formatted_traceback = formatted_traceback
        super().__init__(message)


class StreamingError(Exception):
    def __init__(self, cause: Exception, source: Source):
        self.cause = cause
        self.source = source
        super().__init__(cause)


class ComponentLockError(ComponentBuildError):
    """Raised when component execution blocked per sandboxing policies."""
    def __init__(self, component_path: str):
        self.component_path = component_path
        message = f"Cannot execute untrusted component '{component_path}'"
        formatted_traceback = f"ComponentLockError: {message}"
        super().__init__(message, formatted_traceback)


