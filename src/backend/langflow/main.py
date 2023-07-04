from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from langflow.api import router
from langflow.database.base import create_db_and_tables
from langflow.interface.utils import setup_llm_caching

template_node = {
    "template": {
        "code": {
            "required": True,
            "placeholder": "",
            "show": True,
            "multiline": True,
            "value": "\ndef my_user_python_function(text: str) -> str:\n    \"\"\"This is a default python function that returns the input text\"\"\"\n    return text.upper()\n",
            "password": False,
            "name": "code",
            "advanced": False,
            "type": "code",
            "list": False
        },
        "lc_kwargs": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "password": False,
            "name": "lc_kwargs",
            "advanced": True,
            "type": "code",
            "list": False
        },
        "verbose": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "value": False,
            "password": False,
            "name": "verbose",
            "advanced": False,
            "type": "bool",
            "list": False
        },
        "callbacks": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "password": False,
            "name": "callbacks",
            "advanced": False,
            "type": "langchain.callbacks.base.BaseCallbackHandler",
            "list": True
        },
        "tags": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "password": False,
            "name": "tags",
            "advanced": False,
            "type": "str",
            "list": True
        },
        "client": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "password": False,
            "name": "client",
            "advanced": False,
            "type": "Any",
            "list": False
        },
        "model_name": {
            "required": False,
            "placeholder": "",
            "show": True,
            "multiline": False,
            "value": "gpt-3.5-turbo",
            "password": False,
            "options": [
                "gpt-3.5-turbo-0613",
                "gpt-3.5-turbo",
                "gpt-3.5-turbo-16k-0613",
                "gpt-3.5-turbo-16k",
                "gpt-4-0613",
                "gpt-4-32k-0613",
                "gpt-4",
                "gpt-4-32k"
            ],
            "name": "model_name",
            "advanced": False,
            "type": "str",
            "list": True
        },
        "temperature": {
            "required": False,
            "placeholder": "",
            "show": True,
            "multiline": False,
            "value": 0.7,
            "password": False,
            "name": "temperature",
            "advanced": False,
            "type": "float",
            "list": False
        },
        "model_kwargs": {
            "required": False,
            "placeholder": "",
            "show": True,
            "multiline": False,
            "password": False,
            "name": "model_kwargs",
            "advanced": True,
            "type": "code",
            "list": False
        },
        "openai_api_key": {
            "required": False,
            "placeholder": "",
            "show": True,
            "multiline": False,
            "value": "",
            "password": True,
            "name": "openai_api_key",
            "display_name": "OpenAI API Key",
            "advanced": False,
            "type": "str",
            "list": False
        },
        "openai_api_base": {
            "required": False,
            "placeholder": "",
            "show": True,
            "multiline": False,
            "password": False,
            "name": "openai_api_base",
            "display_name": "OpenAI API Base",
            "advanced": False,
            "type": "str",
            "list": False
        },
        "openai_organization": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "password": False,
            "name": "openai_organization",
            "display_name": "OpenAI Organization",
            "advanced": False,
            "type": "str",
            "list": False
        },
        "openai_proxy": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "password": False,
            "name": "openai_proxy",
            "display_name": "OpenAI Proxy",
            "advanced": False,
            "type": "str",
            "list": False
        },
        "request_timeout": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "password": False,
            "name": "request_timeout",
            "advanced": False,
            "type": "float",
            "list": False
        },
        "max_retries": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "value": 6,
            "password": False,
            "name": "max_retries",
            "advanced": False,
            "type": "int",
            "list": False
        },
        "streaming": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "value": False,
            "password": False,
            "name": "streaming",
            "advanced": False,
            "type": "bool",
            "list": False
        },
        "n": {
            "required": False,
            "placeholder": "",
            "show": False,
            "multiline": False,
            "value": 1,
            "password": False,
            "name": "n",
            "advanced": False,
            "type": "int",
            "list": False
        },
        "max_tokens": {
            "required": False,
            "placeholder": "",
            "show": True,
            "multiline": False,
            "password": True,
            "name": "max_tokens",
            "advanced": False,
            "type": "int",
            "list": False
        },
        "_type": "ChatOpenAI"
    },
    "base_classes": [
        "BaseChatModel",
        "Serializable",
        "BaseLanguageModel",
        "ChatOpenAI"
    ],
    "description": "Wrapper around OpenAI Chat large language models."
}


def create_app():
    """Create the FastAPI app and include the router."""

    app = FastAPI()

    origins = [
        "*",
    ]

    @app.get("/health")
    def get_health():
        return {"status": "OK"}

    @app.get("/dynamic_node")
    def get_dynamic_nome():
        return template_node

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.on_event("startup")(create_db_and_tables)
    app.on_event("startup")(setup_llm_caching)
    return app


def setup_static_files(app: FastAPI, static_files_dir: Path):
    """
    Setup the static files directory.
    Args:
        app (FastAPI): FastAPI app.
        path (str): Path to the static files directory.
    """
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )

    @app.exception_handler(404)
    async def custom_404_handler(request, __):
        path = static_files_dir / "index.html"

        if not path.exists():
            raise RuntimeError(f"File at path {path} does not exist.")
        return FileResponse(path)


# app = create_app()
# setup_static_files(app, static_files_dir)
def setup_app(static_files_dir: Optional[Path]) -> FastAPI:
    """Setup the FastAPI app."""
    # get the directory of the current file
    if not static_files_dir:
        frontend_path = Path(__file__).parent
        static_files_dir = frontend_path / "frontend"

    app = create_app()
    setup_static_files(app, static_files_dir)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=7860)
