from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from langflow.api.chat import router as chat_router
from langflow.api.endpoints import router as endpoints_router
from langflow.api.validate import router as validate_router
from langflow.api.database import router as database_router
from langflow.database.base import create_db_and_tables
from fastapi import APIRouter


# build router
router = APIRouter()


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
    app.include_router(validate_router)
    app.include_router(chat_router)
    app.include_router(database_router)

    app.on_event("startup")(create_db_and_tables)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=7860)
