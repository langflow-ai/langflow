from fastapi import FastAPI
from endpoints import router


def create_app():
    """Create the FastAPI app and include the router."""
    app = FastAPI()
    app.include_router(router)
    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app)
