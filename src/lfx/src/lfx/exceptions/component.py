from lfx.schema.properties import Source


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
