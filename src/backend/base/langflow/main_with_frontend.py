from pathlib import Path

from langflow.main import setup_app


def create_app_with_frontend():
    """Create the FastAPI app with the correct frontend path."""
    # Get the correct path to the frontend build directory
    current_file = Path(__file__)
    # Go up to langflow/src/backend/base/langflow, then to langflow/src/frontend/build
    frontend_build_path = current_file.parent.parent.parent.parent.parent / "src" / "frontend" / "build"

    if frontend_build_path.exists():
        return setup_app(static_files_dir=frontend_build_path, backend_only=False)
    # Fallback to backend only if frontend build doesn't exist
    print(f"Frontend build directory not found at {frontend_build_path}, running backend only")
    return setup_app(backend_only=True)


app = create_app_with_frontend()
