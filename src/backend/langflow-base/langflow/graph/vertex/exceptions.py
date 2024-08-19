class NoComponentInstance(Exception):
    def __init__(self, vertex_id: str):
        message = f"Vertex {vertex_id} does not have a component instance."
        super().__init__(message)
