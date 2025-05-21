class NoComponentInstanceError(Exception):
    def __init__(self, vertex_id: str):
        message = f"Vertex {vertex_id} does not have a component instance."
        super().__init__(message)


class ComponentBuildError(Exception):
    def __init__(self, message: str, formatted_traceback: str):
        self.message = message
        self.formatted_traceback = formatted_traceback
        super().__init__(message)
