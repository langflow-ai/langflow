from fastapi import FastAPI
from endpoints import router as endpoints_router
from list_endpoints import router as list_router
from signature import router as signatures_router
from fastapi.middleware.cors import CORSMiddleware


def create_app():
    """Create the FastAPI app and include the router."""
    app = FastAPI()

    origins = [
        "http://localhost",
        "http://localhost:8080",
        "http://localhost:3000",
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

    uvicorn.run(app, host="0.0.0.0", port=5003)
