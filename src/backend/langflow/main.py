from fastapi import FastAPI
from langflow.api.endpoints import router as endpoints_router
from langflow.api.list_endpoints import router as list_router
from langflow.api.signature import router as signatures_router
from fastapi.middleware.cors import CORSMiddleware


def create_app():
    """Create the FastAPI app and include the router."""
    app = FastAPI()

    origins = [
        "*",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(endpoints_router)
    app.include_router(list_router)
    app.include_router(signatures_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=7860)
