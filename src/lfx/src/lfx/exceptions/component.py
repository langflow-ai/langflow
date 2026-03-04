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


class CustomComponentNotAllowedError(Exception):
    """Raised when a flow contains custom components that are not in the hash allowlist."""

    def __init__(self, blocked_components: list[dict[str, str]]):
        self.blocked_components = blocked_components
        names = [c.get("display_name", "Unknown") for c in blocked_components]
        super().__init__(f"Custom components are not allowed: {', '.join(names)}")
