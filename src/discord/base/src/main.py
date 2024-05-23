from .api import router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app():
    """Create the FastAPI app and include the router."""

    # socketio_server = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*", logger=True)
    # lifespan = get_lifespan(socketio_server=socketio_server)
    app = FastAPI()  # lifespan=lifespan)
    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # app.add_middleware(JavaScriptMIMETypeMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(router)

    # app = mount_socketio(app, socketio_server)

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "langflow.main:create_discord_app",
        host="0.0.0.0",
        port=7880,
        workers=1,
        log_level="error",
        reload=True,
        loop="asyncio",
    )
