# Create an exception class that receives the message and the formatted traceback
class ComponentBuildException(Exception):
    def __init__(self, message: str, formatted_traceback: str):
        self.message = message
        self.formatted_traceback = formatted_traceback
        super().__init__(message)
