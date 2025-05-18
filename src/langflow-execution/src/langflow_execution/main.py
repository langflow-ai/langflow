
import pkg_resources
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langflow_execution.services.manager import ServiceManager
from langflow_execution.api import health_check_router, router

async def lifespan(app: FastAPI):
    service_manager = ServiceManager.get_instance()
    try:
        yield
    finally:
        print("Stopping services...")
        await service_manager.stop()
        print("Shutdown complete. See you next time!")

def create_app() -> FastAPI:
    current_version = pkg_resources.get_distribution("langflow-execution").version
    app = FastAPI(title="Langflow Execution", version=current_version, lifespan=lifespan)

    # TODO: Add sentry, middleware, etc.
    # TODO: server on windows

    # CORS (optional, but common for APIs)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_check_router)
    app.include_router(router)
    
    return app

def run_server(host: str = "127.0.0.1", port: int = 8000, log_level: str = "info", reload: bool = False):
    import uvicorn
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level=log_level, reload=reload) 