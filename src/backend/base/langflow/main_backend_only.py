from langflow.main import setup_app

def create_backend_only_app():
    """Create the FastAPI app in backend-only mode."""
    return setup_app(backend_only=True)

app = create_backend_only_app()