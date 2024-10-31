# Create an exception class that receives the message and the formatted traceback
class ComponentBuildError(Exception):
    def __init__(self, message: str, formatted_traceback: str):
        self.message = message
        self.formatted_traceback = formatted_traceback
        super().__init__(message)


class StreamingError(Exception):
    def __init__(self, cause: Exception, component_name: str):
        self.cause = cause
        self.component_name = component_name
        super().__init__(cause)
