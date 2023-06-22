from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from langflow.api import router
from langflow.database.base import create_db_and_tables

template_node = {
    "template": {
        "lc_kwargs": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "password": "false",
            "name": "lc_kwargs",
            "advanced": "true",
            "type": "code",
            "list": "false"
        },
        "verbose": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "value": "false",
            "password": "false",
            "name": "verbose",
            "advanced": "false",
            "type": "bool",
            "list": "false"
        },
        "callbacks": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "password": "false",
            "name": "callbacks",
            "advanced": "false",
            "type": "langchain.callbacks.base.BaseCallbackHandler",
            "list": "true"
        },
        "tags": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "password": "false",
            "name": "tags",
            "advanced": "false",
            "type": "str",
            "list": "true"
        },
        "client": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "password": "false",
            "name": "client",
            "advanced": "false",
            "type": "Any",
            "list": "false"
        },
        "model_name": {
            "required": "false",
            "placeholder": "",
            "show": "true",
            "multiline": "false",
            "value": "gpt-3.5-turbo",
            "password": "false",
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
            "advanced": "false",
            "type": "str",
            "list": "true"
        },
        "temperature": {
            "required": "false",
            "placeholder": "",
            "show": "true",
            "multiline": "false",
            "value": 0.7,
            "password": "false",
            "name": "temperature",
            "advanced": "false",
            "type": "float",
            "list": "false"
        },
        "model_kwargs": {
            "required": "false",
            "placeholder": "",
            "show": "true",
            "multiline": "false",
            "password": "false",
            "name": "model_kwargs",
            "advanced": "true",
            "type": "code",
            "list": "false"
        },
        "openai_api_key": {
            "required": "false",
            "placeholder": "",
            "show": "true",
            "multiline": "false",
            "value": "",
            "password": "true",
            "name": "openai_api_key",
            "display_name": "OpenAI API Key",
            "advanced": "false",
            "type": "str",
            "list": "false"
        },
        "openai_api_base": {
            "required": "false",
            "placeholder": "",
            "show": "true",
            "multiline": "false",
            "password": "false",
            "name": "openai_api_base",
            "display_name": "OpenAI API Base",
            "advanced": "false",
            "type": "str",
            "list": "false"
        },
        "openai_organization": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "password": "false",
            "name": "openai_organization",
            "display_name": "OpenAI Organization",
            "advanced": "false",
            "type": "str",
            "list": "false"
        },
        "openai_proxy": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "password": "false",
            "name": "openai_proxy",
            "display_name": "OpenAI Proxy",
            "advanced": "false",
            "type": "str",
            "list": "false"
        },
        "request_timeout": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "password": "false",
            "name": "request_timeout",
            "advanced": "false",
            "type": "float",
            "list": "false"
        },
        "max_retries": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "value": 6,
            "password": "false",
            "name": "max_retries",
            "advanced": "false",
            "type": "int",
            "list": "false"
        },
        "streaming": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "value": "false",
            "password": "false",
            "name": "streaming",
            "advanced": "false",
            "type": "bool",
            "list": "false"
        },
        "n": {
            "required": "false",
            "placeholder": "",
            "show": "false",
            "multiline": "false",
            "value": 1,
            "password": "false",
            "name": "n",
            "advanced": "false",
            "type": "int",
            "list": "false"
        },
        "max_tokens": {
            "required": "false",
            "placeholder": "",
            "show": "true",
            "multiline": "false",
            "password": "true",
            "name": "max_tokens",
            "advanced": "false",
            "type": "int",
            "list": "false"
        },
        "_type": "ChatOpenAI"
    },
    "description": "Wrapper around OpenAI Chat large language models.",
    "base_classes": [
        "BaseChatModel",
        "Serializable",
        "BaseLanguageModel",
        "ChatOpenAI"
    ],
    "display_name": "ChatOpenAI"
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
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=7860)
