from fastapi import FastAPI
from endpoints import router as endpoints_router
from list import router as list_router


def create_app():
    """Create the FastAPI app and include the router."""
    app = FastAPI()
    app.include_router(endpoints_router)
    app.include_router(list_router)
    return app


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app)
