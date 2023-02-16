from fastapi import FastAPI
from endpoints import router as endpoints_router
from list import router as list_router
from signature import router as signatures_router


def create_app():
    """Create the FastAPI app and include the router."""
    app = FastAPI()
    app.include_router(endpoints_router)
    app.include_router(list_router)
    app.include_router(signatures_router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
