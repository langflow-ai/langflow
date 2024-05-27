from .api import router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .utils import default


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

    @app.on_event("startup")
    async def on_startup():
        print("on_startup", flush=True)
        with open(default.DEFAULT_MESSAGE_FILE, "w") as f:
            f.write("[]")
        with open(default.DEFAULT_SCRIPT_FILE, "w") as f:
            f.write("import streamlit as st")
        
        # Monta o comando para executar o arquivo no Streamlit
        command = ["streamlit", "run", default.DEFAULT_SCRIPT_FILE, "--browser.serverPort", "5001", "--server.port", "5001"]
        from subprocess import Popen
        Popen(command)

    app.include_router(router)

    # app = mount_socketio(app, socketio_server)

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:create_app",
        host="0.0.0.0",
        port=7881,
        workers=1,
        log_level="error",
        reload=True,
        loop="asyncio",
    )
